# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
Streamlit Cloud 버전 - API/이메일 분리 모드
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 페이지 설정 (맨 처음에!)
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
    get_all_users, get_pending_users, approve_user, suspend_user, ban_user,
    update_user_role, create_first_admin, check_admin_exists
)
from services import (
    get_all_services, get_service_by_id, add_service, delete_service,
    get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, delete_chapter,
    get_guidelines_by_service, add_guideline, delete_guideline,
    get_templates_by_service, add_template, delete_template,
    TEMPLATE_TYPES
)
from notices import get_all_notices, get_notice_by_id, create_notice, delete_notice, get_recent_notices

# ============================================
# 추가 ConfigKeys (services.py에 없으면 여기서 정의)
# ============================================

# API/이메일 모드 키
API_MODE_KEY = "api_mode"  # "unified" or "separated"
EMAIL_MODE_KEY = "email_mode"  # "unified" or "separated"

# ============================================
# CSS
# ============================================

st.markdown("""
<style>
    .main-title { text-align: center; color: #fff; font-size: 2.5rem; margin-bottom: 10px; }
    .sub-title { text-align: center; color: #888; font-size: 1rem; margin-bottom: 30px; }
    .role-badge { padding: 3px 10px; border-radius: 10px; font-size: 0.8rem; }
    .role-1 { background: #6c757d; color: #fff; }
    .role-2 { background: #17a2b8; color: #fff; }
    .role-3 { background: #dc3545; color: #fff; }
    .mode-box { background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; margin: 10px 0; }
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
    """
    API 키 가져오기 (모드에 따라)
    Returns: {"key": "...", "source": "관리자"/"개인", "mode": "unified"/"separated"}
    """
    user = st.session_state.user
    api_mode = get_system_config(API_MODE_KEY, "unified")
    
    admin_api = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
    user_api = user.get('api_key', '') or ''
    
    if api_mode == "unified":
        # 통일 모드: 관리자 API만 사용
        return {"key": admin_api, "source": "관리자", "mode": "unified"}
    else:
        # 분리 모드: 개인 API 우선, 없으면 관리자
        if user_api:
            return {"key": user_api, "source": "개인", "mode": "separated"}
        else:
            return {"key": admin_api, "source": "관리자 (개인 미설정)", "mode": "separated"}

def get_email_config() -> dict:
    """
    이메일 설정 가져오기 (모드에 따라)
    Returns: {"email": "...", "password": "...", "source": "관리자"/"개인", "mode": "..."}
    """
    user = st.session_state.user
    email_mode = get_system_config(EMAIL_MODE_KEY, "unified")
    
    admin_gmail = get_system_config(ConfigKeys.ADMIN_GMAIL, "")
    admin_gmail_pw = get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, "")
    
    user_gmail = user.get('gmail_address', '') or ''
    user_gmail_pw = user.get('gmail_app_password', '') or ''
    
    if email_mode == "unified":
        # 통일 모드: 관리자 이메일만 사용
        if admin_gmail and admin_gmail_pw:
            return {"email": admin_gmail, "password": admin_gmail_pw, "source": "관리자", "mode": "unified"}
        return None
    else:
        # 분리 모드: 개인 이메일 우선, 없으면 관리자
        if user_gmail and user_gmail_pw:
            return {"email": user_gmail, "password": user_gmail_pw, "source": "개인", "mode": "separated"}
        elif admin_gmail and admin_gmail_pw:
            return {"email": admin_gmail, "password": admin_gmail_pw, "source": "관리자 (개인 미설정)", "mode": "separated"}
        return None

# ============================================
# 로그인 페이지
# ============================================

def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<h1 class="main-title">🔮 PDF 자동 생성 플랫폼</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">사주 · 타로 · 연애</p>', unsafe_allow_html=True)
        
        # 관리자 생성 성공 메시지
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
                else:
                    st.error("이메일과 비밀번호를 입력해주세요.")
        
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
                else:
                    st.error("모든 필드를 입력해주세요.")
        
        st.markdown("---")
        
        # 최초 관리자 설정
        if not check_admin_exists():
            with st.expander("🔧 최초 관리자 설정", expanded=True):
                st.warning("⚠️ 아직 관리자가 없습니다. 관리자 계정을 먼저 생성하세요!")
                
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
                    else:
                        st.error("모든 필드를 입력해주세요.")

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
            menu_options.extend(["⚙️ 관리자 설정", "👥 회원 관리", "📦 서비스 관리"])
        if user["role"] >= 1:
            menu_options.append("📋 목차/지침/속지")
        menu_options.extend(["📄 PDF 생성", "👤 MyPage", "📢 공지사항"])
        
        selected = st.radio("메뉴", menu_options, label_visibility="collapsed")
        
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()
    
    # 페이지 라우팅
    if selected == "⚙️ 관리자 설정":
        show_admin_settings()
    elif selected == "👥 회원 관리":
        show_user_management()
    elif selected == "📦 서비스 관리":
        show_service_management()
    elif selected == "📋 목차/지침/속지":
        show_content_management()
    elif selected == "📄 PDF 생성":
        show_pdf_generation()
    elif selected == "👤 MyPage":
        show_mypage()
    elif selected == "📢 공지사항":
        show_notices()

# ============================================
# 관리자 설정 (분리/통일 모드 추가!)
# ============================================

def show_admin_settings():
    st.title("⚙️ 관리자 설정")
    
    tab1, tab2, tab3 = st.tabs(["🔑 API 설정", "📧 이메일 설정", "⚡ 모드 설정"])
    
    # ===== API 설정 =====
    with tab1:
        st.markdown("### 🔑 관리자 OpenAI API")
        api = st.text_input("API 키", value=get_system_config(ConfigKeys.ADMIN_API_KEY, ""), type="password")
        
        if st.button("💾 API 키 저장", key="save_api"):
            set_system_config(ConfigKeys.ADMIN_API_KEY, api)
            st.success("✅ 저장됨")
        
        st.markdown("---")
        st.info("""
        **API 키 발급 방법:**
        1. https://platform.openai.com 접속
        2. 로그인 → API Keys
        3. Create new secret key
        """)
    
    # ===== 이메일 설정 =====
    with tab2:
        st.markdown("### 📧 관리자 Gmail")
        gmail = st.text_input("Gmail 주소", value=get_system_config(ConfigKeys.ADMIN_GMAIL, ""))
        gmail_pw = st.text_input("Gmail 앱 비밀번호", value=get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, ""), type="password")
        
        if st.button("💾 이메일 저장", key="save_email"):
            set_system_config(ConfigKeys.ADMIN_GMAIL, gmail)
            set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, gmail_pw)
            st.success("✅ 저장됨")
        
        st.markdown("---")
        with st.expander("📌 Gmail 앱 비밀번호 발급 방법"):
            st.markdown("""
            1. Google 계정 → **보안** → **2단계 인증** 활성화
            2. https://myaccount.google.com/apppasswords 접속
            3. **앱 선택** → 기타 → 이름 입력 (예: PDF플랫폼)
            4. **생성** 클릭 → 16자리 비밀번호 복사
            """)
    
    # ===== 모드 설정 (핵심!) =====
    with tab3:
        st.markdown("### ⚡ API / 이메일 사용 모드")
        
        st.markdown("---")
        
        # API 모드
        st.markdown("#### 🔑 API 모드")
        current_api_mode = get_system_config(API_MODE_KEY, "unified")
        
        api_mode = st.radio(
            "API 사용 방식",
            ["unified", "separated"],
            index=0 if current_api_mode == "unified" else 1,
            format_func=lambda x: "🔒 통일 (관리자 API만 사용)" if x == "unified" else "🔓 분리 (직원 각자 API 사용)",
            key="api_mode_radio"
        )
        
        if api_mode == "unified":
            st.info("✅ **통일 모드**: 모든 직원이 관리자 API를 사용합니다.")
        else:
            st.warning("⚠️ **분리 모드**: 직원은 MyPage에서 개인 API를 등록해야 합니다. (미등록 시 관리자 API 사용)")
        
        st.markdown("---")
        
        # 이메일 모드
        st.markdown("#### 📧 이메일 모드")
        current_email_mode = get_system_config(EMAIL_MODE_KEY, "unified")
        
        email_mode = st.radio(
            "이메일 사용 방식",
            ["unified", "separated"],
            index=0 if current_email_mode == "unified" else 1,
            format_func=lambda x: "🔒 통일 (관리자 이메일만 사용)" if x == "unified" else "🔓 분리 (직원 각자 이메일 사용)",
            key="email_mode_radio"
        )
        
        if email_mode == "unified":
            st.info("✅ **통일 모드**: 모든 발송이 관리자 이메일로 전송됩니다.")
        else:
            st.warning("⚠️ **분리 모드**: 직원은 MyPage에서 개인 Gmail을 등록해야 합니다. (미등록 시 관리자 이메일 사용)")
        
        st.markdown("---")
        
        if st.button("💾 모드 설정 저장", type="primary", use_container_width=True):
            set_system_config(API_MODE_KEY, api_mode)
            set_system_config(EMAIL_MODE_KEY, email_mode)
            st.success("✅ 모드 설정이 저장되었습니다!")
            st.rerun()

# ============================================
# 회원 관리
# ============================================

def show_user_management():
    st.title("👥 회원 관리")
    
    tab1, tab2 = st.tabs(["전체", "대기"])
    
    with tab1:
        users = get_all_users()
        if not users:
            st.info("등록된 회원이 없습니다.")
        for u in users:
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(f"**{u['name']}** ({u['email']})")
            col2.write(f"등급: {u['role']}단계 | 상태: {u['status']}")
            if u['id'] != st.session_state.user['id']:
                if col3.button("정지", key=f"sus_{u['id']}"):
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
# 서비스 관리
# ============================================

def show_service_management():
    st.title("📦 서비스 관리")
    
    tab1, tab2 = st.tabs(["목록", "추가"])
    
    with tab1:
        services = get_all_services()
        if not services:
            st.info("등록된 서비스가 없습니다.")
        for s in services:
            col1, col2 = st.columns([5, 1])
            col1.write(f"**{s['name']}** - {s.get('description', '')}")
            if col2.button("🗑️", key=f"ds_{s['id']}"):
                delete_service(s['id'])
                st.rerun()
    
    with tab2:
        name = st.text_input("서비스 이름")
        desc = st.text_area("설명")
        if st.button("추가", type="primary") and name:
            add_service(name, desc)
            st.rerun()

# ============================================
# 목차/지침/속지
# ============================================

def show_content_management():
    st.title("📋 목차/지침/속지")
    
    services = get_all_services()
    if not services:
        st.warning("서비스를 먼저 등록하세요.")
        return
    
    sel = st.selectbox("서비스", [s['name'] for s in services])
    sid = next((s['id'] for s in services if s['name'] == sel), None)
    
    tab1, tab2, tab3 = st.tabs(["목차", "지침", "속지"])
    
    with tab1:
        new_ch = st.text_input("새 목차")
        if st.button("추가", key="add_ch") and new_ch:
            add_chapter(sid, new_ch)
            st.rerun()
        for c in get_chapters_by_service(sid):
            col1, col2 = st.columns([5, 1])
            col1.write(f"{c['order']}. {c['title']}")
            if col2.button("🗑️", key=f"dc_{c['id']}"):
                delete_chapter(c['id'])
                st.rerun()
    
    with tab2:
        new_gt = st.text_input("지침 제목")
        new_gc = st.text_area("지침 내용")
        if st.button("추가", key="add_g") and new_gt:
            add_guideline(sid, new_gt, new_gc)
            st.rerun()
        for g in get_guidelines_by_service(sid):
            with st.expander(g['title']):
                st.write(g['content'][:200])
                if st.button("삭제", key=f"dg_{g['id']}"):
                    delete_guideline(g['id'])
                    st.rerun()
    
    with tab3:
        tt = st.selectbox("유형", list(TEMPLATE_TYPES.keys()), format_func=lambda x: TEMPLATE_TYPES[x])
        tn = st.text_input("이름")
        tf = st.file_uploader("이미지", type=["jpg", "png"])
        if st.button("추가", key="add_t") and tn:
            ip = save_uploaded_file(tf, f"{sel}_{tt}") if tf else None
            add_template(sid, tt, tn, ip)
            st.rerun()
        for t in get_templates_by_service(sid):
            col1, col2 = st.columns([5, 1])
            col1.write(f"{TEMPLATE_TYPES[t['template_type']]}: {t['name']}")
            if col2.button("🗑️", key=f"dt_{t['id']}"):
                delete_template(t['id'])
                st.rerun()

# ============================================
# PDF 생성
# ============================================

def show_pdf_generation():
    st.title("📄 PDF 생성")
    
    # API 상태 표시
    api_info = get_api_key()
    if not api_info["key"]:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        if api_info["mode"] == "separated":
            st.info("💡 MyPage에서 개인 API 키를 등록하거나, 관리자에게 문의하세요.")
        else:
            st.info("💡 관리자 설정에서 API 키를 등록해주세요.")
        return
    
    st.success(f"✅ API: {api_info['source']} 사용 중")
    
    # 이메일 상태 표시
    email_info = get_email_config()
    if email_info:
        st.success(f"✅ 이메일: {email_info['source']} ({email_info['email']})")
    else:
        st.warning("⚠️ 이메일 미설정 - 발송 기능 사용 불가")
    
    st.markdown("---")
    
    services = get_all_services()
    if not services:
        st.warning("서비스를 먼저 등록하세요.")
        return
    
    # 서비스 선택
    st.markdown("### 1. 서비스 선택")
    sel_ids = []
    cols = st.columns(len(services))
    for i, s in enumerate(services):
        if cols[i].checkbox(s['name'], key=f"sv_{s['id']}"):
            sel_ids.append(s['id'])
    
    if not sel_ids:
        st.info("서비스를 선택하세요.")
        return
    
    # 문서 설정
    st.markdown("### 2. 문서 설정")
    c1, c2 = st.columns(2)
    font_size = c1.number_input("글자 크기", 10, 24, 14)
    line_height = c2.number_input("줄 간격", 15, 50, 24)
    
    # 고객 파일
    st.markdown("### 3. 고객 파일")
    file = st.file_uploader("엑셀 업로드", type=["xlsx", "xls"])
    if file:
        df = pd.read_excel(file)
        st.session_state.customers_df = df
        st.success(f"✅ {len(df)}명 로드됨")
        st.dataframe(df.head())
    
    # 생성
    if st.session_state.customers_df is not None:
        st.markdown("### 4. 생성")
        if st.button("🚀 PDF 생성", type="primary", use_container_width=True):
            st.info("🚧 PDF 생성 기능 - 곧 구현됩니다!")

# ============================================
# MyPage (개인 API/이메일 설정 추가!)
# ============================================

def show_mypage():
    st.title("👤 MyPage")
    user = st.session_state.user
    
    tab1, tab2, tab3 = st.tabs(["📋 내 정보", "🔑 API 설정", "📧 이메일 설정"])
    
    # ===== 내 정보 =====
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 기본 정보")
            new_name = st.text_input("이름", value=user['name'])
            st.text_input("이메일", value=user['email'], disabled=True)
            role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
            st.info(f"등급: {role_text.get(user['role'], user['role'])}")
            
            if st.button("💾 이름 저장"):
                result = update_user_profile(user['id'], name=new_name)
                if result["success"]:
                    st.session_state.user['name'] = new_name
                    st.success("저장됨")
        
        with col2:
            st.markdown("### 비밀번호 변경")
            old_pw = st.text_input("현재 비밀번호", type="password")
            new_pw = st.text_input("새 비밀번호", type="password")
            new_pw2 = st.text_input("새 비밀번호 확인", type="password")
            
            if st.button("🔒 비밀번호 변경"):
                if old_pw and new_pw:
                    if new_pw != new_pw2:
                        st.error("새 비밀번호가 일치하지 않습니다.")
                    else:
                        result = change_password(user['id'], old_pw, new_pw)
                        if result["success"]:
                            st.success("변경됨")
                        else:
                            st.error(result["error"])
    
    # ===== API 설정 =====
    with tab2:
        st.markdown("### 🔑 개인 OpenAI API 설정")
        
        # 현재 모드 표시
        api_mode = get_system_config(API_MODE_KEY, "unified")
        if api_mode == "unified":
            st.info("🔒 **현재 통일 모드**: 관리자 API가 자동으로 사용됩니다.")
            st.caption("개인 API를 사용하려면 관리자에게 '분리 모드' 설정을 요청하세요.")
        else:
            st.warning("🔓 **현재 분리 모드**: 개인 API를 등록하세요. (미등록 시 관리자 API 사용)")
        
        st.markdown("---")
        
        my_api = st.text_input("내 OpenAI API 키", value=user.get('api_key', '') or '', type="password")
        
        if st.button("💾 API 키 저장", key="save_my_api"):
            result = update_user_profile(user['id'], api_key=my_api)
            if result["success"]:
                st.session_state.user['api_key'] = my_api
                st.success("✅ 저장됨")
        
        # 현재 사용 중인 API 표시
        st.markdown("---")
        api_info = get_api_key()
        st.markdown(f"**현재 사용 API:** {api_info['source']}")
    
    # ===== 이메일 설정 =====
    with tab3:
        st.markdown("### 📧 개인 Gmail 설정")
        
        # 현재 모드 표시
        email_mode = get_system_config(EMAIL_MODE_KEY, "unified")
        if email_mode == "unified":
            st.info("🔒 **현재 통일 모드**: 관리자 이메일로 발송됩니다.")
            st.caption("개인 이메일을 사용하려면 관리자에게 '분리 모드' 설정을 요청하세요.")
        else:
            st.warning("🔓 **현재 분리 모드**: 개인 Gmail을 등록하세요. (미등록 시 관리자 이메일 사용)")
        
        st.markdown("---")
        
        my_gmail = st.text_input("내 Gmail 주소", value=user.get('gmail_address', '') or '')
        my_gmail_pw = st.text_input("내 Gmail 앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
        
        with st.expander("📌 Gmail 앱 비밀번호 발급 방법"):
            st.markdown("""
            1. Google 계정 → 보안 → 2단계 인증 활성화
            2. https://myaccount.google.com/apppasswords
            3. 앱 이름 입력 → 생성 → 16자리 복사
            """)
        
        if st.button("💾 이메일 저장", key="save_my_email"):
            result = update_user_profile(user['id'], gmail_address=my_gmail, gmail_app_password=my_gmail_pw)
            if result["success"]:
                st.session_state.user['gmail_address'] = my_gmail
                st.session_state.user['gmail_app_password'] = my_gmail_pw
                st.success("✅ 저장됨")
        
        # 현재 사용 중인 이메일 표시
        st.markdown("---")
        email_info = get_email_config()
        if email_info:
            st.markdown(f"**현재 발송 이메일:** {email_info['source']} ({email_info['email']})")
        else:
            st.markdown("**현재 발송 이메일:** 미설정")

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
