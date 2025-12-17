# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
1단계: 인증 시스템 (회원가입/로그인/승인대기/관리자)
"""

import streamlit as st
import os
from database import init_db, SessionLocal, UserRole
from auth import (
    register_user, login_user, update_user_profile, change_password,
    get_all_users, get_pending_users, approve_user, suspend_user, ban_user,
    update_user_role, update_user_api_limit, reset_user_api_usage,
    create_first_admin, check_admin_exists
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
# CSS 스타일
# ============================================

st.markdown("""
<style>
    /* 전체 배경 */
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    
    /* 로그인 카드 */
    .login-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 40px;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        max-width: 400px;
        margin: 50px auto;
    }
    
    /* 제목 스타일 */
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
    
    /* 상태 배지 */
    .status-badge {
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    
    .status-pending {
        background: #ffc107;
        color: #000;
    }
    
    .status-approved {
        background: #28a745;
        color: #fff;
    }
    
    .status-suspended {
        background: #dc3545;
        color: #fff;
    }
    
    /* 역할 배지 */
    .role-badge {
        padding: 3px 10px;
        border-radius: 10px;
        font-size: 0.8rem;
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
if 'page' not in st.session_state:
    st.session_state.page = "login"

# ============================================
# 데이터베이스 초기화
# ============================================

@st.cache_resource
def initialize_database():
    """앱 시작 시 DB 초기화"""
    init_db()
    return True

# DB 초기화 실행
db_initialized = initialize_database()

# ============================================
# 로그인 페이지
# ============================================

def show_login_page():
    """로그인 화면"""
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<h1 class="main-title">🔮 PDF 자동 생성 플랫폼</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">사주 · 타로 · 연애</p>', unsafe_allow_html=True)
        
        # 탭: 로그인 / 회원가입
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
        
        # 관리자 계정 생성 (최초 1회)
        st.markdown("---")
        
        if not check_admin_exists():
            with st.expander("🔧 최초 관리자 설정"):
                st.warning("아직 관리자가 없습니다. 첫 번째 관리자를 설정해주세요.")
                
                admin_name = st.text_input("관리자 이름", key="admin_name")
                admin_email = st.text_input("관리자 이메일", key="admin_email")
                admin_password = st.text_input("관리자 비밀번호", type="password", key="admin_password")
                
                if st.button("관리자 계정 생성", type="secondary"):
                    if all([admin_name, admin_email, admin_password]):
                        result = create_first_admin(admin_email, admin_password, admin_name)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["error"])
                    else:
                        st.error("모든 필드를 입력해주세요.")


# ============================================
# 메인 앱 (로그인 후)
# ============================================

def show_main_app():
    """메인 애플리케이션"""
    
    user = st.session_state.user
    
    # 사이드바
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}님")
        
        # 등급 표시
        role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
        role_color = {1: "role-1", 2: "role-2", 3: "role-3"}
        st.markdown(
            f'<span class="role-badge {role_color[user["role"]]}">{role_text[user["role"]]}</span>',
            unsafe_allow_html=True
        )
        
        st.markdown("---")
        
        # 메뉴
        menu_options = ["📄 PDF 생성", "👤 MyPage", "📢 공지사항"]
        
        # 등급별 추가 메뉴
        if user["role"] >= 1:
            menu_options.insert(1, "📋 목차/지침/속지 관리")
        
        if user["role"] >= 2:
            menu_options.insert(-1, "✏️ 공지 작성")
        
        if user["role"] == 3:
            menu_options.insert(0, "⚙️ 관리자 설정")
            menu_options.insert(1, "👥 회원 관리")
        
        selected_menu = st.radio("메뉴", menu_options, label_visibility="collapsed")
        
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
    else:
        show_pdf_generation()


# ============================================
# 관리자 설정 페이지
# ============================================

def show_admin_settings():
    """관리자 설정 페이지"""
    st.title("⚙️ 관리자 설정")
    
    st.info("🚧 2단계에서 구현 예정: 서비스 추가, 시스템 설정 등")
    
    # 관리자 API 키 설정
    st.markdown("### 🔑 관리자 API 설정")
    
    admin_api_key = st.text_input(
        "OpenAI API 키 (공유용)",
        type="password",
        help="회원들이 '관리자 API 사용'을 선택했을 때 사용되는 키입니다."
    )
    
    if st.button("API 키 저장"):
        # TODO: 시스템 설정 테이블에 저장
        st.success("API 키가 저장되었습니다.")


# ============================================
# 회원 관리 페이지
# ============================================

def show_user_management():
    """회원 관리 페이지"""
    st.title("👥 회원 관리")
    
    tab1, tab2 = st.tabs(["📋 전체 회원", "⏳ 승인 대기"])
    
    with tab1:
        st.markdown("### 전체 회원 목록")
        
        users = get_all_users()
        
        if not users:
            st.info("등록된 회원이 없습니다.")
        else:
            for user in users:
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 2])
                    
                    with col1:
                        st.write(f"**{user['name']}**")
                        st.caption(user['email'])
                    
                    with col2:
                        status_text = {
                            "pending": "⏳ 대기",
                            "approved": "✅ 승인",
                            "suspended": "⛔ 중지",
                            "banned": "❌ 강퇴"
                        }
                        st.write(status_text.get(user['status'], user['status']))
                    
                    with col3:
                        role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
                        st.write(role_text.get(user['role'], user['role']))
                    
                    with col4:
                        st.write(f"API: {user['api_usage_count']}/{user['api_usage_limit']}")
                    
                    with col5:
                        # 현재 로그인한 사용자는 본인 수정 불가
                        if user['id'] != st.session_state.user['id']:
                            col_a, col_b, col_c = st.columns(3)
                            
                            with col_a:
                                new_role = st.selectbox(
                                    "등급",
                                    [1, 2, 3],
                                    index=user['role'] - 1,
                                    key=f"role_{user['id']}",
                                    label_visibility="collapsed"
                                )
                                if new_role != user['role']:
                                    if st.button("변경", key=f"role_btn_{user['id']}"):
                                        result = update_user_role(user['id'], new_role)
                                        if result["success"]:
                                            st.success(result["message"])
                                            st.rerun()
                            
                            with col_b:
                                if user['status'] == "approved":
                                    if st.button("중지", key=f"suspend_{user['id']}"):
                                        result = suspend_user(user['id'])
                                        st.rerun()
                                elif user['status'] == "suspended":
                                    if st.button("복구", key=f"restore_{user['id']}"):
                                        result = approve_user(user['id'])
                                        st.rerun()
                            
                            with col_c:
                                if st.button("🗑️", key=f"ban_{user['id']}", help="강퇴"):
                                    result = ban_user(user['id'])
                                    st.rerun()
                    
                    st.markdown("---")
    
    with tab2:
        st.markdown("### 승인 대기 회원")
        
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
                        result = approve_user(user['id'])
                        if result["success"]:
                            st.success(f"{user['name']}님이 승인되었습니다.")
                            st.rerun()
                
                st.markdown("---")


# ============================================
# 목차/지침/속지 관리 페이지
# ============================================

def show_content_management():
    """목차/지침/속지 관리"""
    st.title("📋 목차/지침/속지 관리")
    
    st.info("🚧 3단계에서 구현 예정: 서비스별 목차, 지침, 속지 CRUD")
    
    tab1, tab2, tab3 = st.tabs(["📑 목차 관리", "📜 지침 관리", "🖼️ 속지 관리"])
    
    with tab1:
        st.markdown("### 목차 설정")
        st.write("서비스별로 목차를 추가/삭제/수정할 수 있습니다.")
    
    with tab2:
        st.markdown("### 지침 설정")
        st.write("서비스별로 지침을 작성하고 관리할 수 있습니다.")
    
    with tab3:
        st.markdown("### 속지 설정")
        st.write("표지, 본문 배경, 소개, 안내 이미지를 관리합니다.")


# ============================================
# PDF 생성 페이지
# ============================================

def show_pdf_generation():
    """PDF 생성 페이지"""
    st.title("📄 PDF 생성")
    
    st.info("🚧 4단계에서 구현 예정: 서비스 선택, 고객 업로드, PDF 생성, 발송")
    
    # 서비스 선택 (중복 가능)
    st.markdown("### 📌 서비스 선택")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        saju = st.checkbox("🔮 사주")
    with col2:
        tarot = st.checkbox("🃏 타로")
    with col3:
        love = st.checkbox("💕 연애")
    
    # 폰트 설정
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
    
    # 고객 파일 업로드
    st.markdown("### 📁 고객 파일")
    uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx", "xls"])
    
    # 작업 시작 버튼
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 PDF 생성 시작", type="primary", use_container_width=True):
            st.warning("4단계에서 구현됩니다.")
    
    with col2:
        send_method = st.radio(
            "발송 방법",
            ["📧 이메일 자동발송", "💬 카톡 알림"],
            horizontal=True
        )


# ============================================
# MyPage
# ============================================

def show_mypage():
    """마이페이지"""
    st.title("👤 MyPage")
    
    user = st.session_state.user
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 내 정보")
        
        # 등급 표시
        role_text = {1: "1단계 (기본)", 2: "2단계 (공지작성)", 3: "3단계 (관리자)"}
        st.info(f"**등급:** {role_text.get(user['role'], user['role'])}")
        
        # 정보 수정
        new_name = st.text_input("이름", value=user['name'])
        st.text_input("이메일 (변경 불가)", value=user['email'], disabled=True)
        
        st.markdown("---")
        
        # 비밀번호 변경
        st.markdown("### 🔒 비밀번호 변경")
        old_pw = st.text_input("현재 비밀번호", type="password")
        new_pw = st.text_input("새 비밀번호", type="password")
        new_pw2 = st.text_input("새 비밀번호 확인", type="password")
        
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
        
        # API 선택
        use_admin_api = st.radio(
            "API 키 선택",
            ["관리자 API 사용", "내 API 사용"],
            index=0 if user.get('use_admin_api', True) else 1
        )
        
        if use_admin_api == "내 API 사용":
            my_api_key = st.text_input(
                "OpenAI API 키",
                value=user.get('api_key', '') or '',
                type="password"
            )
        else:
            st.info(f"API 사용량: {user.get('api_usage_count', 0)} / {user.get('api_usage_limit', 100)}")
        
        st.markdown("---")
        
        st.markdown("### 📧 이메일 설정")
        gmail_address = st.text_input(
            "Gmail 주소",
            value=user.get('gmail_address', '') or ''
        )
        gmail_password = st.text_input(
            "Gmail 앱 비밀번호",
            value=user.get('gmail_app_password', '') or '',
            type="password"
        )
        
        st.caption("Gmail 앱 비밀번호 발급: Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호")
        
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
                # 세션 업데이트
                st.session_state.user.update(update_data)
                st.success("설정이 저장되었습니다.")
            else:
                st.error(result["error"])


# ============================================
# 공지 작성
# ============================================

def show_notice_write():
    """공지 작성 페이지"""
    st.title("✏️ 공지 작성")
    
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
    """공지사항 목록"""
    st.title("📢 공지사항")
    
    st.info("🚧 6단계에서 구현 예정")
    
    # 샘플 공지
    st.markdown("""
    ### 📌 시스템 오픈 안내
    *2024-01-15*
    
    안녕하세요. PDF 자동 생성 플랫폼이 오픈되었습니다.
    
    ---
    """)


# ============================================
# 메인 실행
# ============================================

def main():
    # DB 연결 확인
    if not os.environ.get("DATABASE_URL"):
        st.error("⚠️ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        st.info("""
        **Railway 배포 시:**
        1. Railway에서 PostgreSQL 추가
        2. 앱 Settings → Variables에서 DATABASE_URL 확인
        
        **로컬 테스트 시:**
        ```
        export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
        ```
        """)
        
        # 로컬 테스트용 임시 로그인
        st.markdown("---")
        st.markdown("### 🧪 로컬 테스트 모드")
        if st.button("테스트 로그인 (DB 없이)"):
            st.session_state.logged_in = True
            st.session_state.user = {
                "id": 1,
                "email": "test@test.com",
                "name": "테스트 관리자",
                "role": 3,
                "status": "approved",
                "api_key": None,
                "use_admin_api": True,
                "api_usage_count": 0,
                "api_usage_limit": 100,
                "gmail_address": None,
                "gmail_app_password": None,
            }
            st.rerun()
        return
    
    # 로그인 체크
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()


if __name__ == "__main__":
    main()
