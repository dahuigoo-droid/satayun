# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
서비스 작업 통합 버전
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="PDF 자동 생성 플랫폼",
    page_icon="🔮",
    layout="wide"
)

# ============================================
# 데이터베이스 임포트
# ============================================

from database import init_db, SessionLocal
from auth import (
    register_user, login_user, update_user_profile, change_password,
    get_all_users, get_pending_users, approve_user, suspend_user,
    create_first_admin, check_admin_exists
)
from services import (
    get_all_services, get_service_by_id, add_service, delete_service, update_service,
    get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, delete_chapter, update_chapter,
    get_guidelines_by_service, add_guideline, delete_guideline, update_guideline,
    get_templates_by_service, add_template, delete_template,
    TEMPLATE_TYPES
)
from notices import get_all_notices, create_notice, update_notice, delete_notice

# ============================================
# 모드 키
# ============================================

API_MODE_KEY = "api_mode"
EMAIL_MODE_KEY = "email_mode"

# ============================================
# CSS (라디오 버튼 숨기기 + 커서 포인터)
# ============================================

st.markdown("""
<style>
    .main-title { text-align: center; color: #fff; font-size: 2.5rem; margin-bottom: 10px; }
    .sub-title { text-align: center; color: #888; font-size: 1rem; margin-bottom: 30px; }
    
    /* 사이드바 라디오 버튼 숨기기 */
    section[data-testid="stSidebar"] .stRadio > div {
        flex-direction: column;
    }
    section[data-testid="stSidebar"] .stRadio > div > label {
        cursor: pointer !important;
        padding: 10px 15px;
        border-radius: 8px;
        margin: 2px 0;
        transition: background 0.2s;
    }
    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(255,255,255,0.1);
    }
    section[data-testid="stSidebar"] .stRadio > div > label > div:first-child {
        display: none !important;
    }
    
    /* 섹션 헤더 */
    .section-header { 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px 20px; 
        border-radius: 10px; 
        margin: 25px 0 15px 0;
        color: white;
        font-weight: bold;
    }
    
    /* 완료/대기 상태 */
    .status-done { 
        background: #28a745; 
        color: white;
        padding: 3px 10px; 
        border-radius: 15px; 
        font-size: 0.85rem;
    }
    .status-pending { 
        background: #ffc107; 
        color: black;
        padding: 3px 10px; 
        border-radius: 15px; 
        font-size: 0.85rem;
    }
    
    /* 큰 텍스트 영역 */
    .big-textarea textarea {
        min-height: 400px !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# 종소리 JavaScript
# ============================================

def play_bell_sound():
    """완료 시 종소리"""
    st.markdown("""
    <script>
        var audio = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3');
        audio.play();
    </script>
    """, unsafe_allow_html=True)

# ============================================
# 세션 상태
# ============================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'customers_df' not in st.session_state:
    st.session_state.customers_df = None
if 'admin_created' not in st.session_state:
    st.session_state.admin_created = False
if 'selected_customers' not in st.session_state:
    st.session_state.selected_customers = []
if 'completed_customers' not in st.session_state:
    st.session_state.completed_customers = {}  # {idx: filepath}
if 'pdf_just_completed' not in st.session_state:
    st.session_state.pdf_just_completed = False

# ============================================
# DB 초기화
# ============================================

@st.cache_resource
def initialize_database():
    init_db()
    return True

try:
    initialize_database()
except Exception as e:
    st.error(f"DB 초기화 오류: {e}")

# ============================================
# 디렉토리
# ============================================

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ============================================
# 폰트 목록
# ============================================

FONT_OPTIONS = {
    "나눔고딕": "NanumGothic",
    "나눔명조": "NanumMyeongjo",
    "나눔바른고딕": "NanumBarunGothic",
    "맑은고딕": "MalgunGothic",
    "돋움": "Dotum",
    "굴림": "Gulim",
    "바탕": "Batang",
}

# 속지 타입
TEMPLATE_TYPES_NEW = {
    "cover": "📕 표지",
    "background": "📄 내지 (본문 배경)",
    "info": "📋 안내지 (마지막)"
}

# ============================================
# 유틸리티
# ============================================

def check_permission(required_role: int) -> bool:
    if not st.session_state.user:
        return False
    return st.session_state.user.get('role', 0) >= required_role

def save_uploaded_file(uploaded_file, prefix: str) -> str:
    if uploaded_file is None:
        return None
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filepath

def get_api_key() -> dict:
    user = st.session_state.user
    api_mode = get_system_config(API_MODE_KEY, "unified")
    admin_api = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
    user_api = user.get('api_key', '') or ''
    
    if api_mode == "unified":
        return {"key": admin_api, "source": "관리자", "mode": "unified"}
    else:
        if user_api:
            return {"key": user_api, "source": "개인", "mode": "separated"}
        else:
            return {"key": admin_api, "source": "관리자 (개인 미설정)", "mode": "separated"}

def get_email_config() -> dict:
    user = st.session_state.user
    email_mode = get_system_config(EMAIL_MODE_KEY, "unified")
    admin_gmail = get_system_config(ConfigKeys.ADMIN_GMAIL, "")
    admin_gmail_pw = get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, "")
    user_gmail = user.get('gmail_address', '') or ''
    user_gmail_pw = user.get('gmail_app_password', '') or ''
    
    if email_mode == "unified":
        if admin_gmail and admin_gmail_pw:
            return {"email": admin_gmail, "password": admin_gmail_pw, "source": "관리자"}
        return None
    else:
        if user_gmail and user_gmail_pw:
            return {"email": user_gmail, "password": user_gmail_pw, "source": "개인"}
        elif admin_gmail and admin_gmail_pw:
            return {"email": admin_gmail, "password": admin_gmail_pw, "source": "관리자 (개인 미설정)"}
        return None

# ============================================
# 로그인 페이지
# ============================================

def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<h1 class="main-title">🔮 PDF 자동 생성 플랫폼</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">사주 · 타로 · 연애</p>', unsafe_allow_html=True)
        
        if st.session_state.admin_created:
            st.success("✅ 관리자 계정이 생성되었습니다! 위에서 로그인하세요.")
            st.session_state.admin_created = False
        
        tab1, tab2 = st.tabs(["🔐 로그인", "📝 회원가입"])
        
        with tab1:
            email = st.text_input("이메일", key="login_email")
            password = st.text_input("비밀번호", type="password", key="login_password")
            
            if st.button("로그인", type="primary", use_container_width=True):
                if email and password:
                    result = login_user(email, password)
                    if result["success"]:
                        st.session_state.logged_in = True
                        st.session_state.user = result["user"]
                        st.rerun()
                    else:
                        st.error(result["error"])
        
        with tab2:
            reg_name = st.text_input("이름", key="reg_name")
            reg_email = st.text_input("이메일", key="reg_email")
            reg_password = st.text_input("비밀번호", type="password", key="reg_password")
            reg_password2 = st.text_input("비밀번호 확인", type="password", key="reg_password2")
            
            if st.button("회원가입", type="primary", use_container_width=True):
                if all([reg_name, reg_email, reg_password, reg_password2]):
                    if reg_password != reg_password2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        result = register_user(reg_email, reg_password, reg_name)
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["error"])
        
        st.markdown("---")
        
        if not check_admin_exists():
            with st.expander("🔧 최초 관리자 설정", expanded=True):
                st.warning("⚠️ 관리자 계정을 먼저 생성하세요!")
                admin_name = st.text_input("관리자 이름", key="admin_name")
                admin_email = st.text_input("관리자 이메일", key="admin_email")
                admin_password = st.text_input("관리자 비밀번호", type="password", key="admin_password")
                
                if st.button("🔑 관리자 계정 생성", type="primary", use_container_width=True):
                    if all([admin_name, admin_email, admin_password]):
                        result = create_first_admin(admin_email, admin_password, admin_name)
                        if result["success"]:
                            st.session_state.admin_created = True
                            st.rerun()
                        else:
                            st.error(result["error"])

# ============================================
# 메인 앱
# ============================================

def show_main_app():
    user = st.session_state.user
    
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}님")
        role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
        st.caption(f"등급: {role_text.get(user['role'], user['role'])}")
        
        st.markdown("---")
        
        menu_options = []
        if user["role"] == 3:
            menu_options.extend(["⚙️ 관리자 설정", "👥 회원 관리"])
        menu_options.extend(["📦 서비스 작업", "👤 MyPage", "📢 공지사항"])
        
        selected = st.radio("메뉴", menu_options, label_visibility="collapsed")
        
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.customers_df = None
            st.session_state.selected_customers = []
            st.session_state.completed_customers = {}
            st.rerun()
    
    if selected == "⚙️ 관리자 설정":
        show_admin_settings()
    elif selected == "👥 회원 관리":
        show_user_management()
    elif selected == "📦 서비스 작업":
        show_service_work()
    elif selected == "👤 MyPage":
        show_mypage()
    elif selected == "📢 공지사항":
        show_notices()

# ============================================
# 관리자 설정
# ============================================

def show_admin_settings():
    st.title("⚙️ 관리자 설정")
    
    tab1, tab2, tab3 = st.tabs(["🔑 API", "📧 이메일", "⚡ 모드"])
    
    with tab1:
        api = st.text_input("OpenAI API 키", value=get_system_config(ConfigKeys.ADMIN_API_KEY, ""), type="password")
        if st.button("💾 저장", key="save_api"):
            set_system_config(ConfigKeys.ADMIN_API_KEY, api)
            st.success("✅ 저장됨")
    
    with tab2:
        gmail = st.text_input("Gmail 주소", value=get_system_config(ConfigKeys.ADMIN_GMAIL, ""))
        gmail_pw = st.text_input("Gmail 앱 비밀번호", value=get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, ""), type="password")
        if st.button("💾 저장", key="save_email"):
            set_system_config(ConfigKeys.ADMIN_GMAIL, gmail)
            set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, gmail_pw)
            st.success("✅ 저장됨")
    
    with tab3:
        api_mode = st.radio("API 모드", ["unified", "separated"],
            index=0 if get_system_config(API_MODE_KEY, "unified") == "unified" else 1,
            format_func=lambda x: "🔒 통일 (관리자만)" if x == "unified" else "🔓 분리 (각자)")
        
        email_mode = st.radio("이메일 모드", ["unified", "separated"],
            index=0 if get_system_config(EMAIL_MODE_KEY, "unified") == "unified" else 1,
            format_func=lambda x: "🔒 통일 (관리자만)" if x == "unified" else "🔓 분리 (각자)")
        
        if st.button("💾 모드 저장", type="primary"):
            set_system_config(API_MODE_KEY, api_mode)
            set_system_config(EMAIL_MODE_KEY, email_mode)
            st.success("✅ 저장됨")

# ============================================
# 회원 관리
# ============================================

def show_user_management():
    st.title("👥 회원 관리")
    
    tab1, tab2 = st.tabs(["전체", "대기"])
    
    with tab1:
        for u in get_all_users():
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{u['name']}** ({u['email']}) - {u['status']}")
            if u['id'] != st.session_state.user['id'] and u['status'] == 'approved':
                if col2.button("정지", key=f"sus_{u['id']}"):
                    suspend_user(u['id'])
                    st.rerun()
    
    with tab2:
        pending = get_pending_users()
        if not pending:
            st.success("대기 중인 회원이 없습니다.")
        for u in pending:
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{u['name']}** ({u['email']})")
            if col2.button("승인", key=f"ap_{u['id']}", type="primary"):
                approve_user(u['id'])
                st.rerun()

# ============================================
# 📦 서비스 작업 (통합 - 모든 작업 포함)
# ============================================

def show_service_work():
    st.title("📦 서비스 작업")
    
    # API 확인
    api_info = get_api_key()
    if not api_info["key"]:
        st.error("⚠️ API 키가 설정되지 않았습니다. 관리자에게 문의하세요.")
        return
    
    # ========================================
    # 1️⃣ 서비스 종류 (목차 + 지침 세트)
    # ========================================
    st.markdown('<div class="section-header">1️⃣ 서비스 종류 선택/관리 (목차 + 지침)</div>', unsafe_allow_html=True)
    
    services = get_all_services()
    
    # 관리자만 서비스 추가/수정 가능
    if check_permission(3):
        with st.expander("➕ 새 서비스 종류 추가", expanded=False):
            new_svc_name = st.text_input("서비스 이름", placeholder="예: 2024년 사주", key="new_svc_name")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📑 목차 내용**")
                new_chapters = st.text_area(
                    "목차 (줄바꿈으로 구분)",
                    height=400,
                    placeholder="1. 올해의 총운\n2. 재물운\n3. 건강운\n4. 연애운\n...",
                    key="new_chapters"
                )
            
            with col2:
                st.markdown("**📜 지침 내용**")
                new_guideline = st.text_area(
                    "AI 작성 지침",
                    height=400,
                    placeholder="- 긍정적이고 희망적인 톤으로 작성\n- 각 목차당 300자 이상\n- 구체적인 시기 언급\n...",
                    key="new_guideline"
                )
            
            if st.button("💾 서비스 저장", type="primary", key="save_new_svc"):
                if new_svc_name:
                    # 서비스 추가
                    result = add_service(new_svc_name, "")
                    if result.get("success"):
                        svc_id = result.get("id")
                        # 목차 추가
                        if new_chapters:
                            for idx, ch in enumerate(new_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx + 1)
                        # 지침 추가
                        if new_guideline:
                            add_guideline(svc_id, f"{new_svc_name} 지침", new_guideline)
                        st.success(f"✅ '{new_svc_name}' 서비스가 생성되었습니다!")
                        st.rerun()
                else:
                    st.error("서비스 이름을 입력하세요.")
    
    # 서비스 선택
    if not services:
        st.warning("등록된 서비스가 없습니다. 관리자가 먼저 서비스를 등록해야 합니다.")
        return
    
    service_names = [s['name'] for s in services]
    selected_service_name = st.selectbox("📌 서비스 선택", service_names, key="sel_service")
    selected_service = next((s for s in services if s['name'] == selected_service_name), None)
    
    if selected_service:
        # 선택된 서비스 내용 표시
        with st.expander(f"📋 '{selected_service_name}' 상세 보기/수정", expanded=False):
            chapters = get_chapters_by_service(selected_service['id'])
            guidelines = get_guidelines_by_service(selected_service['id'])
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📑 목차**")
                chapters_text = "\n".join([c['title'] for c in chapters]) if chapters else ""
                edited_chapters = st.text_area("목차 수정", value=chapters_text, height=400, key=f"edit_ch_{selected_service['id']}")
            
            with col2:
                st.markdown("**📜 지침**")
                guideline_text = guidelines[0]['content'] if guidelines else ""
                edited_guideline = st.text_area("지침 수정", value=guideline_text, height=400, key=f"edit_g_{selected_service['id']}")
            
            if check_permission(3):
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 수정 저장", key=f"update_svc_{selected_service['id']}"):
                        # 기존 목차 삭제 후 재등록
                        for ch in chapters:
                            delete_chapter(ch['id'])
                        for idx, ch in enumerate(edited_chapters.strip().split("\n")):
                            if ch.strip():
                                add_chapter(selected_service['id'], ch.strip(), "", idx + 1)
                        
                        # 지침 업데이트
                        if guidelines:
                            update_guideline(guidelines[0]['id'], guidelines[0]['title'], edited_guideline)
                        else:
                            add_guideline(selected_service['id'], f"{selected_service_name} 지침", edited_guideline)
                        
                        st.success("✅ 수정 저장됨")
                        st.rerun()
                
                with col_btn2:
                    if st.button("🗑️ 서비스 삭제", key=f"del_svc_{selected_service['id']}"):
                        delete_service(selected_service['id'])
                        st.success("삭제됨")
                        st.rerun()
    
    # ========================================
    # 2️⃣ 디자인 종류 (속지 세트)
    # ========================================
    st.markdown('<div class="section-header">2️⃣ 디자인 종류 선택/관리 (속지)</div>', unsafe_allow_html=True)
    
    # 디자인 세트 조회 (서비스별 templates를 디자인 이름으로 그룹화)
    all_templates = []
    for svc in services:
        templates = get_templates_by_service(svc['id'])
        all_templates.extend(templates)
    
    # 디자인 이름 추출 (고유 이름들)
    design_names = list(set([t['name'].split('_')[0] if '_' in t['name'] else t['name'] for t in all_templates]))
    
    # 관리자만 디자인 추가/수정 가능
    if check_permission(3):
        with st.expander("➕ 새 디자인 종류 추가", expanded=False):
            new_design_name = st.text_input("디자인 이름", placeholder="예: 2024년 사주", key="new_design_name")
            st.caption("⚠️ 서비스 이름과 동일하게 작성하세요!")
            
            st.markdown("**속지 업로드**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("📕 **표지**")
                cover_file = st.file_uploader("표지 이미지", type=["jpg", "jpeg", "png"], key="new_cover")
                if cover_file:
                    st.image(cover_file, width=150)
            
            with col2:
                st.markdown("📄 **내지 (본문 배경)**")
                bg_file = st.file_uploader("내지 이미지", type=["jpg", "jpeg", "png"], key="new_bg")
                if bg_file:
                    st.image(bg_file, width=150)
            
            with col3:
                st.markdown("📋 **안내지 (마지막)**")
                info_file = st.file_uploader("안내지 이미지", type=["jpg", "jpeg", "png"], key="new_info")
                if info_file:
                    st.image(info_file, width=150)
            
            if st.button("💾 디자인 저장", type="primary", key="save_new_design"):
                if new_design_name and selected_service:
                    saved_count = 0
                    if cover_file:
                        path = save_uploaded_file(cover_file, f"{new_design_name}_cover")
                        add_template(selected_service['id'], "cover", f"{new_design_name}_표지", path)
                        saved_count += 1
                    if bg_file:
                        path = save_uploaded_file(bg_file, f"{new_design_name}_bg")
                        add_template(selected_service['id'], "background", f"{new_design_name}_내지", path)
                        saved_count += 1
                    if info_file:
                        path = save_uploaded_file(info_file, f"{new_design_name}_info")
                        add_template(selected_service['id'], "info", f"{new_design_name}_안내지", path)
                        saved_count += 1
                    
                    if saved_count > 0:
                        st.success(f"✅ '{new_design_name}' 디자인이 저장되었습니다! ({saved_count}개 파일)")
                        st.rerun()
                else:
                    st.error("디자인 이름을 입력하고 서비스를 선택하세요.")
    
    # 디자인 선택
    templates = get_templates_by_service(selected_service['id']) if selected_service else []
    
    # 디자인 이름 그룹화
    design_groups = {}
    for t in templates:
        # 이름에서 디자인 그룹 추출 (예: "2024사주_표지" → "2024사주")
        base_name = t['name'].replace("_표지", "").replace("_내지", "").replace("_안내지", "")
        if base_name not in design_groups:
            design_groups[base_name] = {"cover": None, "background": None, "info": None}
        design_groups[base_name][t['template_type']] = t
    
    if not design_groups:
        st.info("등록된 디자인이 없습니다.")
        selected_design_name = None
    else:
        design_options = list(design_groups.keys())
        selected_design_name = st.selectbox("📌 디자인 선택", design_options, key="sel_design")
        
        # 선택된 디자인 미리보기
        if selected_design_name:
            design = design_groups[selected_design_name]
            cols = st.columns(3)
            
            for idx, (ttype, tname) in enumerate([("cover", "📕 표지"), ("background", "📄 내지"), ("info", "📋 안내지")]):
                with cols[idx]:
                    st.markdown(f"**{tname}**")
                    if design[ttype] and design[ttype].get('image_path'):
                        path = design[ttype]['image_path']
                        if os.path.exists(path):
                            st.image(path, width=150)
                        else:
                            st.caption("이미지 없음")
                    else:
                        st.caption("미등록")
    
    # ========================================
    # ⚠️ 서비스-디자인 매칭 확인
    # ========================================
    if selected_service_name and selected_design_name:
        # 이름 비교 (앞부분 일치 확인)
        svc_base = selected_service_name.replace(" ", "")
        design_base = selected_design_name.replace(" ", "").replace("_표지", "").replace("_내지", "").replace("_안내지", "")
        
        if svc_base not in design_base and design_base not in svc_base:
            st.warning(f"⚠️ **주의:** 서비스 '{selected_service_name}'와 디자인 '{selected_design_name}'의 이름이 일치하지 않습니다!")
            st.info("서비스와 디자인 이름을 동일하게 맞춰주세요.")
        else:
            st.success(f"✅ 서비스 '{selected_service_name}' + 디자인 '{selected_design_name}' 매칭 완료")
    
    # ========================================
    # 3️⃣ 폰트 / 스타일 설정
    # ========================================
    st.markdown('<div class="section-header">3️⃣ 폰트 / 스타일 설정</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        font = st.selectbox("폰트", list(FONT_OPTIONS.keys()), key="font_sel")
    with col2:
        font_size = st.number_input("글자 크기", 8, 30, 14, key="font_size")
    with col3:
        char_width = st.number_input("장평 (%)", 50, 150, 100, key="char_width")
    with col4:
        letter_spacing = st.number_input("자간", -5, 10, 0, key="letter_spacing")
    with col5:
        line_height = st.number_input("행간", 10, 50, 24, key="line_height")
    
    # ========================================
    # 4️⃣ 고객 파일 업로드
    # ========================================
    st.markdown('<div class="section-header">4️⃣ 고객 파일 업로드</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("엑셀 파일 (.xlsx, .xls)", type=["xlsx", "xls"], key="customer_file")
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.session_state.customers_df = df
        st.success(f"✅ {len(df)}명 로드됨")
        st.caption(f"컬럼: {', '.join(df.columns.tolist())}")
    
    # ========================================
    # 5️⃣ 고객 선택 및 PDF 변환
    # ========================================
    if st.session_state.customers_df is not None and selected_service and selected_design_name:
        st.markdown('<div class="section-header">5️⃣ 고객 선택 및 PDF 변환</div>', unsafe_allow_html=True)
        
        df = st.session_state.customers_df
        
        # 이름 컬럼 찾기
        name_col = None
        for col in ['이름', 'name', 'Name', '성명', '고객명']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            name_col = df.columns[0]
        
        # 선택 모드
        mode = st.radio("선택 모드", ["✅ 전체 선택", "🔘 개별 선택"], horizontal=True, key="select_mode")
        
        if mode == "✅ 전체 선택":
            st.session_state.selected_customers = list(range(len(df)))
        
        # 고객 목록 표시
        st.markdown("---")
        
        cols_per_row = 4
        rows = (len(df) + cols_per_row - 1) // cols_per_row
        
        selected = []
        for row_idx in range(rows):
            cols = st.columns(cols_per_row)
            for col_idx in range(cols_per_row):
                idx = row_idx * cols_per_row + col_idx
                if idx >= len(df):
                    break
                
                with cols[col_idx]:
                    row = df.iloc[idx]
                    cust_name = row[name_col]
                    
                    # 완료 상태 확인
                    is_done = idx in st.session_state.completed_customers
                    
                    if is_done:
                        # 완료된 고객
                        st.markdown(f'<span class="status-done">✅ 완료</span> **{cust_name}**', unsafe_allow_html=True)
                        
                        # 다운로드 버튼
                        filepath = st.session_state.completed_customers.get(idx)
                        if filepath and os.path.exists(filepath):
                            with open(filepath, "rb") as f:
                                st.download_button(
                                    "⬇️ 다운로드",
                                    f.read(),
                                    file_name=f"{cust_name}_report.pdf",
                                    mime="application/pdf",
                                    key=f"dl_{idx}"
                                )
                    else:
                        # 대기 중 고객
                        if mode == "🔘 개별 선택":
                            if st.checkbox(f"⏳ {cust_name}", key=f"cust_{idx}"):
                                selected.append(idx)
                        else:
                            st.markdown(f'<span class="status-pending">⏳ 대기</span> **{cust_name}**', unsafe_allow_html=True)
                            selected.append(idx)
        
        if mode == "🔘 개별 선택":
            st.session_state.selected_customers = selected
        
        st.markdown("---")
        
        # 선택 현황
        pending_count = len([i for i in st.session_state.selected_customers if i not in st.session_state.completed_customers])
        done_count = len(st.session_state.completed_customers)
        
        st.info(f"📊 선택: {len(st.session_state.selected_customers)}명 | ⏳ 대기: {pending_count}명 | ✅ 완료: {done_count}명")
        
        # 진행 바
        total = len(df)
        if total > 0:
            st.progress(done_count / total)
        
        # PDF 변환 버튼
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🚀 PDF 변환 시작", type="primary", use_container_width=True):
                if not st.session_state.selected_customers:
                    st.error("고객을 선택하세요")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    pending = [i for i in st.session_state.selected_customers if i not in st.session_state.completed_customers]
                    total_pending = len(pending)
                    
                    for i, cust_idx in enumerate(pending):
                        row = df.iloc[cust_idx]
                        cust_name = row[name_col]
                        
                        status_text.text(f"📝 {cust_name} 처리 중... ({i+1}/{total_pending})")
                        progress_bar.progress((i + 1) / total_pending)
                        
                        # TODO: 실제 PDF 생성 로직
                        import time
                        time.sleep(0.5)  # 시뮬레이션
                        
                        # 임시 파일 경로 (실제로는 PDF 파일 경로)
                        pdf_path = os.path.join(OUTPUT_DIR, f"{cust_name}_report.pdf")
                        
                        # 완료 표시
                        st.session_state.completed_customers[cust_idx] = pdf_path
                        
                        # 종소리 (매번)
                        st.toast(f"🔔 {cust_name} 완료!")
                    
                    status_text.text("✅ 모든 PDF 변환 완료!")
                    st.balloons()
                    
                    # 종소리 HTML
                    st.markdown("""
                    <audio autoplay>
                        <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
                    </audio>
                    """, unsafe_allow_html=True)
                    
                    st.rerun()
        
        with col_btn2:
            if st.button("🔄 초기화", use_container_width=True):
                st.session_state.completed_customers = {}
                st.session_state.selected_customers = []
                st.rerun()

# ============================================
# MyPage
# ============================================

def show_mypage():
    st.title("👤 MyPage")
    user = st.session_state.user
    
    tab1, tab2, tab3 = st.tabs(["📋 내 정보", "🔑 API", "📧 이메일"])
    
    with tab1:
        new_name = st.text_input("이름", value=user['name'])
        st.text_input("이메일", value=user['email'], disabled=True)
        
        if st.button("저장"):
            result = update_user_profile(user['id'], name=new_name)
            if result["success"]:
                st.session_state.user['name'] = new_name
                st.success("저장됨")
        
        st.markdown("---")
        st.markdown("### 비밀번호 변경")
        old_pw = st.text_input("현재 비밀번호", type="password")
        new_pw = st.text_input("새 비밀번호", type="password")
        
        if st.button("변경"):
            if old_pw and new_pw:
                result = change_password(user['id'], old_pw, new_pw)
                if result["success"]:
                    st.success("변경됨")
                else:
                    st.error(result["error"])
    
    with tab2:
        api_mode = get_system_config(API_MODE_KEY, "unified")
        if api_mode == "unified":
            st.info("🔒 통일 모드: 관리자 API 사용 중")
        else:
            st.warning("🔓 분리 모드: 개인 API 등록 필요")
        
        my_api = st.text_input("내 API 키", value=user.get('api_key', '') or '', type="password")
        if st.button("API 저장"):
            result = update_user_profile(user['id'], api_key=my_api)
            if result["success"]:
                st.session_state.user['api_key'] = my_api
                st.success("저장됨")
    
    with tab3:
        email_mode = get_system_config(EMAIL_MODE_KEY, "unified")
        if email_mode == "unified":
            st.info("🔒 통일 모드: 관리자 이메일 사용 중")
        else:
            st.warning("🔓 분리 모드: 개인 이메일 등록 필요")
        
        my_gmail = st.text_input("내 Gmail", value=user.get('gmail_address', '') or '')
        my_gmail_pw = st.text_input("앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
        
        if st.button("이메일 저장"):
            result = update_user_profile(user['id'], gmail_address=my_gmail, gmail_app_password=my_gmail_pw)
            if result["success"]:
                st.session_state.user['gmail_address'] = my_gmail
                st.session_state.user['gmail_app_password'] = my_gmail_pw
                st.success("저장됨")

# ============================================
# 📢 공지사항 (관리자만 작성/수정)
# ============================================

def show_notices():
    st.title("📢 공지사항")
    
    user = st.session_state.user
    is_admin = user['role'] == 3
    
    # 관리자: 글쓰기 버튼
    if is_admin:
        with st.expander("✏️ 새 공지 작성", expanded=False):
            new_title = st.text_input("제목", key="notice_title")
            new_content = st.text_area("내용", height=200, key="notice_content")
            is_pinned = st.checkbox("📌 상단 고정", key="notice_pinned")
            
            if st.button("💾 공지 등록", type="primary"):
                if new_title and new_content:
                    result = create_notice(user['id'], new_title, new_content, None, is_pinned)
                    if result.get("success"):
                        st.success("✅ 공지가 등록되었습니다!")
                        st.rerun()
                    else:
                        st.error(result.get("error", "등록 실패"))
                else:
                    st.error("제목과 내용을 입력하세요.")
    
    st.markdown("---")
    
    # 공지 목록
    notices = get_all_notices()
    
    if not notices:
        st.info("등록된 공지사항이 없습니다.")
    else:
        for n in notices:
            pin = "📌 " if n['is_pinned'] else ""
            
            with st.expander(f"{pin}**{n['title']}** ({n['created_at']})", expanded=False):
                st.write(n['content'])
                
                # 관리자: 수정/삭제 버튼
                if is_admin:
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🗑️ 삭제", key=f"del_notice_{n['id']}"):
                            delete_notice(n['id'])
                            st.success("삭제됨")
                            st.rerun()
                    
                    with col2:
                        if st.button("📌 고정 토글", key=f"pin_notice_{n['id']}"):
                            # toggle pin
                            from notices import toggle_pin_notice
                            toggle_pin_notice(n['id'])
                            st.rerun()

# ============================================
# 메인
# ============================================

def main():
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
