# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
통합 서비스 작업 + PDF 생성 개선 버전
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
    get_all_services, get_service_by_id, add_service, delete_service,
    get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, delete_chapter, update_chapter,
    get_guidelines_by_service, add_guideline, delete_guideline, update_guideline,
    get_templates_by_service, add_template, delete_template,
    TEMPLATE_TYPES
)
from notices import get_all_notices, create_notice, delete_notice

# ============================================
# 모드 키
# ============================================

API_MODE_KEY = "api_mode"
EMAIL_MODE_KEY = "email_mode"

# ============================================
# CSS
# ============================================

st.markdown("""
<style>
    .main-title { text-align: center; color: #fff; font-size: 2.5rem; margin-bottom: 10px; }
    .sub-title { text-align: center; color: #888; font-size: 1rem; margin-bottom: 30px; }
    .service-box { 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px; border-radius: 15px; margin: 10px 0;
        text-align: center; cursor: pointer;
    }
    .service-box:hover { transform: scale(1.02); }
    .section-header { 
        background: rgba(255,255,255,0.1); 
        padding: 10px 20px; border-radius: 10px; 
        margin: 20px 0 10px 0;
    }
    .customer-done { background: #d4edda; padding: 5px 10px; border-radius: 5px; }
    .customer-pending { background: #fff3cd; padding: 5px 10px; border-radius: 5px; }
    .big-input textarea { font-size: 16px !important; }
</style>
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
    st.session_state.completed_customers = []

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

# 속지 타입 재정의
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
        menu_options.extend(["📦 서비스 작업", "📄 PDF 생성", "👤 MyPage", "📢 공지사항"])
        
        selected = st.radio("메뉴", menu_options, label_visibility="collapsed")
        
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.customers_df = None
            st.session_state.selected_customers = []
            st.session_state.completed_customers = []
            st.rerun()
    
    if selected == "⚙️ 관리자 설정":
        show_admin_settings()
    elif selected == "👥 회원 관리":
        show_user_management()
    elif selected == "📦 서비스 작업":
        show_service_work()
    elif selected == "📄 PDF 생성":
        show_pdf_generation()
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
        st.markdown("### API / 이메일 모드")
        
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
# 📦 서비스 작업 (통합!)
# ============================================

def show_service_work():
    st.title("📦 서비스 작업")
    
    # ===== 1. 서비스 선택 (최대 3개) =====
    st.markdown('<div class="section-header"><h3>1️⃣ 서비스 선택 (최대 3개)</h3></div>', unsafe_allow_html=True)
    
    services = get_all_services()
    default_services = ["사주", "타로", "연애"]
    
    # 기본 서비스가 없으면 자동 생성
    existing_names = [s['name'] for s in services]
    for svc in default_services:
        if svc not in existing_names:
            add_service(svc, f"{svc} 서비스")
    
    services = get_all_services()  # 다시 로드
    
    col1, col2, col3 = st.columns(3)
    selected_services = []
    
    for idx, svc in enumerate(services[:3]):  # 최대 3개
        with [col1, col2, col3][idx]:
            icon = ["🔮", "🃏", "💕"][idx] if idx < 3 else "📦"
            if st.checkbox(f"{icon} {svc['name']}", key=f"svc_sel_{svc['id']}"):
                selected_services.append(svc)
    
    if not selected_services:
        st.info("👆 서비스를 선택하세요")
        return
    
    st.success(f"✅ 선택된 서비스: {', '.join([s['name'] for s in selected_services])}")
    
    # ===== 2. 목차 / 지침 / 속지 관리 =====
    for svc in selected_services:
        st.markdown("---")
        st.markdown(f"### 📌 {svc['name']} 설정")
        
        tab1, tab2, tab3 = st.tabs([f"📑 목차", f"📜 지침", f"🖼️ 속지"])
        
        # ----- 목차 탭 -----
        with tab1:
            st.markdown("#### 목차 추가")
            
            col_a, col_b = st.columns([1, 2])
            with col_a:
                new_ch_title = st.text_input("목차 제목", key=f"ch_title_{svc['id']}", placeholder="예: 올해의 운세")
            with col_b:
                new_ch_desc = st.text_area("목차 설명 (선택)", key=f"ch_desc_{svc['id']}", 
                                          height=100, placeholder="이 목차에서 다룰 내용...")
            
            if st.button("➕ 목차 추가", key=f"add_ch_{svc['id']}"):
                if new_ch_title:
                    add_chapter(svc['id'], new_ch_title, new_ch_desc)
                    st.success(f"✅ '{new_ch_title}' 추가됨")
                    st.rerun()
            
            st.markdown("#### 저장된 목차")
            chapters = get_chapters_by_service(svc['id'])
            if not chapters:
                st.info("등록된 목차가 없습니다.")
            else:
                for ch in chapters:
                    with st.expander(f"{ch['order']}. {ch['title']}", expanded=False):
                        st.caption(ch.get('description', '') or '설명 없음')
                        if st.button("🗑️ 삭제", key=f"del_ch_{ch['id']}"):
                            delete_chapter(ch['id'])
                            st.rerun()
        
        # ----- 지침 탭 -----
        with tab2:
            st.markdown("#### 지침 추가")
            
            new_g_title = st.text_input("지침 제목", key=f"g_title_{svc['id']}", placeholder="예: 기본 작성 지침")
            new_g_content = st.text_area("지침 내용", key=f"g_content_{svc['id']}", 
                                        height=250, 
                                        placeholder="AI가 참고할 작성 지침을 상세히 입력하세요...")
            
            if st.button("➕ 지침 추가", key=f"add_g_{svc['id']}"):
                if new_g_title and new_g_content:
                    add_guideline(svc['id'], new_g_title, new_g_content)
                    st.success(f"✅ '{new_g_title}' 추가됨")
                    st.rerun()
            
            st.markdown("#### 저장된 지침")
            guidelines = get_guidelines_by_service(svc['id'])
            if not guidelines:
                st.info("등록된 지침이 없습니다.")
            else:
                for g in guidelines:
                    with st.expander(f"📜 {g['title']}", expanded=False):
                        st.text_area("내용", value=g['content'], height=200, 
                                    key=f"view_g_{g['id']}", disabled=True)
                        if st.button("🗑️ 삭제", key=f"del_g_{g['id']}"):
                            delete_guideline(g['id'])
                            st.rerun()
        
        # ----- 속지 탭 -----
        with tab3:
            st.markdown("#### 속지 업로드")
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                tmpl_type = st.selectbox("속지 종류", 
                    list(TEMPLATE_TYPES_NEW.keys()),
                    format_func=lambda x: TEMPLATE_TYPES_NEW[x],
                    key=f"tmpl_type_{svc['id']}")
            with col_t2:
                tmpl_name = st.text_input("속지 이름", key=f"tmpl_name_{svc['id']}", 
                                         placeholder="예: 기본 표지")
            
            tmpl_file = st.file_uploader("이미지 파일", type=["jpg", "jpeg", "png"],
                                        key=f"tmpl_file_{svc['id']}")
            
            if tmpl_file:
                st.image(tmpl_file, width=200, caption="미리보기")
            
            if st.button("➕ 속지 추가", key=f"add_tmpl_{svc['id']}"):
                if tmpl_name and tmpl_file:
                    img_path = save_uploaded_file(tmpl_file, f"{svc['name']}_{tmpl_type}")
                    add_template(svc['id'], tmpl_type, tmpl_name, img_path)
                    st.success(f"✅ '{tmpl_name}' 추가됨")
                    st.rerun()
            
            st.markdown("#### 저장된 속지")
            templates = get_templates_by_service(svc['id'])
            
            for ttype, tname in TEMPLATE_TYPES_NEW.items():
                type_templates = [t for t in templates if t['template_type'] == ttype]
                if type_templates:
                    st.markdown(f"**{tname}**")
                    cols = st.columns(4)
                    for idx, t in enumerate(type_templates):
                        with cols[idx % 4]:
                            if t['image_path'] and os.path.exists(t['image_path']):
                                st.image(t['image_path'], width=100)
                            st.caption(t['name'])
                            if st.button("🗑️", key=f"del_t_{t['id']}"):
                                delete_template(t['id'])
                                st.rerun()

# ============================================
# 📄 PDF 생성
# ============================================

def show_pdf_generation():
    st.title("📄 PDF 생성")
    
    # API 확인
    api_info = get_api_key()
    if not api_info["key"]:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        return
    
    st.success(f"✅ API: {api_info['source']}")
    
    # ===== 1. 서비스 선택 =====
    st.markdown('<div class="section-header"><h3>1️⃣ 서비스 선택</h3></div>', unsafe_allow_html=True)
    
    services = get_all_services()
    if not services:
        st.warning("서비스를 먼저 등록하세요.")
        return
    
    cols = st.columns(len(services))
    selected_service_ids = []
    
    for idx, svc in enumerate(services):
        with cols[idx]:
            icon = ["🔮", "🃏", "💕"][idx] if idx < 3 else "📦"
            if st.checkbox(f"{icon} {svc['name']}", key=f"pdf_svc_{svc['id']}"):
                selected_service_ids.append(svc['id'])
    
    if not selected_service_ids:
        st.info("서비스를 선택하세요")
        return
    
    # ===== 2. 목차 / 지침 / 속지 선택 =====
    st.markdown('<div class="section-header"><h3>2️⃣ 콘텐츠 선택</h3></div>', unsafe_allow_html=True)
    
    pdf_config = {}
    
    for sid in selected_service_ids:
        svc = get_service_by_id(sid)
        if not svc:
            continue
        
        with st.expander(f"📌 {svc['name']} 설정", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # 목차 선택
                chapters = get_chapters_by_service(sid)
                if chapters:
                    ch_options = [f"{c['order']}. {c['title']}" for c in chapters]
                    selected_chs = st.multiselect("📑 목차 선택", ch_options, 
                                                  default=ch_options, key=f"sel_ch_{sid}")
                else:
                    st.warning("등록된 목차 없음")
                    selected_chs = []
                
                # 지침 선택
                guidelines = get_guidelines_by_service(sid)
                if guidelines:
                    g_options = [g['title'] for g in guidelines]
                    selected_g = st.selectbox("📜 지침 선택", g_options, key=f"sel_g_{sid}")
                else:
                    st.warning("등록된 지침 없음")
                    selected_g = None
            
            with col2:
                # 속지 선택
                templates = get_templates_by_service(sid)
                
                cover_opts = [t['name'] for t in templates if t['template_type'] == 'cover']
                bg_opts = [t['name'] for t in templates if t['template_type'] == 'background']
                info_opts = [t['name'] for t in templates if t['template_type'] == 'info']
                
                sel_cover = st.selectbox("📕 표지", ["없음"] + cover_opts, key=f"sel_cover_{sid}")
                sel_bg = st.selectbox("📄 내지", ["없음"] + bg_opts, key=f"sel_bg_{sid}")
                sel_info = st.selectbox("📋 안내지", ["없음"] + info_opts, key=f"sel_info_{sid}")
            
            pdf_config[sid] = {
                "service_name": svc['name'],
                "chapters": selected_chs,
                "guideline": selected_g,
                "cover": sel_cover if sel_cover != "없음" else None,
                "background": sel_bg if sel_bg != "없음" else None,
                "info": sel_info if sel_info != "없음" else None
            }
    
    # ===== 3. 폰트 / 스타일 설정 =====
    st.markdown('<div class="section-header"><h3>3️⃣ 폰트 / 스타일 설정</h3></div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        font = st.selectbox("폰트", list(FONT_OPTIONS.keys()))
    with col2:
        font_size = st.number_input("글자 크기", 8, 30, 14)
    with col3:
        char_width = st.number_input("장평 (%)", 50, 150, 100)
    with col4:
        letter_spacing = st.number_input("자간", -5, 10, 0)
    with col5:
        line_height = st.number_input("행간", 10, 50, 24)
    
    font_settings = {
        "font": FONT_OPTIONS[font],
        "font_name": font,
        "size": font_size,
        "char_width": char_width,
        "letter_spacing": letter_spacing,
        "line_height": line_height
    }
    
    # ===== 4. 고객 파일 업로드 =====
    st.markdown('<div class="section-header"><h3>4️⃣ 고객 파일 업로드</h3></div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("엑셀 파일 (.xlsx, .xls)", type=["xlsx", "xls"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.session_state.customers_df = df
        st.success(f"✅ {len(df)}명 로드됨")
        
        # 컬럼 표시
        st.caption(f"컬럼: {', '.join(df.columns.tolist())}")
    
    # ===== 5. 고객 선택 =====
    if st.session_state.customers_df is not None:
        st.markdown('<div class="section-header"><h3>5️⃣ 고객 선택</h3></div>', unsafe_allow_html=True)
        
        df = st.session_state.customers_df
        
        # 이름 컬럼 찾기
        name_col = None
        for col in ['이름', 'name', 'Name', '성명', '고객명']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            name_col = df.columns[0]
        
        # 전체/선택 모드
        mode = st.radio("선택 모드", ["✅ 전체 선택", "🔘 개별 선택"], horizontal=True)
        
        if mode == "✅ 전체 선택":
            st.session_state.selected_customers = list(range(len(df)))
            st.info(f"전체 {len(df)}명 선택됨")
        else:
            # 개별 선택
            cols = st.columns(5)
            selected = []
            
            for idx, row in df.iterrows():
                col_idx = idx % 5
                with cols[col_idx]:
                    # 완료 여부 표시
                    is_done = idx in st.session_state.completed_customers
                    status = "✅" if is_done else "⏳"
                    
                    if st.checkbox(f"{status} {row[name_col]}", key=f"cust_{idx}", 
                                  value=(idx in st.session_state.selected_customers)):
                        selected.append(idx)
            
            st.session_state.selected_customers = selected
            st.info(f"{len(selected)}명 선택됨")
        
        # ===== 6. PDF 변환 =====
        st.markdown('<div class="section-header"><h3>6️⃣ PDF 변환</h3></div>', unsafe_allow_html=True)
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🚀 PDF 변환 시작", type="primary", use_container_width=True):
                if not st.session_state.selected_customers:
                    st.error("고객을 선택하세요")
                else:
                    # 진행 표시
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    total = len(st.session_state.selected_customers)
                    
                    for i, cust_idx in enumerate(st.session_state.selected_customers):
                        row = df.iloc[cust_idx]
                        cust_name = row[name_col]
                        
                        status_text.text(f"📝 {cust_name} 처리 중... ({i+1}/{total})")
                        progress_bar.progress((i + 1) / total)
                        
                        # TODO: 실제 PDF 생성 로직
                        import time
                        time.sleep(0.5)  # 시뮬레이션
                        
                        # 완료 표시
                        if cust_idx not in st.session_state.completed_customers:
                            st.session_state.completed_customers.append(cust_idx)
                    
                    status_text.text("✅ 모든 PDF 변환 완료!")
                    st.balloons()
        
        with col_btn2:
            if st.button("🔄 완료 초기화", use_container_width=True):
                st.session_state.completed_customers = []
                st.rerun()
        
        # 완료 현황
        done_count = len(st.session_state.completed_customers)
        total_count = len(df)
        st.markdown(f"**완료 현황:** {done_count} / {total_count} ({done_count/total_count*100:.0f}%)")
        
        # 진행 바
        st.progress(done_count / total_count if total_count > 0 else 0)

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
# 공지사항
# ============================================

def show_notices():
    st.title("📢 공지사항")
    
    notices = get_all_notices()
    if not notices:
        st.info("등록된 공지사항이 없습니다.")
    else:
        for n in notices:
            pin = "📌 " if n['is_pinned'] else ""
            with st.expander(f"{pin}{n['title']} ({n['created_at']})"):
                st.write(n['content'])

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
