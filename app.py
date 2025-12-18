# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
6단계 (최종): 공지사항 기능 완성
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from database import init_db, SessionLocal, UserRole
from auth import (
    register_user, login_user, update_user_profile, change_password,
    get_all_users, get_pending_users, approve_user, suspend_user, ban_user,
    update_user_role, create_first_admin, check_admin_exists
)
from services import (
    get_all_services, get_service_by_id, add_service, update_service,
    delete_service, restore_service,
    get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, delete_chapter,
    get_guidelines_by_service, add_guideline, delete_guideline,
    get_templates_by_service, add_template, delete_template,
    TEMPLATE_TYPES
)
from pdf_generator import generate_combined_pdf
from notification import send_email_with_pdf
from notices import (
    get_all_notices, get_notice_by_id, create_notice, update_notice,
    delete_notice, toggle_pin_notice, get_recent_notices
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
    .notice-card { background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin: 10px 0; }
    .notice-pinned { border-left: 4px solid #ffc107; }
    .notice-title { font-size: 1.2rem; font-weight: bold; margin-bottom: 5px; }
    .notice-meta { font-size: 0.85rem; color: #888; }
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
if 'view_notice_id' not in st.session_state:
    st.session_state.view_notice_id = None

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

def save_uploaded_file(uploaded_file, prefix: str) -> str:
    if uploaded_file is None:
        return None
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
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
    user = st.session_state.user
    user_gmail = user.get('gmail_address', '')
    user_gmail_pw = user.get('gmail_app_password', '')
    if user_gmail and user_gmail_pw:
        return {"email": user_gmail, "password": user_gmail_pw, "source": "개인"}
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
        
        # 최근 공지사항 표시
        recent_notices = get_recent_notices(3)
        if recent_notices:
            st.markdown("### 📢 공지사항")
            for notice in recent_notices:
                pin_icon = "📌 " if notice['is_pinned'] else ""
                st.markdown(f"- {pin_icon}**{notice['title']}** ({notice['created_at']})")
            st.markdown("---")
        
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
    
    tab1, tab2, tab3 = st.tabs(["🔑 API", "📧 이메일", "💬 카카오"])
    
    with tab1:
        current_api = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
        admin_api = st.text_input("OpenAI API 키", value=current_api, type="password")
        current_limit = get_system_config(ConfigKeys.DEFAULT_API_LIMIT, "100")
        default_limit = st.number_input("기본 한도", min_value=10, value=int(current_limit))
        if st.button("저장", key="save_api", type="primary"):
            set_system_config(ConfigKeys.ADMIN_API_KEY, admin_api)
            set_system_config(ConfigKeys.DEFAULT_API_LIMIT, str(default_limit))
            st.success("✅ 저장됨")
    
    with tab2:
        current_gmail = get_system_config(ConfigKeys.ADMIN_GMAIL, "")
        current_pw = get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, "")
        gmail = st.text_input("Gmail", value=current_gmail)
        gmail_pw = st.text_input("앱 비밀번호", value=current_pw, type="password")
        if st.button("저장", key="save_email", type="primary"):
            set_system_config(ConfigKeys.ADMIN_GMAIL, gmail)
            set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, gmail_pw)
            st.success("✅ 저장됨")
    
    with tab3:
        current_kakao = get_system_config(ConfigKeys.KAKAO_CHANNEL_ID, "")
        kakao = st.text_input("카카오 채널 ID", value=current_kakao)
        if st.button("저장", key="save_kakao", type="primary"):
            set_system_config(ConfigKeys.KAKAO_CHANNEL_ID, kakao)
            st.success("✅ 저장됨")

# ============================================
# 서비스/회원/콘텐츠 관리 (간소화)
# ============================================

def show_service_management():
    st.title("📦 서비스 관리")
    if not require_permission(3):
        return
    
    tab1, tab2 = st.tabs(["목록", "추가"])
    with tab1:
        for s in get_all_services(include_inactive=True):
            if s['is_active']:
                col1, col2 = st.columns([5, 1])
                col1.write(f"**{s['name']}** - {s['description'] or ''}")
                if col2.button("🗑️", key=f"ds_{s['id']}"):
                    delete_service(s['id'])
                    st.rerun()
    with tab2:
        name = st.text_input("이름")
        desc = st.text_area("설명")
        if st.button("추가", type="primary") and name:
            add_service(name, desc)
            st.rerun()

def show_user_management():
    st.title("👥 회원 관리")
    if not require_permission(3):
        return
    
    tab1, tab2 = st.tabs(["전체", "대기"])
    with tab1:
        for u in get_all_users():
            st.write(f"**{u['name']}** ({u['email']}) - {u['status']}")
    with tab2:
        for u in get_pending_users():
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{u['name']}** ({u['email']})")
            if col2.button("승인", key=f"ap_{u['id']}", type="primary"):
                approve_user(u['id'])
                st.rerun()

def show_content_management():
    st.title("📋 목차/지침/속지 관리")
    if not require_permission(1):
        return
    
    services = get_all_services()
    if not services:
        st.warning("서비스 없음")
        return
    
    sel = st.selectbox("서비스", [s['name'] for s in services])
    sid = next((s['id'] for s in services if s['name'] == sel), None)
    if not sid:
        return
    
    tab1, tab2, tab3 = st.tabs(["목차", "지침", "속지"])
    
    with tab1:
        with st.expander("➕ 추가"):
            t = st.text_input("제목", key="ch_t")
            if st.button("추가", key="ch_add") and t:
                add_chapter(sid, t)
                st.rerun()
        for c in get_chapters_by_service(sid):
            col1, col2 = st.columns([5, 1])
            col1.write(f"{c['order']}. {c['title']}")
            if col2.button("🗑️", key=f"dc_{c['id']}"):
                delete_chapter(c['id'])
                st.rerun()
    
    with tab2:
        with st.expander("➕ 추가"):
            t = st.text_input("제목", key="g_t")
            c = st.text_area("내용", key="g_c")
            if st.button("추가", key="g_add") and t and c:
                add_guideline(sid, t, c)
                st.rerun()
        for g in get_guidelines_by_service(sid):
            with st.expander(g['title']):
                st.write(g['content'][:200] + "...")
                if st.button("삭제", key=f"dg_{g['id']}"):
                    delete_guideline(g['id'])
                    st.rerun()
    
    with tab3:
        with st.expander("➕ 추가"):
            tt = st.selectbox("유형", list(TEMPLATE_TYPES.keys()), format_func=lambda x: TEMPLATE_TYPES[x])
            tn = st.text_input("이름", key="t_n")
            tf = st.file_uploader("이미지", type=["jpg", "png"])
            if st.button("추가", key="t_add") and tn:
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
    
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ API 키 필요")
        return
    
    services = get_all_services()
    if not services:
        st.warning("서비스 없음")
        return
    
    # 1. 서비스 선택
    st.markdown("### 1. 서비스 선택")
    sel_ids = []
    cols = st.columns(len(services))
    for i, s in enumerate(services):
        if cols[i].checkbox(s['name'], key=f"sv_{s['id']}"):
            sel_ids.append(s['id'])
    
    if not sel_ids:
        return
    
    # 2. 문서 설정
    st.markdown("### 2. 문서 설정")
    c1, c2, c3, c4 = st.columns(4)
    font = c1.selectbox("폰트", ["나눔고딕", "나눔명조"])
    size = c2.number_input("크기", 10, 24, 14)
    spacing = c3.number_input("자간", -5, 10, 0)
    height = c4.number_input("행간", 15, 50, 24)
    font_set = {"font": font, "size": size, "letter_spacing": spacing, "line_height": height}
    
    # 3. 목차/지침 선택
    st.markdown("### 3. 설정")
    svc_data = []
    for sid in sel_ids:
        svc = get_service_by_id(sid)
        if not svc:
            continue
        with st.expander(f"📌 {svc['name']}"):
            chs = get_chapters_by_service(sid)
            sel_chs = st.multiselect("목차", [c['title'] for c in chs], default=[c['title'] for c in chs], key=f"chs_{sid}") if chs else []
            gds = get_guidelines_by_service(sid)
            gd_content = ""
            if gds:
                sel_gd = st.selectbox("지침", [g['title'] for g in gds], key=f"gd_{sid}")
                gd_content = next((g['content'] for g in gds if g['title'] == sel_gd), "")
            svc_data.append({"service_id": sid, "service_name": svc['name'], "chapters": sel_chs, "guideline": gd_content,
                           "cover_image": None, "intro_image": None, "background_image": None, "info_image": None})
    
    # 4. 고객 파일
    st.markdown("### 4. 고객 파일")
    file = st.file_uploader("엑셀", type=["xlsx", "xls"])
    if file:
        df = pd.read_excel(file)
        st.session_state.customers_df = df
        st.success(f"✅ {len(df)}명")
    
    # 5. 생성
    if st.session_state.customers_df is not None:
        df = st.session_state.customers_df
        st.markdown("### 5. 생성")
        
        mode = st.radio("방식", ["전체", "선택"], horizontal=True)
        name_col = next((c for c in ['이름', 'name', 'Name'] if c in df.columns), df.columns[0])
        email_col = next((c for c in ['이메일', 'email', 'Email'] if c in df.columns), None)
        
        sel_idx = list(range(len(df))) if mode == "전체" else [i for i in range(len(df)) if st.checkbox(str(df.iloc[i][name_col]), key=f"c_{i}")]
        
        auto_send = st.checkbox("자동 발송")
        
        if st.button("🚀 생성", type="primary", use_container_width=True):
            if not sel_idx:
                st.error("고객 선택 필요")
                return
            
            prog = st.progress(0)
            stat = st.empty()
            results = []
            svc_names = "+".join([s['service_name'] for s in svc_data])
            email_cfg = get_email_config()
            
            for i, idx in enumerate(sel_idx):
                row = df.iloc[idx]
                name = str(row[name_col])
                email = str(row[email_col]) if email_col else ""
                stat.text(f"📝 {name} 생성중...")
                
                try:
                    pdf = generate_combined_pdf(api_key, dict(row), svc_data, font_set,
                                               lambda p, m: prog.progress((i + p) / len(sel_idx)))
                    fname = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                    fpath = os.path.join(OUTPUT_DIR, fname)
                    with open(fpath, "wb") as f:
                        f.write(pdf)
                    
                    sent = False
                    if auto_send and email and email_cfg:
                        r = send_email_with_pdf(email_cfg['email'], email_cfg['password'], email, name, svc_names, fpath)
                        sent = r['success']
                    
                    results.append({"name": name, "email": email, "file": fname, "path": fpath, "bytes": pdf, "sent": sent})
                except Exception as e:
                    st.error(f"❌ {name}: {e}")
            
            prog.progress(1.0)
            stat.text("✅ 완료!")
            st.session_state.generated_pdfs = results
            
            st.markdown("### 📥 결과")
            for r in results:
                c1, c2 = st.columns([4, 1])
                c1.write(f"{'✅' if r['sent'] else '⏳'} **{r['name']}**")
                c2.download_button("📥", r['bytes'], r['file'], "application/pdf", key=f"dl_{r['file']}")

# ============================================
# 공지 작성 (6단계 핵심!)
# ============================================

def show_notice_write():
    st.title("✏️ 공지 작성")
    
    if not require_permission(2):
        return
    
    user = st.session_state.user
    
    tab1, tab2 = st.tabs(["📝 새 공지 작성", "📋 내 공지 관리"])
    
    with tab1:
        st.markdown("### 새 공지사항 작성")
        
        title = st.text_input("제목", placeholder="공지사항 제목을 입력하세요")
        content = st.text_area("내용", height=300, placeholder="공지사항 내용을 입력하세요")
        
        col1, col2 = st.columns(2)
        with col1:
            image_file = st.file_uploader("이미지 첨부 (선택)", type=["jpg", "jpeg", "png", "gif"])
        with col2:
            is_pinned = st.checkbox("📌 상단 고정", value=False)
        
        if st.button("공지 등록", type="primary", use_container_width=True):
            if not title:
                st.error("제목을 입력해주세요.")
            elif not content:
                st.error("내용을 입력해주세요.")
            else:
                # 이미지 저장
                image_path = None
                if image_file:
                    image_path = save_uploaded_file(image_file, "notice")
                
                result = create_notice(
                    author_id=user['id'],
                    title=title,
                    content=content,
                    image_path=image_path,
                    is_pinned=is_pinned
                )
                
                if result["success"]:
                    st.success("✅ 공지사항이 등록되었습니다!")
                    st.rerun()
                else:
                    st.error(result["error"])
    
    with tab2:
        st.markdown("### 내가 작성한 공지")
        
        all_notices = get_all_notices()
        my_notices = [n for n in all_notices if n['author_id'] == user['id']]
        
        if not my_notices:
            st.info("작성한 공지사항이 없습니다.")
        else:
            for notice in my_notices:
                with st.expander(f"{'📌 ' if notice['is_pinned'] else ''}{notice['title']} ({notice['created_at']})"):
                    # 수정 폼
                    edit_title = st.text_input("제목", value=notice['title'], key=f"edit_t_{notice['id']}")
                    edit_content = st.text_area("내용", value=notice['content'], height=200, key=f"edit_c_{notice['id']}")
                    edit_pinned = st.checkbox("📌 상단 고정", value=notice['is_pinned'], key=f"edit_p_{notice['id']}")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("💾 수정", key=f"save_{notice['id']}", type="primary"):
                            result = update_notice(
                                notice['id'],
                                title=edit_title,
                                content=edit_content,
                                is_pinned=edit_pinned
                            )
                            if result["success"]:
                                st.success("수정되었습니다.")
                                st.rerun()
                    
                    with col2:
                        if st.button("📌 고정 토글", key=f"pin_{notice['id']}"):
                            toggle_pin_notice(notice['id'])
                            st.rerun()
                    
                    with col3:
                        if st.button("🗑️ 삭제", key=f"del_{notice['id']}"):
                            delete_notice(notice['id'])
                            st.rerun()

# ============================================
# 공지사항 목록/상세 (6단계 핵심!)
# ============================================

def show_notices():
    st.title("📢 공지사항")
    
    # 상세 보기 모드
    if st.session_state.view_notice_id:
        notice = get_notice_by_id(st.session_state.view_notice_id)
        
        if notice:
            # 뒤로가기 버튼
            if st.button("← 목록으로"):
                st.session_state.view_notice_id = None
                st.rerun()
            
            st.markdown("---")
            
            # 제목
            pin_icon = "📌 " if notice['is_pinned'] else ""
            st.markdown(f"## {pin_icon}{notice['title']}")
            
            # 메타 정보
            st.caption(f"작성자: {notice['author_name']} | 작성일: {notice['created_at']}")
            
            st.markdown("---")
            
            # 이미지
            if notice['image_path'] and os.path.exists(notice['image_path']):
                st.image(notice['image_path'], use_column_width=True)
            
            # 내용
            st.markdown(notice['content'])
            
            st.markdown("---")
            
            # 수정일
            if notice['updated_at'] != notice['created_at']:
                st.caption(f"최종 수정: {notice['updated_at']}")
        else:
            st.error("공지사항을 찾을 수 없습니다.")
            st.session_state.view_notice_id = None
        
        return
    
    # 목록 보기 모드
    notices = get_all_notices()
    
    if not notices:
        st.info("등록된 공지사항이 없습니다.")
        return
    
    # 고정 공지
    pinned = [n for n in notices if n['is_pinned']]
    normal = [n for n in notices if not n['is_pinned']]
    
    if pinned:
        st.markdown("### 📌 고정 공지")
        for notice in pinned:
            col1, col2 = st.columns([5, 1])
            with col1:
                if st.button(f"📌 **{notice['title']}**", key=f"view_p_{notice['id']}", use_container_width=True):
                    st.session_state.view_notice_id = notice['id']
                    st.rerun()
            with col2:
                st.caption(notice['created_at'][:10])
        
        st.markdown("---")
    
    # 일반 공지
    if normal:
        st.markdown("### 📋 전체 공지")
        for notice in normal:
            col1, col2 = st.columns([5, 1])
            with col1:
                if st.button(notice['title'], key=f"view_n_{notice['id']}", use_container_width=True):
                    st.session_state.view_notice_id = notice['id']
                    st.rerun()
            with col2:
                st.caption(notice['created_at'][:10])

# ============================================
# MyPage
# ============================================

def show_mypage():
    st.title("👤 MyPage")
    user = st.session_state.user
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 내 정보")
        st.info(f"등급: {['', '1단계', '2단계', '관리자'][user['role']]}")
        new_name = st.text_input("이름", value=user['name'])
        st.text_input("이메일", value=user['email'], disabled=True)
        
        st.markdown("### 🔒 비밀번호")
        old_pw = st.text_input("현재", type="password", key="op")
        new_pw = st.text_input("새 비밀번호", type="password", key="np")
        if st.button("변경") and old_pw and new_pw:
            r = change_password(user['id'], old_pw, new_pw)
            st.success("변경됨") if r["success"] else st.error(r["error"])
    
    with col2:
        st.markdown("### 🔑 API")
        use_admin = st.radio("선택", ["관리자 API", "내 API"], index=0 if user.get('use_admin_api', True) else 1)
        my_api = st.text_input("API 키", value=user.get('api_key', '') or '', type="password") if use_admin == "내 API" else ""
        
        st.markdown("### 📧 이메일")
        gmail = st.text_input("Gmail", value=user.get('gmail_address', '') or '')
        gmail_pw = st.text_input("앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
        
        if st.button("💾 저장", type="primary", use_container_width=True):
            data = {'name': new_name, 'use_admin_api': use_admin == "관리자 API", 'gmail_address': gmail, 'gmail_app_password': gmail_pw}
            if use_admin == "내 API":
                data['api_key'] = my_api
            r = update_user_profile(user['id'], **data)
            if r["success"]:
                st.session_state.user.update(data)
                st.success("저장됨")

# ============================================
# 메인
# ============================================

def main():
    if not os.environ.get("DATABASE_URL"):
        st.error("⚠️ DATABASE_URL 필요")
        if st.button("테스트 로그인"):
            st.session_state.logged_in = True
            st.session_state.user = {"id": 1, "email": "test@test.com", "name": "테스트 관리자",
                "role": 3, "status": "approved", "api_key": None, "use_admin_api": True,
                "api_usage_count": 0, "api_usage_limit": 100, "gmail_address": None, "gmail_app_password": None}
            st.rerun()
        return
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
