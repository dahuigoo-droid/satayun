# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
3단계: 목차/지침/속지 관리 CRUD
"""

import streamlit as st
import os
import base64
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
    get_chapters_by_service, add_chapter, update_chapter, delete_chapter, reorder_chapters,
    get_guidelines_by_service, get_guideline_by_id, add_guideline, update_guideline, delete_guideline,
    get_templates_by_service, get_template_by_id, add_template, update_template, delete_template,
    TEMPLATE_TYPES
)

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

# ============================================
# CSS 스타일
# ============================================

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    .main-title {
        text-align: center;
        color: #fff;
        font-size: 2.5rem;
        margin-bottom: 10px;
    }
    .sub-title {
        text-align: center;
        color: #888;
        font-size: 1rem;
        margin-bottom: 30px;
    }
    .role-badge {
        padding: 3px 10px;
        border-radius: 10px;
        font-size: 0.8rem;
        display: inline-block;
    }
    .role-1 { background: #6c757d; color: #fff; }
    .role-2 { background: #17a2b8; color: #fff; }
    .role-3 { background: #dc3545; color: #fff; }
</style>
""", unsafe_allow_html=True)

# ============================================
# 세션 상태 초기화
# ============================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None

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
    """업로드된 파일 저장 후 경로 반환"""
    if uploaded_file is None:
        return None
    
    # 파일명 생성
    file_ext = uploaded_file.name.split('.')[-1]
    safe_service = service_name.replace(' ', '_')
    filename = f"{safe_service}_{file_type}_{uploaded_file.name}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # 파일 저장
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return filepath

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
            st.markdown("### 로그인")
            email = st.text_input("이메일", key="login_email", placeholder="example@email.com")
            password = st.text_input("비밀번호", type="password", key="login_password")
            
            if st.button("로그인", type="primary", use_container_width=True):
                if not email or not password:
                    st.error("이메일과 비밀번호를 입력해주세요.")
                else:
                    result = login_user(email, password)
                    if result["success"]:
                        st.session_state.logged_in = True
                        st.session_state.user = result["user"]
                        st.success(f"환영합니다, {result['user']['name']}님!")
                        st.rerun()
                    else:
                        st.error(result["error"])
        
        with tab2:
            st.markdown("### 회원가입")
            reg_name = st.text_input("이름", key="reg_name", placeholder="홍길동")
            reg_email = st.text_input("이메일", key="reg_email", placeholder="example@email.com")
            reg_password = st.text_input("비밀번호", type="password", key="reg_password")
            reg_password2 = st.text_input("비밀번호 확인", type="password", key="reg_password2")
            
            if st.button("회원가입", type="primary", use_container_width=True):
                if not all([reg_name, reg_email, reg_password, reg_password2]):
                    st.error("모든 필드를 입력해주세요.")
                elif reg_password != reg_password2:
                    st.error("비밀번호가 일치하지 않습니다.")
                elif len(reg_password) < 4:
                    st.error("비밀번호는 4자 이상이어야 합니다.")
                else:
                    result = register_user(reg_email, reg_password, reg_name)
                    if result["success"]:
                        st.success(result["message"])
                        st.info("관리자 승인 후 로그인할 수 있습니다.")
                    else:
                        st.error(result["error"])
        
        st.markdown("---")
        
        if not check_admin_exists():
            with st.expander("🔧 최초 관리자 설정"):
                st.warning("아직 관리자가 없습니다.")
                admin_name = st.text_input("관리자 이름", key="admin_name")
                admin_email = st.text_input("관리자 이메일", key="admin_email")
                admin_password = st.text_input("관리자 비밀번호", type="password", key="admin_password")
                
                if st.button("관리자 계정 생성", type="secondary"):
                    if all([admin_name, admin_email, admin_password]):
                        result = create_first_admin(admin_email, admin_password, admin_name)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()

# ============================================
# 메인 앱 (로그인 후)
# ============================================

def show_main_app():
    user = st.session_state.user
    
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}님")
        
        role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
        role_color = {1: "role-1", 2: "role-2", 3: "role-3"}
        st.markdown(
            f'<span class="role-badge {role_color[user["role"]]}">{role_text[user["role"]]}</span>',
            unsafe_allow_html=True
        )
        
        st.markdown("---")
        
        menu_options = []
        
        if user["role"] == 3:
            menu_options.append("⚙️ 관리자 설정")
            menu_options.append("👥 회원 관리")
            menu_options.append("📦 서비스 관리")
        
        if user["role"] >= 1:
            menu_options.append("📋 목차/지침/속지 관리")
        
        menu_options.append("📄 PDF 생성")
        menu_options.append("👤 MyPage")
        
        if user["role"] >= 2:
            menu_options.append("✏️ 공지 작성")
        
        menu_options.append("📢 공지사항")
        
        selected_menu = st.radio("메뉴", menu_options, label_visibility="collapsed")
        
        st.markdown("---")
        
        if user.get('use_admin_api', True):
            usage = user.get('api_usage_count', 0)
            limit = user.get('api_usage_limit', 100)
            st.caption(f"API 사용량: {usage}/{limit}")
            if limit > 0:
                st.progress(min(usage / limit, 1.0))
        
        st.markdown("---")
        
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()
    
    # 메인 콘텐츠
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
# 관리자 설정 페이지
# ============================================

def show_admin_settings():
    st.title("⚙️ 관리자 설정")
    
    if not require_permission(3):
        return
    
    tab1, tab2, tab3 = st.tabs(["🔑 API 설정", "📧 이메일 설정", "💬 카카오 설정"])
    
    with tab1:
        st.markdown("### 🔑 관리자 API 설정")
        current_api_key = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
        admin_api_key = st.text_input("OpenAI API 키", value=current_api_key, type="password")
        
        st.markdown("---")
        st.markdown("### 📊 기본 API 사용 한도")
        current_limit = get_system_config(ConfigKeys.DEFAULT_API_LIMIT, "100")
        default_limit = st.number_input("신규 회원 기본 한도", min_value=10, max_value=10000, value=int(current_limit), step=10)
        
        if st.button("API 설정 저장", type="primary"):
            set_system_config(ConfigKeys.ADMIN_API_KEY, admin_api_key)
            set_system_config(ConfigKeys.DEFAULT_API_LIMIT, str(default_limit))
            st.success("✅ API 설정이 저장되었습니다.")
    
    with tab2:
        st.markdown("### 📧 관리자 이메일 설정")
        current_gmail = get_system_config(ConfigKeys.ADMIN_GMAIL, "")
        current_gmail_pw = get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, "")
        
        admin_gmail = st.text_input("Gmail 주소", value=current_gmail)
        admin_gmail_pw = st.text_input("Gmail 앱 비밀번호", value=current_gmail_pw, type="password")
        
        if st.button("이메일 설정 저장", type="primary"):
            set_system_config(ConfigKeys.ADMIN_GMAIL, admin_gmail)
            set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, admin_gmail_pw)
            st.success("✅ 이메일 설정이 저장되었습니다.")
    
    with tab3:
        st.markdown("### 💬 카카오 알림톡 설정")
        current_kakao_channel = get_system_config(ConfigKeys.KAKAO_CHANNEL_ID, "")
        current_kakao_api = get_system_config(ConfigKeys.KAKAO_API_KEY, "")
        
        kakao_channel_id = st.text_input("카카오 채널 ID", value=current_kakao_channel)
        kakao_api_key = st.text_input("카카오 API 키", value=current_kakao_api, type="password")
        
        if st.button("카카오 설정 저장", type="primary"):
            set_system_config(ConfigKeys.KAKAO_CHANNEL_ID, kakao_channel_id)
            set_system_config(ConfigKeys.KAKAO_API_KEY, kakao_api_key)
            st.success("✅ 카카오 설정이 저장되었습니다.")

# ============================================
# 서비스 관리 페이지
# ============================================

def show_service_management():
    st.title("📦 서비스 관리")
    
    if not require_permission(3):
        return
    
    tab1, tab2 = st.tabs(["📋 서비스 목록", "➕ 서비스 추가"])
    
    with tab1:
        services = get_all_services(include_inactive=True)
        
        if not services:
            st.info("등록된 서비스가 없습니다.")
        else:
            active_services = [s for s in services if s['is_active']]
            inactive_services = [s for s in services if not s['is_active']]
            
            for service in active_services:
                col1, col2, col3, col4 = st.columns([2, 4, 1, 1])
                with col1:
                    st.markdown(f"**{service['order']}. {service['name']}**")
                with col2:
                    st.caption(service['description'] or "설명 없음")
                with col3:
                    if st.button("✏️", key=f"edit_{service['id']}"):
                        st.session_state[f"editing_{service['id']}"] = True
                        st.rerun()
                with col4:
                    if st.button("🗑️", key=f"del_{service['id']}"):
                        delete_service(service['id'])
                        st.rerun()
                
                if st.session_state.get(f"editing_{service['id']}", False):
                    new_name = st.text_input("이름", value=service['name'], key=f"name_{service['id']}")
                    new_desc = st.text_input("설명", value=service['description'] or "", key=f"desc_{service['id']}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("저장", key=f"save_{service['id']}", type="primary"):
                            update_service(service['id'], name=new_name, description=new_desc)
                            st.session_state[f"editing_{service['id']}"] = False
                            st.rerun()
                    with col_b:
                        if st.button("취소", key=f"cancel_{service['id']}"):
                            st.session_state[f"editing_{service['id']}"] = False
                            st.rerun()
                st.markdown("---")
            
            if inactive_services:
                st.markdown("### 🚫 비활성 서비스")
                for service in inactive_services:
                    col1, col2, col3 = st.columns([3, 5, 1])
                    with col1:
                        st.markdown(f"~~{service['name']}~~")
                    with col3:
                        if st.button("복구", key=f"restore_{service['id']}"):
                            restore_service(service['id'])
                            st.rerun()
    
    with tab2:
        new_service_name = st.text_input("서비스 이름", placeholder="예: 궁합, 운세 등")
        new_service_desc = st.text_area("서비스 설명")
        
        if st.button("서비스 추가", type="primary"):
            if not new_service_name:
                st.error("서비스 이름을 입력해주세요.")
            else:
                result = add_service(new_service_name, new_service_desc)
                if result["success"]:
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["error"])

# ============================================
# 회원 관리 페이지
# ============================================

def show_user_management():
    st.title("👥 회원 관리")
    
    if not require_permission(3):
        return
    
    tab1, tab2 = st.tabs(["📋 전체 회원", "⏳ 승인 대기"])
    
    with tab1:
        users = get_all_users()
        if not users:
            st.info("등록된 회원이 없습니다.")
        else:
            for user in users:
                col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 2])
                with col1:
                    st.write(f"**{user['name']}**")
                    st.caption(user['email'])
                with col2:
                    status_text = {"pending": "⏳ 대기", "approved": "✅ 승인", "suspended": "⛔ 중지", "banned": "❌ 강퇴"}
                    st.write(status_text.get(user['status'], user['status']))
                with col3:
                    role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
                    st.write(role_text.get(user['role'], user['role']))
                with col4:
                    st.write(f"API: {user['api_usage_count']}/{user['api_usage_limit']}")
                with col5:
                    if user['id'] != st.session_state.user['id']:
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            new_role = st.selectbox("등급", [1, 2, 3], index=user['role'] - 1, key=f"role_{user['id']}", label_visibility="collapsed")
                            if new_role != user['role']:
                                if st.button("변경", key=f"role_btn_{user['id']}"):
                                    update_user_role(user['id'], new_role)
                                    st.rerun()
                        with col_b:
                            if user['status'] == "approved":
                                if st.button("중지", key=f"suspend_{user['id']}"):
                                    suspend_user(user['id'])
                                    st.rerun()
                            elif user['status'] == "suspended":
                                if st.button("복구", key=f"restore_user_{user['id']}"):
                                    approve_user(user['id'])
                                    st.rerun()
                        with col_c:
                            if st.button("🗑️", key=f"ban_{user['id']}"):
                                ban_user(user['id'])
                                st.rerun()
                st.markdown("---")
    
    with tab2:
        pending_users = get_pending_users()
        if not pending_users:
            st.success("승인 대기 중인 회원이 없습니다.")
        else:
            for user in pending_users:
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{user['name']}**")
                    st.caption(user['email'])
                with col2:
                    st.caption(f"가입일: {user['created_at']}")
                with col3:
                    if st.button("✅ 승인", key=f"approve_{user['id']}", type="primary"):
                        approve_user(user['id'])
                        st.rerun()
                st.markdown("---")

# ============================================
# 목차/지침/속지 관리 페이지 (3단계 핵심!)
# ============================================

def show_content_management():
    st.title("📋 목차/지침/속지 관리")
    
    if not require_permission(1):
        return
    
    # 서비스 선택
    services = get_all_services()
    
    if not services:
        st.warning("⚠️ 등록된 서비스가 없습니다. 관리자에게 문의하세요.")
        return
    
    service_names = [s['name'] for s in services]
    selected_service_name = st.selectbox("📌 서비스 선택", service_names)
    
    # 선택된 서비스 찾기
    selected_service = None
    for s in services:
        if s['name'] == selected_service_name:
            selected_service = s
            break
    
    if not selected_service:
        st.error("⚠️ 분류를 잘못 선택했습니다. 다시 선택해주세요.")
        return
    
    service_id = selected_service['id']
    
    st.markdown("---")
    
    # 탭: 목차 / 지침 / 속지
    tab1, tab2, tab3 = st.tabs(["📑 목차 관리", "📜 지침 관리", "🖼️ 속지 관리"])
    
    # ========== 목차 관리 ==========
    with tab1:
        st.markdown(f"### 📑 {selected_service_name} - 목차 설정")
        
        # 목차 추가
        with st.expander("➕ 새 목차 추가", expanded=False):
            new_chapter_title = st.text_input("목차 제목", key="new_chapter_title", placeholder="예: 총운, 성격분석, 재물운...")
            new_chapter_desc = st.text_input("목차 설명 (선택)", key="new_chapter_desc")
            
            if st.button("목차 추가", key="add_chapter_btn", type="primary"):
                if new_chapter_title:
                    result = add_chapter(service_id, new_chapter_title, new_chapter_desc)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["error"])
                else:
                    st.error("목차 제목을 입력해주세요.")
        
        st.markdown("---")
        
        # 목차 목록
        chapters = get_chapters_by_service(service_id)
        
        if not chapters:
            st.info("등록된 목차가 없습니다. 위에서 추가해주세요.")
        else:
            st.markdown(f"**총 {len(chapters)}개 목차**")
            
            for chapter in chapters:
                col1, col2, col3, col4 = st.columns([1, 4, 3, 1])
                
                with col1:
                    st.write(f"**{chapter['order']}**")
                
                with col2:
                    st.write(chapter['title'])
                
                with col3:
                    st.caption(chapter['description'] or "-")
                
                with col4:
                    if st.button("🗑️", key=f"del_ch_{chapter['id']}", help="삭제"):
                        delete_chapter(chapter['id'])
                        st.rerun()
            
            st.markdown("---")
    
    # ========== 지침 관리 ==========
    with tab2:
        st.markdown(f"### 📜 {selected_service_name} - 지침 설정")
        
        # 지침 추가
        with st.expander("➕ 새 지침 추가", expanded=False):
            new_guide_title = st.text_input("지침 제목", key="new_guide_title", placeholder="예: 기본 지침, 상세 풀이 지침...")
            new_guide_content = st.text_area("지침 내용", key="new_guide_content", height=300, placeholder="GPT에게 전달할 지침 내용을 작성하세요...")
            
            if st.button("지침 추가", key="add_guide_btn", type="primary"):
                if new_guide_title and new_guide_content:
                    result = add_guideline(service_id, new_guide_title, new_guide_content)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["error"])
                else:
                    st.error("제목과 내용을 모두 입력해주세요.")
        
        st.markdown("---")
        
        # 지침 목록
        guidelines = get_guidelines_by_service(service_id)
        
        if not guidelines:
            st.info("등록된 지침이 없습니다. 위에서 추가해주세요.")
        else:
            st.markdown(f"**총 {len(guidelines)}개 지침**")
            
            for guide in guidelines:
                with st.expander(f"📜 {guide['title']} (수정일: {guide['updated_at']})"):
                    # 수정 모드
                    edit_title = st.text_input("제목", value=guide['title'], key=f"edit_guide_title_{guide['id']}")
                    edit_content = st.text_area("내용", value=guide['content'], height=300, key=f"edit_guide_content_{guide['id']}")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("💾 저장", key=f"save_guide_{guide['id']}", type="primary"):
                            result = update_guideline(guide['id'], title=edit_title, content=edit_content)
                            if result["success"]:
                                st.success("저장되었습니다.")
                                st.rerun()
                            else:
                                st.error(result["error"])
                    with col_b:
                        if st.button("🗑️ 삭제", key=f"del_guide_{guide['id']}"):
                            delete_guideline(guide['id'])
                            st.rerun()
    
    # ========== 속지 관리 ==========
    with tab3:
        st.markdown(f"### 🖼️ {selected_service_name} - 속지 설정")
        st.info("표지, 속지(본문배경), 소개, 안내 이미지를 관리합니다.")
        
        # 템플릿 추가
        with st.expander("➕ 새 속지 추가", expanded=False):
            new_tmpl_type = st.selectbox("유형 선택", list(TEMPLATE_TYPES.keys()), format_func=lambda x: TEMPLATE_TYPES[x], key="new_tmpl_type")
            new_tmpl_name = st.text_input("이름", key="new_tmpl_name", placeholder="예: 기본 표지, 봄 테마 배경...")
            new_tmpl_file = st.file_uploader("이미지 업로드", type=["jpg", "jpeg", "png"], key="new_tmpl_file")
            
            if st.button("속지 추가", key="add_tmpl_btn", type="primary"):
                if new_tmpl_name:
                    # 이미지 저장
                    image_path = None
                    if new_tmpl_file:
                        image_path = save_uploaded_file(new_tmpl_file, selected_service_name, new_tmpl_type)
                    
                    result = add_template(service_id, new_tmpl_type, new_tmpl_name, image_path)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["error"])
                else:
                    st.error("이름을 입력해주세요.")
        
        st.markdown("---")
        
        # 템플릿 목록 (유형별로 표시)
        templates = get_templates_by_service(service_id)
        
        if not templates:
            st.info("등록된 속지가 없습니다. 위에서 추가해주세요.")
        else:
            # 유형별로 그룹핑
            for tmpl_type, tmpl_name in TEMPLATE_TYPES.items():
                type_templates = [t for t in templates if t['template_type'] == tmpl_type]
                
                if type_templates:
                    st.markdown(f"#### {tmpl_name}")
                    
                    cols = st.columns(3)
                    for idx, tmpl in enumerate(type_templates):
                        with cols[idx % 3]:
                            st.markdown(f"**{tmpl['name']}**")
                            
                            # 이미지 미리보기
                            if tmpl['image_path'] and os.path.exists(tmpl['image_path']):
                                st.image(tmpl['image_path'], width=150)
                            else:
                                st.caption("(이미지 없음)")
                            
                            if st.button("🗑️ 삭제", key=f"del_tmpl_{tmpl['id']}"):
                                delete_template(tmpl['id'])
                                st.rerun()
                    
                    st.markdown("---")

# ============================================
# PDF 생성 페이지
# ============================================

def show_pdf_generation():
    st.title("📄 PDF 생성")
    
    st.markdown("### 📌 서비스 선택 (중복 가능)")
    services = get_all_services()
    
    if not services:
        st.warning("등록된 서비스가 없습니다.")
        return
    
    selected_services = []
    cols = st.columns(len(services))
    
    for idx, service in enumerate(services):
        with cols[idx]:
            if st.checkbox(service['name'], key=f"service_check_{service['id']}"):
                selected_services.append(service['id'])
    
    if selected_services:
        st.success(f"선택된 서비스: {len(selected_services)}개 → 합본 PDF 생성")
    
    st.markdown("---")
    
    st.markdown("### 🔤 문서 설정")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        font = st.selectbox("폰트", ["나눔고딕", "맑은고딕", "바탕"])
    with col2:
        font_size = st.number_input("크기", 10, 24, 14)
    with col3:
        letter_spacing = st.number_input("자간", -5, 10, 0)
    with col4:
        line_height = st.number_input("행간", 10, 50, 24)
    
    st.markdown("---")
    
    # 목차/지침 선택 (서비스별)
    if selected_services:
        st.markdown("### 📋 목차 & 지침 선택")
        
        for service_id in selected_services:
            service = get_service_by_id(service_id)
            if service:
                with st.expander(f"📌 {service['name']} 설정"):
                    # 목차 선택
                    chapters = get_chapters_by_service(service_id)
                    if chapters:
                        chapter_options = [c['title'] for c in chapters]
                        selected_chapters = st.multiselect(
                            "목차 선택",
                            chapter_options,
                            default=chapter_options,
                            key=f"chapters_{service_id}"
                        )
                    else:
                        st.caption("등록된 목차가 없습니다.")
                    
                    # 지침 선택
                    guidelines = get_guidelines_by_service(service_id)
                    if guidelines:
                        guide_options = {g['title']: g['id'] for g in guidelines}
                        selected_guide = st.selectbox(
                            "지침 선택",
                            list(guide_options.keys()),
                            key=f"guide_{service_id}"
                        )
                    else:
                        st.caption("등록된 지침이 없습니다.")
    
    st.markdown("---")
    
    st.markdown("### 📁 고객 파일")
    uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx", "xls"])
    
    if uploaded_file:
        st.success(f"✅ 파일 업로드: {uploaded_file.name}")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 PDF 생성 시작", type="primary", use_container_width=True):
            if not selected_services:
                st.error("서비스를 선택해주세요.")
            elif not uploaded_file:
                st.error("고객 파일을 업로드해주세요.")
            else:
                st.info("🚧 4단계에서 구현 예정")
    
    with col2:
        send_method = st.radio("발송 방법", ["📧 이메일 자동발송", "💬 카톡 알림"], horizontal=True)

# ============================================
# MyPage
# ============================================

def show_mypage():
    st.title("👤 MyPage")
    
    user = st.session_state.user
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 내 정보")
        role_text = {1: "1단계 (기본)", 2: "2단계 (공지작성)", 3: "3단계 (관리자)"}
        st.info(f"**등급:** {role_text.get(user['role'], user['role'])}")
        
        new_name = st.text_input("이름", value=user['name'])
        st.text_input("이메일 (변경 불가)", value=user['email'], disabled=True)
        
        st.markdown("---")
        st.markdown("### 🔒 비밀번호 변경")
        old_pw = st.text_input("현재 비밀번호", type="password", key="old_pw")
        new_pw = st.text_input("새 비밀번호", type="password", key="new_pw")
        new_pw2 = st.text_input("새 비밀번호 확인", type="password", key="new_pw2")
        
        if st.button("비밀번호 변경"):
            if new_pw != new_pw2:
                st.error("새 비밀번호가 일치하지 않습니다.")
            elif len(new_pw) < 4:
                st.error("비밀번호는 4자 이상이어야 합니다.")
            else:
                result = change_password(user['id'], old_pw, new_pw)
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["error"])
    
    with col2:
        st.markdown("### 🔑 API 설정")
        
        use_admin_api = st.radio(
            "API 키 선택",
            ["관리자 API 사용", "내 API 사용"],
            index=0 if user.get('use_admin_api', True) else 1
        )
        
        if use_admin_api == "내 API 사용":
            my_api_key = st.text_input("OpenAI API 키", value=user.get('api_key', '') or '', type="password")
        else:
            usage = user.get('api_usage_count', 0)
            limit = user.get('api_usage_limit', 100)
            st.info(f"API 사용량: {usage} / {limit}")
            if limit > 0:
                st.progress(min(usage / limit, 1.0))
        
        st.markdown("---")
        st.markdown("### 📧 이메일 설정")
        gmail_address = st.text_input("Gmail 주소", value=user.get('gmail_address', '') or '')
        gmail_password = st.text_input("Gmail 앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
        
        st.markdown("---")
        
        if st.button("💾 설정 저장", type="primary", use_container_width=True):
            update_data = {
                'name': new_name,
                'use_admin_api': use_admin_api == "관리자 API 사용",
                'gmail_address': gmail_address,
                'gmail_app_password': gmail_password,
            }
            if use_admin_api == "내 API 사용":
                update_data['api_key'] = my_api_key
            
            result = update_user_profile(user['id'], **update_data)
            if result["success"]:
                st.session_state.user.update(update_data)
                st.success("설정이 저장되었습니다.")
            else:
                st.error(result["error"])

# ============================================
# 공지 작성
# ============================================

def show_notice_write():
    st.title("✏️ 공지 작성")
    
    if not require_permission(2):
        return
    
    st.info("🚧 6단계에서 구현 예정")
    
    title = st.text_input("제목")
    content = st.text_area("내용", height=300)
    image = st.file_uploader("이미지 첨부", type=["jpg", "png", "gif"])
    
    if st.button("공지 등록", type="primary"):
        st.warning("6단계에서 구현됩니다.")

# ============================================
# 공지사항 목록
# ============================================

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
        st.markdown("### 🧪 로컬 테스트 모드")
        if st.button("테스트 로그인 (DB 없이)"):
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
