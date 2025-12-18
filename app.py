# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
4단계: PDF 생성 (핵심 기능)
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
    delete_service, restore_service, reorder_services,
    get_system_config, set_system_config, get_all_system_configs, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, update_chapter, delete_chapter,
    get_guidelines_by_service, get_guideline_by_id, add_guideline, update_guideline, delete_guideline,
    get_templates_by_service, get_template_by_id, add_template, update_template, delete_template,
    TEMPLATE_TYPES
)
from pdf_generator import generate_combined_pdf, PDFGenerator

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
# 이미지 저장 경로
# ============================================

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

OUTPUT_DIR = "outputs"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ============================================
# CSS 스타일
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
    .customer-card { background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; margin: 5px 0; }
</style>
""", unsafe_allow_html=True)

# ============================================
# 세션 상태 초기화
# ============================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'customers_df' not in st.session_state:
    st.session_state.customers_df = None
if 'selected_customers' not in st.session_state:
    st.session_state.selected_customers = []

# ============================================
# 데이터베이스 초기화
# ============================================

@st.cache_resource
def initialize_database():
    init_db()
    return True

db_initialized = initialize_database()

# ============================================
# 권한 체크 함수
# ============================================

def check_permission(required_role: int) -> bool:
    if not st.session_state.user:
        return False
    return st.session_state.user.get('role', 0) >= required_role

def require_permission(required_role: int):
    if not check_permission(required_role):
        role_names = {1: "1단계", 2: "2단계", 3: "관리자"}
        st.error(f"⛔ 이 기능은 {role_names.get(required_role, required_role)} 이상 권한이 필요합니다.")
        return False
    return True

# ============================================
# 파일 저장 함수
# ============================================

def save_uploaded_file(uploaded_file, service_name: str, file_type: str) -> str:
    if uploaded_file is None:
        return None
    file_ext = uploaded_file.name.split('.')[-1]
    safe_service = service_name.replace(' ', '_')
    filename = f"{safe_service}_{file_type}_{uploaded_file.name}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filepath

# ============================================
# API 키 가져오기
# ============================================

def get_api_key() -> str:
    """사용자 설정에 따라 API 키 반환"""
    user = st.session_state.user
    
    if user.get('use_admin_api', True):
        # 관리자 API 사용
        return get_system_config(ConfigKeys.ADMIN_API_KEY, "")
    else:
        # 개인 API 사용
        return user.get('api_key', "")

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
        current_gmail = get_system_config(ConfigKeys.ADMIN_GMAIL, "")
        current_gmail_pw = get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, "")
        admin_gmail = st.text_input("Gmail 주소", value=current_gmail)
        admin_gmail_pw = st.text_input("Gmail 앱 비밀번호", value=current_gmail_pw, type="password")
        
        if st.button("이메일 설정 저장", type="primary"):
            set_system_config(ConfigKeys.ADMIN_GMAIL, admin_gmail)
            set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, admin_gmail_pw)
            st.success("✅ 저장되었습니다.")
    
    with tab3:
        current_kakao = get_system_config(ConfigKeys.KAKAO_CHANNEL_ID, "")
        kakao_channel = st.text_input("카카오 채널 ID", value=current_kakao)
        
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
                st.success("추가되었습니다.")
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
                if user['id'] != st.session_state.user['id']:
                    if user['status'] == "approved":
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
        st.error("서비스를 찾을 수 없습니다.")
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
                st.text_area("내용", value=g['content'], height=150, key=f"g_content_{g['id']}", disabled=True)
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
# PDF 생성 (4단계 핵심!)
# ============================================

def show_pdf_generation():
    st.title("📄 PDF 생성")
    
    # API 키 확인
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ API 키가 설정되지 않았습니다. MyPage 또는 관리자 설정에서 API 키를 설정해주세요.")
        return
    
    services = get_all_services()
    if not services:
        st.warning("등록된 서비스가 없습니다.")
        return
    
    # ========== 1. 서비스 선택 ==========
    st.markdown("### 📌 1. 서비스 선택 (중복 가능)")
    
    selected_service_ids = []
    cols = st.columns(len(services))
    for idx, service in enumerate(services):
        with cols[idx]:
            if st.checkbox(service['name'], key=f"svc_{service['id']}"):
                selected_service_ids.append(service['id'])
    
    if not selected_service_ids:
        st.info("서비스를 선택해주세요.")
        return
    
    st.success(f"✅ {len(selected_service_ids)}개 서비스 선택됨 → 합본 PDF")
    
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
    
    font_settings = {
        "font": font,
        "size": font_size,
        "letter_spacing": letter_spacing,
        "line_height": line_height
    }
    
    # ========== 3. 목차/지침/속지 선택 ==========
    st.markdown("---")
    st.markdown("### 📋 3. 목차 / 지침 / 속지 선택")
    
    services_data = []
    
    for service_id in selected_service_ids:
        service = get_service_by_id(service_id)
        if not service:
            continue
        
        with st.expander(f"📌 {service['name']} 설정", expanded=True):
            # 목차 선택
            chapters = get_chapters_by_service(service_id)
            selected_chapters = []
            
            if chapters:
                chapter_titles = [c['title'] for c in chapters]
                selected_chapters = st.multiselect(
                    "목차 선택",
                    chapter_titles,
                    default=chapter_titles,
                    key=f"chapters_{service_id}"
                )
            else:
                st.warning("등록된 목차가 없습니다.")
            
            # 지침 선택
            guidelines = get_guidelines_by_service(service_id)
            selected_guideline_content = ""
            
            if guidelines:
                guideline_titles = [g['title'] for g in guidelines]
                selected_guideline_title = st.selectbox(
                    "지침 선택",
                    guideline_titles,
                    key=f"guideline_{service_id}"
                )
                # 선택된 지침 내용 가져오기
                for g in guidelines:
                    if g['title'] == selected_guideline_title:
                        selected_guideline_content = g['content']
                        break
            else:
                st.warning("등록된 지침이 없습니다.")
            
            # 속지 선택
            templates = get_templates_by_service(service_id)
            
            cover_image = None
            intro_image = None
            background_image = None
            info_image = None
            
            if templates:
                st.markdown("**속지 선택:**")
                col_a, col_b, col_c, col_d = st.columns(4)
                
                cover_templates = [t for t in templates if t['template_type'] == 'cover']
                intro_templates = [t for t in templates if t['template_type'] == 'intro']
                bg_templates = [t for t in templates if t['template_type'] == 'background']
                info_templates = [t for t in templates if t['template_type'] == 'info']
                
                with col_a:
                    if cover_templates:
                        cover_names = ["(없음)"] + [t['name'] for t in cover_templates]
                        sel_cover = st.selectbox("표지", cover_names, key=f"cover_{service_id}")
                        for t in cover_templates:
                            if t['name'] == sel_cover:
                                cover_image = t['image_path']
                
                with col_b:
                    if intro_templates:
                        intro_names = ["(없음)"] + [t['name'] for t in intro_templates]
                        sel_intro = st.selectbox("소개", intro_names, key=f"intro_{service_id}")
                        for t in intro_templates:
                            if t['name'] == sel_intro:
                                intro_image = t['image_path']
                
                with col_c:
                    if bg_templates:
                        bg_names = ["(없음)"] + [t['name'] for t in bg_templates]
                        sel_bg = st.selectbox("속지", bg_names, key=f"bg_{service_id}")
                        for t in bg_templates:
                            if t['name'] == sel_bg:
                                background_image = t['image_path']
                
                with col_d:
                    if info_templates:
                        info_names = ["(없음)"] + [t['name'] for t in info_templates]
                        sel_info = st.selectbox("안내", info_names, key=f"info_{service_id}")
                        for t in info_templates:
                            if t['name'] == sel_info:
                                info_image = t['image_path']
            
            # 서비스 데이터 저장
            services_data.append({
                "service_id": service_id,
                "service_name": service['name'],
                "chapters": selected_chapters,
                "guideline": selected_guideline_content,
                "cover_image": cover_image,
                "intro_image": intro_image,
                "background_image": background_image,
                "info_image": info_image
            })
    
    # ========== 4. 고객 파일 업로드 ==========
    st.markdown("---")
    st.markdown("### 📁 4. 고객 파일 업로드")
    
    uploaded_file = st.file_uploader("엑셀 파일 (.xlsx, .xls)", type=["xlsx", "xls"])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.session_state.customers_df = df
            
            st.success(f"✅ {len(df)}명의 고객 정보 로드됨")
            
            # 컬럼 표시
            st.markdown("**인식된 컬럼:**")
            st.write(", ".join(df.columns.tolist()))
            
            # 데이터 미리보기
            with st.expander("데이터 미리보기"):
                st.dataframe(df.head(10))
        
        except Exception as e:
            st.error(f"파일 읽기 오류: {str(e)}")
    
    # ========== 5. 고객 선택 및 처리 ==========
    if st.session_state.customers_df is not None:
        df = st.session_state.customers_df
        
        st.markdown("---")
        st.markdown("### 👥 5. 고객 선택")
        
        process_mode = st.radio(
            "처리 방식",
            ["전체 고객 처리", "특정 고객 선택"],
            horizontal=True
        )
        
        selected_indices = []
        
        if process_mode == "전체 고객 처리":
            selected_indices = list(range(len(df)))
            st.info(f"전체 {len(df)}명 처리 예정")
        
        else:
            # 고객 선택 UI
            st.markdown("**처리할 고객을 선택하세요:**")
            
            # 이름 컬럼 찾기
            name_col = None
            for col in ['이름', 'name', 'Name', '성명']:
                if col in df.columns:
                    name_col = col
                    break
            
            if name_col is None:
                name_col = df.columns[0]  # 첫 번째 컬럼 사용
            
            for idx, row in df.iterrows():
                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.checkbox("", key=f"cust_{idx}"):
                        selected_indices.append(idx)
                with col2:
                    st.write(f"**{row[name_col]}** - {dict(row)}")
            
            st.info(f"{len(selected_indices)}명 선택됨")
        
        # ========== 6. PDF 생성 버튼 ==========
        st.markdown("---")
        st.markdown("### 🚀 6. PDF 생성")
        
        col1, col2 = st.columns(2)
        
        with col1:
            send_method = st.radio("발송 방법", ["📧 이메일", "💬 카톡 알림"], horizontal=True)
        
        with col2:
            auto_send = st.checkbox("생성 후 자동 발송")
        
        if st.button("🚀 PDF 생성 시작", type="primary", use_container_width=True):
            if not selected_indices:
                st.error("처리할 고객을 선택해주세요.")
                return
            
            # 목차 확인
            total_chapters = sum(len(s['chapters']) for s in services_data)
            if total_chapters == 0:
                st.error("선택된 목차가 없습니다.")
                return
            
            # 진행 상황 표시
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            generated_files = []
            
            for cust_idx, row_idx in enumerate(selected_indices):
                row = df.iloc[row_idx]
                customer_info = dict(row)
                
                # 이름 찾기
                customer_name = "고객"
                for col in ['이름', 'name', 'Name', '성명']:
                    if col in customer_info and customer_info[col]:
                        customer_name = str(customer_info[col])
                        break
                
                status_text.text(f"📝 {customer_name} 처리 중... ({cust_idx+1}/{len(selected_indices)})")
                
                try:
                    # 진행률 콜백
                    def update_progress(progress, message):
                        overall = (cust_idx + progress) / len(selected_indices)
                        progress_bar.progress(overall)
                        status_text.text(f"📝 {customer_name}: {message}")
                    
                    # PDF 생성
                    pdf_bytes = generate_combined_pdf(
                        api_key=api_key,
                        customer_info=customer_info,
                        services_data=services_data,
                        font_settings=font_settings,
                        progress_callback=update_progress
                    )
                    
                    # 파일 저장
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{customer_name}_{timestamp}.pdf"
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(pdf_bytes)
                    
                    generated_files.append({
                        "name": customer_name,
                        "filename": filename,
                        "filepath": filepath,
                        "bytes": pdf_bytes,
                        "email": customer_info.get('이메일', customer_info.get('email', ''))
                    })
                
                except Exception as e:
                    st.error(f"❌ {customer_name} 처리 실패: {str(e)}")
            
            progress_bar.progress(1.0)
            status_text.text("✅ 완료!")
            
            # 결과 표시
            st.markdown("---")
            st.markdown("### 📥 생성된 PDF")
            
            for file_info in generated_files:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"✅ **{file_info['name']}** - {file_info['filename']}")
                with col2:
                    st.download_button(
                        "📥 다운로드",
                        data=file_info['bytes'],
                        file_name=file_info['filename'],
                        mime="application/pdf",
                        key=f"dl_{file_info['filename']}"
                    )
            
            st.success(f"🎉 총 {len(generated_files)}개 PDF 생성 완료!")
            
            # TODO: 5단계에서 자동 발송 구현
            if auto_send:
                st.info("🚧 자동 발송은 5단계에서 구현 예정입니다.")

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
        
        use_admin = st.radio("API 선택", ["관리자 API", "내 API"], index=0 if user.get('use_admin_api', True) else 1)
        
        if use_admin == "내 API":
            my_api = st.text_input("OpenAI API 키", value=user.get('api_key', '') or '', type="password")
        else:
            st.info(f"사용량: {user.get('api_usage_count', 0)} / {user.get('api_usage_limit', 100)}")
        
        st.markdown("### 📧 이메일 설정")
        gmail = st.text_input("Gmail", value=user.get('gmail_address', '') or '')
        gmail_pw = st.text_input("Gmail 앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
        
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
# 공지 작성 / 공지사항
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
# 메인 실행
# ============================================

def main():
    if not os.environ.get("DATABASE_URL"):
        st.error("⚠️ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        st.markdown("---")
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
