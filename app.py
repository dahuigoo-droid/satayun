# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
5단계: 이메일 + 카톡 발송
"""

import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from database import init_db, SessionLocal, UserRole
from auth import (
    register_user, login_user, update_user_profile, change_password,
    get_all_users, get_pending_users, approve_user, suspend_user, ban_user,
    update_user_role, update_user_api_limit, reset_user_api_usage,
    create_first_admin, check_admin_exists
)
from services import (
    get_all_services, get_service_by_id, add_service, update_service,
    delete_service, restore_service,
    get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, update_chapter, delete_chapter,
    get_guidelines_by_service, get_guideline_by_id, add_guideline, update_guideline, delete_guideline,
    get_templates_by_service, add_template, delete_template,
    TEMPLATE_TYPES
)
from pdf_generator import generate_combined_pdf
from notification import send_email_with_pdf, send_bulk_emails

# ============================================
# 페이지 설정
# ============================================

st.set_page_config(
    page_title="PDF 자동 생성 플랫폼",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# 디렉토리 설정
# ============================================

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ============================================
# CSS
# ============================================

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); }
    .main-title { text-align: center; color: #fff; font-size: 2.5rem; margin-bottom: 10px; }
    .sub-title { text-align: center; color: #888; font-size: 1rem; margin-bottom: 30px; }
    .role-badge { padding: 3px 10px; border-radius: 10px; font-size: 0.8rem; display: inline-block; }
    .role-1 { background: #6c757d; color: #fff; }
    .role-2 { background: #17a2b8; color: #fff; }
    .role-3 { background: #dc3545; color: #fff; }
    .success-box { background: #d4edda; padding: 10px; border-radius: 5px; margin: 5px 0; }
    .fail-box { background: #f8d7da; padding: 10px; border-radius: 5px; margin: 5px 0; }
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
if 'generated_pdfs' not in st.session_state:
    st.session_state.generated_pdfs = []

# ============================================
# DB 초기화
# ============================================

@st.cache_resource
def initialize_database():
    init_db()
    return True

initialize_database()

# ============================================
# 유틸리티 함수
# ============================================

def check_permission(required_role: int) -> bool:
    if not st.session_state.user:
        return False
    return st.session_state.user.get('role', 0) >= required_role

def require_permission(required_role: int):
    if not check_permission(required_role):
        st.error(f"⛔ 권한이 부족합니다.")
        return False
    return True

def save_uploaded_file(uploaded_file, service_name: str, file_type: str) -> str:
    if uploaded_file is None:
        return None
    filename = f"{service_name}_{file_type}_{uploaded_file.name}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filepath

def get_api_key() -> str:
    user = st.session_state.user
    if user.get('use_admin_api', True):
        return get_system_config(ConfigKeys.ADMIN_API_KEY, "")
    return user.get('api_key', "")

def get_email_config() -> dict:
    """이메일 설정 가져오기 (개인 우선, 없으면 관리자)"""
    user = st.session_state.user
    
    # 개인 Gmail 설정 확인
    user_gmail = user.get('gmail_address', '')
    user_gmail_pw = user.get('gmail_app_password', '')
    
    if user_gmail and user_gmail_pw:
        return {"email": user_gmail, "password": user_gmail_pw, "source": "개인"}
    
    # 관리자 Gmail 설정
    admin_gmail = get_system_config(ConfigKeys.ADMIN_GMAIL, "")
    admin_gmail_pw = get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, "")
    
    if admin_gmail and admin_gmail_pw:
        return {"email": admin_gmail, "password": admin_gmail_pw, "source": "관리자"}
    
    return None

# ============================================
# 로그인 페이지
# ============================================

def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<h1 class="main-title">🔮 PDF 자동 생성 플랫폼</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">사주 · 타로 · 연애</p>', unsafe_allow_html=True)
        
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
        
        st.markdown("---")
        
        if not check_admin_exists():
            with st.expander("🔧 최초 관리자 설정"):
                admin_name = st.text_input("관리자 이름", key="admin_name")
                admin_email = st.text_input("관리자 이메일", key="admin_email")
                admin_password = st.text_input("관리자 비밀번호", type="password", key="admin_password")
                
                if st.button("관리자 계정 생성"):
                    if all([admin_name, admin_email, admin_password]):
                        result = create_first_admin(admin_email, admin_password, admin_name)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()

# ============================================
# 메인 앱
# ============================================

def show_main_app():
    user = st.session_state.user
    
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}님")
        role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
        role_color = {1: "role-1", 2: "role-2", 3: "role-3"}
        st.markdown(f'<span class="role-badge {role_color[user["role"]]}">{role_text[user["role"]]}</span>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        menu_options = []
        if user["role"] == 3:
            menu_options.extend(["⚙️ 관리자 설정", "👥 회원 관리", "📦 서비스 관리"])
        if user["role"] >= 1:
            menu_options.append("📋 목차/지침/속지 관리")
        menu_options.extend(["📄 PDF 생성", "👤 MyPage"])
        if user["role"] >= 2:
            menu_options.append("✏️ 공지 작성")
        menu_options.append("📢 공지사항")
        
        selected_menu = st.radio("메뉴", menu_options, label_visibility="collapsed")
        
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.customers_df = None
            st.session_state.generated_pdfs = []
            st.rerun()
    
    if selected_menu == "⚙️ 관리자 설정":
        show_admin_settings()
    elif selected_menu == "👥 회원 관리":
        show_user_management()
    elif selected_menu == "📦 서비스 관리":
        show_service_management()
    elif selected_menu == "📋 목차/지침/속지 관리":
        show_content_management()
    elif selected_menu == "📄 PDF 생성":
        show_pdf_generation()
    elif selected_menu == "👤 MyPage":
        show_mypage()
    elif selected_menu == "✏️ 공지 작성":
        show_notice_write()
    elif selected_menu == "📢 공지사항":
        show_notices()

# ============================================
# 관리자 설정
# ============================================

def show_admin_settings():
    st.title("⚙️ 관리자 설정")
    if not require_permission(3):
        return
    
    tab1, tab2, tab3 = st.tabs(["🔑 API 설정", "📧 이메일 설정", "💬 카카오 설정"])
    
    with tab1:
        current_api_key = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
        admin_api_key = st.text_input("OpenAI API 키", value=current_api_key, type="password")
        current_limit = get_system_config(ConfigKeys.DEFAULT_API_LIMIT, "100")
        default_limit = st.number_input("기본 API 한도", min_value=10, max_value=10000, value=int(current_limit))
        
        if st.button("API 설정 저장", type="primary"):
            set_system_config(ConfigKeys.ADMIN_API_KEY, admin_api_key)
            set_system_config(ConfigKeys.DEFAULT_API_LIMIT, str(default_limit))
            st.success("✅ 저장되었습니다.")
    
    with tab2:
        st.markdown("### 📧 관리자 이메일 설정")
        st.info("회원 개인 Gmail이 없을 때 사용되는 기본 발송 이메일입니다.")
        
        current_gmail = get_system_config(ConfigKeys.ADMIN_GMAIL, "")
        current_gmail_pw = get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, "")
        admin_gmail = st.text_input("Gmail 주소", value=current_gmail)
        admin_gmail_pw = st.text_input("Gmail 앱 비밀번호", value=current_gmail_pw, type="password")
        
        with st.expander("📌 Gmail 앱 비밀번호 발급 방법"):
            st.markdown("""
            1. Google 계정 → **보안** → **2단계 인증** 활성화
            2. https://myaccount.google.com/apppasswords 접속
            3. **앱 선택** → 기타 → 이름 입력 (예: PDF플랫폼)
            4. **생성** 클릭 → 16자리 비밀번호 복사
            5. 위 입력란에 붙여넣기 (띄어쓰기 없이)
            """)
        
        if st.button("이메일 설정 저장", type="primary"):
            set_system_config(ConfigKeys.ADMIN_GMAIL, admin_gmail)
            set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, admin_gmail_pw)
            st.success("✅ 저장되었습니다.")
        
        # 테스트 발송
        st.markdown("---")
        st.markdown("### 🧪 테스트 발송")
        test_email = st.text_input("테스트 수신 이메일")
        if st.button("테스트 이메일 발송"):
            if admin_gmail and admin_gmail_pw and test_email:
                from notification import send_email
                result = send_email(
                    sender_email=admin_gmail,
                    sender_password=admin_gmail_pw,
                    recipient_email=test_email,
                    subject="[테스트] PDF 플랫폼 이메일 테스트",
                    body="<h2>테스트 성공!</h2><p>이메일 설정이 정상적으로 완료되었습니다.</p>"
                )
                if result["success"]:
                    st.success(f"✅ {result['message']}")
                else:
                    st.error(f"❌ {result['message']}")
            else:
                st.error("Gmail 설정과 테스트 이메일 주소를 모두 입력해주세요.")
    
    with tab3:
        st.markdown("### 💬 카카오 알림톡 설정")
        st.warning("⚠️ 카카오 비즈니스 채널 가입 후 사용 가능합니다.")
        
        current_kakao = get_system_config(ConfigKeys.KAKAO_CHANNEL_ID, "")
        kakao_channel = st.text_input("카카오 채널 ID", value=current_kakao)
        
        with st.expander("📌 카카오 비즈니스 채널 설정 방법"):
            st.markdown("""
            1. https://business.kakao.com 접속
            2. **카카오톡 채널** 만들기
            3. **비즈메시지** 신청
            4. **알림톡 템플릿** 등록 및 승인 대기
            5. 승인 후 API 연동
            
            ⚠️ 현재 카카오 알림톡은 준비 중입니다.
            """)
        
        if st.button("카카오 설정 저장", type="primary"):
            set_system_config(ConfigKeys.KAKAO_CHANNEL_ID, kakao_channel)
            st.success("✅ 저장되었습니다.")

# ============================================
# 서비스 관리
# ============================================

def show_service_management():
    st.title("📦 서비스 관리")
    if not require_permission(3):
        return
    
    tab1, tab2 = st.tabs(["📋 서비스 목록", "➕ 서비스 추가"])
    
    with tab1:
        services = get_all_services(include_inactive=True)
        for service in services:
            if service['is_active']:
                col1, col2, col3 = st.columns([3, 5, 1])
                with col1:
                    st.write(f"**{service['name']}**")
                with col2:
                    st.caption(service['description'] or "-")
                with col3:
                    if st.button("🗑️", key=f"del_{service['id']}"):
                        delete_service(service['id'])
                        st.rerun()
                st.markdown("---")
    
    with tab2:
        new_name = st.text_input("서비스 이름")
        new_desc = st.text_area("설명")
        if st.button("추가", type="primary"):
            if new_name:
                add_service(new_name, new_desc)
                st.rerun()

# ============================================
# 회원 관리
# ============================================

def show_user_management():
    st.title("👥 회원 관리")
    if not require_permission(3):
        return
    
    tab1, tab2 = st.tabs(["📋 전체 회원", "⏳ 승인 대기"])
    
    with tab1:
        users = get_all_users()
        for user in users:
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.write(f"**{user['name']}** ({user['email']})")
            with col2:
                status_text = {"pending": "⏳대기", "approved": "✅승인", "suspended": "⛔중지"}
                st.write(status_text.get(user['status'], user['status']))
            with col3:
                if user['id'] != st.session_state.user['id'] and user['status'] == "approved":
                    if st.button("중지", key=f"sus_{user['id']}"):
                        suspend_user(user['id'])
                        st.rerun()
            st.markdown("---")
    
    with tab2:
        pending = get_pending_users()
        if not pending:
            st.success("대기 중인 회원이 없습니다.")
        for user in pending:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{user['name']}** ({user['email']})")
            with col2:
                if st.button("승인", key=f"apr_{user['id']}", type="primary"):
                    approve_user(user['id'])
                    st.rerun()

# ============================================
# 목차/지침/속지 관리
# ============================================

def show_content_management():
    st.title("📋 목차/지침/속지 관리")
    if not require_permission(1):
        return
    
    services = get_all_services()
    if not services:
        st.warning("등록된 서비스가 없습니다.")
        return
    
    service_names = [s['name'] for s in services]
    selected_name = st.selectbox("서비스 선택", service_names)
    
    service_id = None
    for s in services:
        if s['name'] == selected_name:
            service_id = s['id']
            break
    
    if not service_id:
        return
    
    tab1, tab2, tab3 = st.tabs(["📑 목차", "📜 지침", "🖼️ 속지"])
    
    with tab1:
        with st.expander("➕ 목차 추가"):
            new_title = st.text_input("목차 제목", key="new_ch_title")
            if st.button("추가", key="add_ch"):
                if new_title:
                    add_chapter(service_id, new_title)
                    st.rerun()
        
        chapters = get_chapters_by_service(service_id)
        for ch in chapters:
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"{ch['order']}. {ch['title']}")
            with col2:
                if st.button("🗑️", key=f"del_ch_{ch['id']}"):
                    delete_chapter(ch['id'])
                    st.rerun()
    
    with tab2:
        with st.expander("➕ 지침 추가"):
            new_g_title = st.text_input("지침 제목", key="new_g_title")
            new_g_content = st.text_area("지침 내용", key="new_g_content", height=200)
            if st.button("추가", key="add_g"):
                if new_g_title and new_g_content:
                    add_guideline(service_id, new_g_title, new_g_content)
                    st.rerun()
        
        guidelines = get_guidelines_by_service(service_id)
        for g in guidelines:
            with st.expander(f"📜 {g['title']}"):
                st.text_area("내용", value=g['content'], height=150, key=f"g_{g['id']}", disabled=True)
                if st.button("삭제", key=f"del_g_{g['id']}"):
                    delete_guideline(g['id'])
                    st.rerun()
    
    with tab3:
        with st.expander("➕ 속지 추가"):
            tmpl_type = st.selectbox("유형", list(TEMPLATE_TYPES.keys()), format_func=lambda x: TEMPLATE_TYPES[x])
            tmpl_name = st.text_input("이름", key="new_tmpl_name")
            tmpl_file = st.file_uploader("이미지", type=["jpg", "png"], key="new_tmpl_file")
            if st.button("추가", key="add_tmpl"):
                if tmpl_name:
                    img_path = save_uploaded_file(tmpl_file, selected_name, tmpl_type) if tmpl_file else None
                    add_template(service_id, tmpl_type, tmpl_name, img_path)
                    st.rerun()
        
        templates = get_templates_by_service(service_id)
        for t in templates:
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                st.write(TEMPLATE_TYPES.get(t['template_type'], t['template_type']))
            with col2:
                st.write(t['name'])
            with col3:
                if st.button("🗑️", key=f"del_t_{t['id']}"):
                    delete_template(t['id'])
                    st.rerun()

# ============================================
# PDF 생성 (5단계: 발송 기능 추가!)
# ============================================

def show_pdf_generation():
    st.title("📄 PDF 생성")
    
    # API 키 확인
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        return
    
    services = get_all_services()
    if not services:
        st.warning("등록된 서비스가 없습니다.")
        return
    
    # ========== 1. 서비스 선택 ==========
    st.markdown("### 📌 1. 서비스 선택")
    
    selected_service_ids = []
    cols = st.columns(len(services))
    for idx, service in enumerate(services):
        with cols[idx]:
            if st.checkbox(service['name'], key=f"svc_{service['id']}"):
                selected_service_ids.append(service['id'])
    
    if not selected_service_ids:
        st.info("서비스를 선택해주세요.")
        return
    
    # ========== 2. 문서 설정 ==========
    st.markdown("---")
    st.markdown("### 🔤 2. 문서 설정")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        font = st.selectbox("폰트", ["나눔고딕", "나눔명조"])
    with col2:
        font_size = st.number_input("크기", 10, 24, 14)
    with col3:
        letter_spacing = st.number_input("자간", -5, 10, 0)
    with col4:
        line_height = st.number_input("행간", 15, 50, 24)
    
    font_settings = {"font": font, "size": font_size, "letter_spacing": letter_spacing, "line_height": line_height}
    
    # ========== 3. 목차/지침/속지 선택 ==========
    st.markdown("---")
    st.markdown("### 📋 3. 목차 / 지침 / 속지 선택")
    
    services_data = []
    
    for service_id in selected_service_ids:
        service = get_service_by_id(service_id)
        if not service:
            continue
        
        with st.expander(f"📌 {service['name']} 설정", expanded=True):
            chapters = get_chapters_by_service(service_id)
            selected_chapters = []
            if chapters:
                chapter_titles = [c['title'] for c in chapters]
                selected_chapters = st.multiselect("목차", chapter_titles, default=chapter_titles, key=f"ch_{service_id}")
            
            guidelines = get_guidelines_by_service(service_id)
            guideline_content = ""
            if guidelines:
                guideline_titles = [g['title'] for g in guidelines]
                sel_guide = st.selectbox("지침", guideline_titles, key=f"guide_{service_id}")
                for g in guidelines:
                    if g['title'] == sel_guide:
                        guideline_content = g['content']
            
            templates = get_templates_by_service(service_id)
            cover_img = intro_img = bg_img = info_img = None
            
            if templates:
                col_a, col_b, col_c, col_d = st.columns(4)
                for t in templates:
                    if t['template_type'] == 'cover':
                        with col_a:
                            if st.checkbox(f"표지: {t['name']}", key=f"cv_{t['id']}"):
                                cover_img = t['image_path']
                    elif t['template_type'] == 'intro':
                        with col_b:
                            if st.checkbox(f"소개: {t['name']}", key=f"in_{t['id']}"):
                                intro_img = t['image_path']
                    elif t['template_type'] == 'background':
                        with col_c:
                            if st.checkbox(f"속지: {t['name']}", key=f"bg_{t['id']}"):
                                bg_img = t['image_path']
                    elif t['template_type'] == 'info':
                        with col_d:
                            if st.checkbox(f"안내: {t['name']}", key=f"if_{t['id']}"):
                                info_img = t['image_path']
            
            services_data.append({
                "service_id": service_id,
                "service_name": service['name'],
                "chapters": selected_chapters,
                "guideline": guideline_content,
                "cover_image": cover_img,
                "intro_image": intro_img,
                "background_image": bg_img,
                "info_image": info_img
            })
    
    # ========== 4. 고객 파일 ==========
    st.markdown("---")
    st.markdown("### 📁 4. 고객 파일")
    
    uploaded_file = st.file_uploader("엑셀 파일", type=["xlsx", "xls"])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.session_state.customers_df = df
            st.success(f"✅ {len(df)}명 로드됨")
            st.write("**컬럼:** " + ", ".join(df.columns.tolist()))
            with st.expander("미리보기"):
                st.dataframe(df.head())
        except Exception as e:
            st.error(f"파일 오류: {e}")
    
    # ========== 5. 고객 선택 ==========
    if st.session_state.customers_df is not None:
        df = st.session_state.customers_df
        
        st.markdown("---")
        st.markdown("### 👥 5. 고객 선택")
        
        process_mode = st.radio("처리 방식", ["전체 처리", "선택 처리"], horizontal=True)
        
        # 이름/이메일 컬럼 찾기
        name_col = email_col = None
        for col in ['이름', 'name', 'Name', '성명']:
            if col in df.columns:
                name_col = col
                break
        for col in ['이메일', 'email', 'Email', 'E-mail']:
            if col in df.columns:
                email_col = col
                break
        
        name_col = name_col or df.columns[0]
        
        selected_indices = []
        
        if process_mode == "전체 처리":
            selected_indices = list(range(len(df)))
            st.info(f"전체 {len(df)}명")
        else:
            for idx, row in df.iterrows():
                if st.checkbox(f"{row[name_col]}", key=f"cust_{idx}"):
                    selected_indices.append(idx)
            st.info(f"{len(selected_indices)}명 선택")
        
        # ========== 6. 발송 설정 (5단계 핵심!) ==========
        st.markdown("---")
        st.markdown("### 📧 6. 발송 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            send_method = st.radio("발송 방법", ["📧 이메일", "💬 카톡 (준비중)"], horizontal=True)
        
        with col2:
            auto_send = st.checkbox("생성 후 자동 발송", value=False)
        
        # 이메일 설정 확인
        email_config = get_email_config()
        
        if send_method == "📧 이메일":
            if email_config:
                st.success(f"✅ 발송 이메일: {email_config['email']} ({email_config['source']} 설정)")
            else:
                st.warning("⚠️ 이메일 설정이 없습니다. MyPage 또는 관리자 설정에서 Gmail을 설정해주세요.")
                auto_send = False
        
        # ========== 7. 생성 및 발송 ==========
        st.markdown("---")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            generate_btn = st.button("🚀 PDF 생성", type="primary", use_container_width=True)
        
        with col_btn2:
            send_btn = st.button("📧 선택 발송", use_container_width=True, 
                                disabled=len(st.session_state.generated_pdfs) == 0)
        
        # PDF 생성
        if generate_btn:
            if not selected_indices:
                st.error("고객을 선택해주세요.")
                return
            
            total_chapters = sum(len(s['chapters']) for s in services_data)
            if total_chapters == 0:
                st.error("목차를 선택해주세요.")
                return
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            generated_files = []
            service_names = " + ".join([s['service_name'] for s in services_data])
            
            for cust_idx, row_idx in enumerate(selected_indices):
                row = df.iloc[row_idx]
                customer_info = dict(row)
                customer_name = str(row[name_col])
                customer_email = str(row[email_col]) if email_col and email_col in row else ""
                
                status_text.text(f"📝 {customer_name} 생성 중... ({cust_idx+1}/{len(selected_indices)})")
                
                try:
                    def update_progress(p, msg):
                        overall = (cust_idx + p) / len(selected_indices)
                        progress_bar.progress(overall)
                        status_text.text(f"📝 {customer_name}: {msg}")
                    
                    pdf_bytes = generate_combined_pdf(
                        api_key=api_key,
                        customer_info=customer_info,
                        services_data=services_data,
                        font_settings=font_settings,
                        progress_callback=update_progress
                    )
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{customer_name}_{timestamp}.pdf"
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(pdf_bytes)
                    
                    generated_files.append({
                        "name": customer_name,
                        "email": customer_email,
                        "filename": filename,
                        "filepath": filepath,
                        "bytes": pdf_bytes,
                        "sent": False
                    })
                
                except Exception as e:
                    st.error(f"❌ {customer_name} 실패: {e}")
            
            progress_bar.progress(1.0)
            status_text.text("✅ 생성 완료!")
            
            st.session_state.generated_pdfs = generated_files
            
            # 자동 발송
            if auto_send and email_config and send_method == "📧 이메일":
                st.markdown("---")
                st.markdown("### 📧 자동 발송 중...")
                
                send_progress = st.progress(0)
                send_status = st.empty()
                
                success_count = 0
                fail_count = 0
                
                for idx, file_info in enumerate(generated_files):
                    if not file_info['email']:
                        fail_count += 1
                        continue
                    
                    send_status.text(f"📧 {file_info['name']}에게 발송 중...")
                    
                    result = send_email_with_pdf(
                        sender_email=email_config['email'],
                        sender_password=email_config['password'],
                        recipient_email=file_info['email'],
                        recipient_name=file_info['name'],
                        service_type=service_names,
                        pdf_path=file_info['filepath']
                    )
                    
                    if result['success']:
                        success_count += 1
                        file_info['sent'] = True
                    else:
                        fail_count += 1
                    
                    send_progress.progress((idx + 1) / len(generated_files))
                
                send_status.text("✅ 발송 완료!")
                st.success(f"📧 발송 결과: 성공 {success_count}건 / 실패 {fail_count}건")
        
        # 생성된 PDF 목록 표시
        if st.session_state.generated_pdfs:
            st.markdown("---")
            st.markdown("### 📥 생성된 PDF")
            
            for file_info in st.session_state.generated_pdfs:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    sent_icon = "✅" if file_info.get('sent') else "⏳"
                    st.write(f"{sent_icon} **{file_info['name']}** ({file_info['email'] or '이메일 없음'})")
                with col2:
                    st.download_button("📥", data=file_info['bytes'], file_name=file_info['filename'], 
                                      mime="application/pdf", key=f"dl_{file_info['filename']}")
                with col3:
                    if not file_info.get('sent') and file_info['email'] and email_config:
                        if st.button("📧", key=f"send_{file_info['filename']}"):
                            result = send_email_with_pdf(
                                sender_email=email_config['email'],
                                sender_password=email_config['password'],
                                recipient_email=file_info['email'],
                                recipient_name=file_info['name'],
                                service_type=service_names,
                                pdf_path=file_info['filepath']
                            )
                            if result['success']:
                                file_info['sent'] = True
                                st.success(f"✅ {file_info['name']}에게 발송 완료!")
                                st.rerun()
                            else:
                                st.error(result['message'])

# ============================================
# MyPage
# ============================================

def show_mypage():
    st.title("👤 MyPage")
    user = st.session_state.user
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 내 정보")
        role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
        st.info(f"등급: {role_text.get(user['role'], user['role'])}")
        
        new_name = st.text_input("이름", value=user['name'])
        st.text_input("이메일", value=user['email'], disabled=True)
        
        st.markdown("### 🔒 비밀번호 변경")
        old_pw = st.text_input("현재 비밀번호", type="password", key="old_pw")
        new_pw = st.text_input("새 비밀번호", type="password", key="new_pw")
        
        if st.button("비밀번호 변경"):
            if old_pw and new_pw:
                result = change_password(user['id'], old_pw, new_pw)
                if result["success"]:
                    st.success("변경되었습니다.")
                else:
                    st.error(result["error"])
    
    with col2:
        st.markdown("### 🔑 API 설정")
        
        use_admin = st.radio("API 선택", ["관리자 API", "내 API"], 
                            index=0 if user.get('use_admin_api', True) else 1)
        
        my_api = ""
        if use_admin == "내 API":
            my_api = st.text_input("OpenAI API 키", value=user.get('api_key', '') or '', type="password")
        else:
            st.info(f"사용량: {user.get('api_usage_count', 0)} / {user.get('api_usage_limit', 100)}")
        
        st.markdown("### 📧 내 이메일 설정")
        st.caption("개인 Gmail을 설정하면 본인 이메일로 발송됩니다.")
        
        gmail = st.text_input("Gmail 주소", value=user.get('gmail_address', '') or '')
        gmail_pw = st.text_input("Gmail 앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
        
        with st.expander("📌 Gmail 앱 비밀번호 발급"):
            st.markdown("""
            1. Google 계정 → 보안 → 2단계 인증 활성화
            2. https://myaccount.google.com/apppasswords
            3. 앱 이름 입력 → 생성 → 16자리 복사
            """)
        
        if st.button("💾 저장", type="primary", use_container_width=True):
            update_data = {
                'name': new_name,
                'use_admin_api': use_admin == "관리자 API",
                'gmail_address': gmail,
                'gmail_app_password': gmail_pw,
            }
            if use_admin == "내 API":
                update_data['api_key'] = my_api
            
            result = update_user_profile(user['id'], **update_data)
            if result["success"]:
                st.session_state.user.update(update_data)
                st.success("저장되었습니다.")

# ============================================
# 공지
# ============================================

def show_notice_write():
    st.title("✏️ 공지 작성")
    if not require_permission(2):
        return
    st.info("🚧 6단계에서 구현 예정")

def show_notices():
    st.title("📢 공지사항")
    st.info("🚧 6단계에서 구현 예정")

# ============================================
# 메인
# ============================================

def main():
    if not os.environ.get("DATABASE_URL"):
        st.error("⚠️ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        if st.button("테스트 로그인"):
            st.session_state.logged_in = True
            st.session_state.user = {
                "id": 1, "email": "test@test.com", "name": "테스트 관리자",
                "role": 3, "status": "approved", "api_key": None,
                "use_admin_api": True, "api_usage_count": 0, "api_usage_limit": 100,
                "gmail_address": None, "gmail_app_password": None,
            }
            st.rerun()
        return
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
