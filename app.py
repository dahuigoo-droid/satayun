# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
UI 개선 버전
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO

# 페이지 설정
st.set_page_config(
    page_title="PDF 자동 생성 플랫폼",
    page_icon="🔮",
    layout="wide"
)

# ============================================
# 임포트
# ============================================

from database import init_db, SessionLocal
from auth import (
    register_user, login_user, update_user_profile, change_password,
    get_all_users, get_pending_users, approve_user, suspend_user, activate_user,
    update_user_settings, create_first_admin, check_admin_exists
)
from services import (
    get_all_services, get_admin_services, get_user_services,
    add_service, delete_service, get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, delete_chapter,
    get_guidelines_by_service, add_guideline, update_guideline,
    get_templates_by_service, add_template, delete_template
)
from notices import get_all_notices, create_notice, update_notice, delete_notice, toggle_pin_notice

# ============================================
# CSS
# ============================================

st.markdown("""
<style>
    .main-title { text-align: center; color: #fff; font-size: 2.5rem; margin-bottom: 10px; }
    .sub-title { text-align: center; color: #888; font-size: 1rem; margin-bottom: 30px; }
    
    /* 사이드바 라디오 버튼 숨기기 */
    section[data-testid="stSidebar"] .stRadio > div > label > div:first-child {
        display: none !important;
    }
    section[data-testid="stSidebar"] .stRadio > div > label {
        cursor: pointer !important;
        padding: 10px 15px;
        border-radius: 8px;
        margin: 2px 0;
    }
    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(255,255,255,0.1);
    }
    
    /* 섹션 제목 */
    .section-title {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 8px 20px;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        font-size: 1rem;
        margin: 15px 0 10px 0;
    }
    
    /* 구분선 */
    .divider {
        border-top: 1px solid rgba(255,255,255,0.1);
        margin: 20px 0;
    }
    
    /* 등급 배지 */
    .badge-admin { background: #dc3545; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level1 { background: #6c757d; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level2 { background: #17a2b8; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level3 { background: #28a745; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    
    /* 완료 배지 */
    .badge-done { background: #28a745; color: white; padding: 3px 10px; border-radius: 10px; font-size: 0.8rem; }
    
    /* 큰 텍스트 영역 */
    .stTextArea textarea {
        min-height: 200px !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# 세션 상태 초기화
# ============================================

defaults = {
    'logged_in': False,
    'user': None,
    'customers_df': None,
    'completed_customers': {},
    'generated_pdfs': {},
    'selected_product_type': 'ready',
    'selected_service_id': None,
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

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

TEMPLATE_TYPES = {"cover": "📕 표지", "background": "📄 내지", "info": "📋 안내지"}

# ============================================
# 유틸리티
# ============================================

def is_admin() -> bool:
    return st.session_state.user and st.session_state.user.get('is_admin', False)

def get_member_level() -> int:
    if not st.session_state.user:
        return 1
    return st.session_state.user.get('member_level', 1)

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
    admin_api = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
    
    if user.get('api_mode') == 'separated' and user.get('api_key'):
        return user['api_key']
    return admin_api

def play_sound():
    """완료 시 종소리"""
    st.markdown("""
    <audio autoplay>
        <source src="https://www.soundjay.com/buttons/sounds/button-09.mp3" type="audio/mpeg">
    </audio>
    """, unsafe_allow_html=True)

def verify_pdf_generation_ready(service_id: int, api_key: str) -> tuple:
    """PDF 생성 가능 여부 검증"""
    errors = []
    
    # API 키 확인
    if not api_key:
        errors.append("❌ API 키가 설정되지 않았습니다.")
    
    # 서비스 확인
    if not service_id:
        errors.append("❌ 상품이 선택되지 않았습니다.")
        return False, errors
    
    # 목차 확인
    chapters = get_chapters_by_service(service_id)
    if not chapters:
        errors.append("❌ 목차가 등록되지 않았습니다.")
    
    # 지침 확인
    guidelines = get_guidelines_by_service(service_id)
    if not guidelines:
        errors.append("⚠️ 지침이 없습니다. (기본 지침 사용)")
    
    if errors and any("❌" in e for e in errors):
        return False, errors
    
    return True, errors

# ============================================
# PDF 생성 함수
# ============================================

def generate_content_with_gpt(api_key: str, chapter_title: str, guideline: str, customer_data: dict) -> str:
    """GPT로 챕터 내용 생성"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        customer_info = "\n".join([f"- {k}: {v}" for k, v in customer_data.items()])
        
        prompt = f"""당신은 전문 운세 작성가입니다.

[고객 정보]
{customer_info}

[작성 지침]
{guideline}

[작성할 챕터]
{chapter_title}

위 정보를 바탕으로 '{chapter_title}' 챕터 내용을 작성해주세요.
- 고객 정보를 반영하여 개인화된 내용
- 긍정적이고 희망적인 톤
- 300-500자 분량
- 마크다운 없이 순수 텍스트"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[내용 생성 오류: {str(e)}]"


def create_pdf_document(customer_name: str, chapters_content: list, templates: dict, font_size: int = 12) -> bytes:
    """PDF 문서 생성"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.lib.colors import black
        
        buffer = BytesIO()
        page_width, page_height = A4
        
        # 마진 설정
        left_margin = 25*mm
        right_margin = 25*mm
        top_margin = 30*mm
        bottom_margin = 30*mm
        
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=left_margin, rightMargin=right_margin,
            topMargin=top_margin, bottomMargin=bottom_margin
        )
        
        # 사용 가능한 영역 계산
        available_width = page_width - left_margin - right_margin
        available_height = page_height - top_margin - bottom_margin
        
        # 이미지 크기 (마진 고려하여 약간 작게)
        img_width = available_width - 10*mm
        img_height = available_height - 20*mm
        
        # 스타일
        title_style = ParagraphStyle('Title', fontSize=24, alignment=TA_CENTER, 
                                     spaceAfter=30, textColor=black, fontName='Helvetica-Bold')
        chapter_style = ParagraphStyle('Chapter', fontSize=16, spaceBefore=20, 
                                       spaceAfter=15, textColor=black, fontName='Helvetica-Bold')
        body_style = ParagraphStyle('Body', fontSize=font_size, leading=font_size*1.5,
                                    alignment=TA_JUSTIFY, spaceAfter=12, textColor=black)
        page_style = ParagraphStyle('Page', fontSize=10, alignment=TA_CENTER, textColor=black)
        
        story = []
        
        # ===== 표지 =====
        cover_path = templates.get('cover')
        if cover_path and os.path.exists(cover_path):
            try:
                img = Image(cover_path, width=img_width, height=img_height)
                img.hAlign = 'CENTER'
                story.append(img)
            except:
                story.append(Spacer(1, 80*mm))
                story.append(Paragraph(f"🔮 {customer_name}님의 운세", title_style))
        else:
            story.append(Spacer(1, 80*mm))
            story.append(Paragraph(f"🔮 {customer_name}님의 운세", title_style))
            story.append(Spacer(1, 20*mm))
            story.append(Paragraph(datetime.now().strftime("%Y년 %m월 %d일"), 
                                  ParagraphStyle('Date', fontSize=14, alignment=TA_CENTER)))
        
        story.append(PageBreak())
        
        # ===== 본문 =====
        for idx, chapter in enumerate(chapters_content):
            safe_title = chapter['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f"📌 {safe_title}", chapter_style))
            
            content = chapter['content']
            for para in content.split('\n'):
                if para.strip():
                    safe_para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_para, body_style))
            
            story.append(Spacer(1, 10*mm))
            story.append(Paragraph(f"- {idx + 2} -", page_style))
            
            if idx < len(chapters_content) - 1:
                story.append(PageBreak())
        
        # ===== 안내지 =====
        story.append(PageBreak())
        info_path = templates.get('info')
        if info_path and os.path.exists(info_path):
            try:
                img = Image(info_path, width=img_width, height=img_height)
                img.hAlign = 'CENTER'
                story.append(img)
            except:
                story.append(Spacer(1, 80*mm))
                story.append(Paragraph("감사합니다", title_style))
        else:
            story.append(Spacer(1, 80*mm))
            story.append(Paragraph("감사합니다", title_style))
        
        doc.build(story)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None


def generate_pdf_for_customer(customer_data: dict, service_id: int, font_size: int, api_key: str) -> bytes:
    """고객용 PDF 생성"""
    chapters = get_chapters_by_service(service_id)
    guidelines = get_guidelines_by_service(service_id)
    guideline_text = guidelines[0]['content'] if guidelines else "친절하고 긍정적인 톤으로 작성하세요."
    
    templates_list = get_templates_by_service(service_id)
    templates = {}
    for t in templates_list:
        if t.get('image_path') and os.path.exists(t['image_path']):
            templates[t['template_type']] = t['image_path']
    
    name_col = None
    for col in ['이름', 'name', 'Name', '성명', '고객명']:
        if col in customer_data:
            name_col = col
            break
    customer_name = customer_data.get(name_col, "고객") if name_col else "고객"
    
    chapters_content = []
    for ch in chapters:
        content = generate_content_with_gpt(api_key, ch['title'], guideline_text, customer_data)
        chapters_content.append({"title": ch['title'], "content": content})
    
    return create_pdf_document(customer_name, chapters_content, templates, font_size)

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
            pw = st.text_input("비밀번호", type="password", key="login_pw")
            
            if st.button("로그인", type="primary", use_container_width=True):
                if email and pw:
                    result = login_user(email, pw)
                    if result["success"]:
                        st.session_state.logged_in = True
                        st.session_state.user = result["user"]
                        st.rerun()
                    else:
                        st.error(result["error"])
        
        with tab2:
            name = st.text_input("이름", key="reg_name")
            email2 = st.text_input("이메일", key="reg_email")
            pw1 = st.text_input("비밀번호", type="password", key="reg_pw1")
            pw2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
            
            if st.button("회원가입", type="primary", use_container_width=True):
                if all([name, email2, pw1, pw2]):
                    if pw1 != pw2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        result = register_user(email2, pw1, name)
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["error"])
        
        st.markdown("---")
        
        if not check_admin_exists():
            with st.expander("🔧 최초 관리자 설정", expanded=True):
                st.warning("⚠️ 관리자 계정을 먼저 생성하세요!")
                a_name = st.text_input("관리자 이름", key="a_name")
                a_email = st.text_input("관리자 이메일", key="a_email")
                a_pw = st.text_input("관리자 비밀번호", type="password", key="a_pw")
                
                if st.button("🔑 관리자 계정 생성", type="primary", use_container_width=True):
                    if all([a_name, a_email, a_pw]):
                        result = create_first_admin(a_email, a_pw, a_name)
                        if result["success"]:
                            st.success("✅ 관리자 계정 생성됨! 로그인하세요.")
                            st.rerun()

# ============================================
# 메인 앱
# ============================================

def show_main_app():
    user = st.session_state.user
    
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}님")
        
        if user['is_admin']:
            st.markdown('<span class="badge-admin">관리자</span>', unsafe_allow_html=True)
        else:
            level = user.get('member_level', 1)
            if level == 1:
                st.markdown('<span class="badge-level1">1단계</span>', unsafe_allow_html=True)
            elif level == 2:
                st.markdown('<span class="badge-level2">2단계</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge-level3">3단계</span>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        menu = []
        if user['is_admin']:
            menu.append("⚙️ 관리자 설정")
        menu.extend(["📦 서비스 작업", "👤 MyPage", "📢 공지사항"])
        
        selected = st.radio("메뉴", menu, label_visibility="collapsed")
        
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    if selected == "⚙️ 관리자 설정":
        show_admin_settings()
    elif selected == "📦 서비스 작업":
        show_service_work()
    elif selected == "👤 MyPage":
        show_mypage()
    elif selected == "📢 공지사항":
        show_notices()

# ============================================
# ⚙️ 관리자 설정
# ============================================

def show_admin_settings():
    st.title("⚙️ 관리자 설정")
    
    tab1, tab2, tab3 = st.tabs(["🔑 API/이메일", "👥 회원관리", "📦 기성상품 등록"])
    
    # ===== API/이메일 =====
    with tab1:
        st.markdown('<span class="section-title">🔑 관리자 API/이메일</span>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            api = st.text_input("OpenAI API 키", value=get_system_config(ConfigKeys.ADMIN_API_KEY, ""), type="password")
            if st.button("💾 API 저장"):
                set_system_config(ConfigKeys.ADMIN_API_KEY, api)
                st.success("저장됨")
        
        with col2:
            gmail = st.text_input("Gmail", value=get_system_config(ConfigKeys.ADMIN_GMAIL, ""))
            gmail_pw = st.text_input("앱 비밀번호", value=get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, ""), type="password")
            if st.button("💾 이메일 저장"):
                set_system_config(ConfigKeys.ADMIN_GMAIL, gmail)
                set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, gmail_pw)
                st.success("저장됨")
    
    # ===== 회원관리 =====
    with tab2:
        st.markdown('<span class="section-title">👥 회원 관리</span>', unsafe_allow_html=True)
        
        st.markdown("""
        **회원 등급 설명:**
        - **1단계**: 기성상품만 사용
        - **2단계**: 개별상품만 사용  
        - **3단계**: 둘 다 사용
        """)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        subtab1, subtab2 = st.tabs(["전체 회원", "승인 대기"])
        
        with subtab1:
            users = get_all_users()
            
            for u in users:
                if u['id'] == st.session_state.user['id']:
                    continue
                
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                
                with col1:
                    status_icon = "🟢" if u['status'] == 'approved' else "🔴"
                    admin_mark = "👑" if u['is_admin'] else ""
                    st.write(f"{status_icon} {admin_mark} **{u['name']}**")
                    st.caption(u['email'])
                
                with col2:
                    new_level = st.selectbox(
                        "등급",
                        [1, 2, 3],
                        index=u.get('member_level', 1) - 1,
                        format_func=lambda x: f"{x}단계",
                        key=f"lvl_{u['id']}"
                    )
                
                with col3:
                    new_api = st.selectbox(
                        "API",
                        ["unified", "separated"],
                        index=0 if u.get('api_mode') == 'unified' else 1,
                        format_func=lambda x: "통합" if x == "unified" else "분리",
                        key=f"api_{u['id']}"
                    )
                
                with col4:
                    new_email = st.selectbox(
                        "이메일",
                        ["unified", "separated"],
                        index=0 if u.get('email_mode') == 'unified' else 1,
                        format_func=lambda x: "통합" if x == "unified" else "분리",
                        key=f"email_{u['id']}"
                    )
                
                with col5:
                    if st.button("💾", key=f"save_{u['id']}"):
                        update_user_settings(u['id'], new_level, new_api, new_email)
                        st.success("저장")
                        st.rerun()
                    
                    if u['status'] == 'approved':
                        if st.button("🚫", key=f"sus_{u['id']}"):
                            suspend_user(u['id'])
                            st.rerun()
                    elif u['status'] == 'suspended':
                        if st.button("✅", key=f"act_{u['id']}"):
                            activate_user(u['id'])
                            st.rerun()
                
                st.markdown("---")
        
        with subtab2:
            pending = get_pending_users()
            if not pending:
                st.success("대기 중인 회원이 없습니다.")
            for u in pending:
                col1, col2 = st.columns([4, 1])
                col1.write(f"**{u['name']}** ({u['email']})")
                if col2.button("✅ 승인", key=f"ap_{u['id']}", type="primary"):
                    approve_user(u['id'])
                    st.rerun()
    
    # ===== 기성상품 등록 =====
    with tab3:
        st.markdown('<span class="section-title">📦 기성상품 등록</span>', unsafe_allow_html=True)
        
        with st.expander("➕ 새 기성상품 등록", expanded=False):
            product_name = st.text_input("상품명", key="new_prod")
            
            st.markdown("**📑 목차** (줄바꿈으로 구분)")
            new_chapters = st.text_area("목차 입력", height=250, key="new_ch",
                placeholder="1. 올해의 총운\n2. 재물운\n3. 건강운\n4. 연애운\n5. 직장운")
            
            st.markdown("**📜 AI 작성 지침**")
            new_guideline = st.text_area("지침 입력", height=250, key="new_g",
                placeholder="- 긍정적이고 희망적인 톤으로 작성\n- 각 목차당 300-500자 분량\n- 구체적인 조언 포함\n- 고객 정보를 자연스럽게 반영")
            
            st.markdown("**🎨 디자인**")
            d_cols = st.columns(3)
            with d_cols[0]:
                cover = st.file_uploader("📕 표지", type=["jpg","jpeg","png"], key="new_cover")
                if cover:
                    st.image(cover, width=100)
            with d_cols[1]:
                bg = st.file_uploader("📄 내지", type=["jpg","jpeg","png"], key="new_bg")
                if bg:
                    st.image(bg, width=100)
            with d_cols[2]:
                info = st.file_uploader("📋 안내지", type=["jpg","jpeg","png"], key="new_info")
                if info:
                    st.image(info, width=100)
            
            if st.button("💾 기성상품 등록", type="primary", use_container_width=True):
                if product_name:
                    result = add_service(product_name, "", None)
                    if result.get("success"):
                        svc_id = result["id"]
                        
                        if new_chapters:
                            for idx, ch in enumerate(new_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx+1)
                        
                        if new_guideline:
                            add_guideline(svc_id, f"{product_name} 지침", new_guideline)
                        
                        if cover:
                            path = save_uploaded_file(cover, f"{product_name}_cover")
                            add_template(svc_id, "cover", "표지", path)
                        if bg:
                            path = save_uploaded_file(bg, f"{product_name}_bg")
                            add_template(svc_id, "background", "내지", path)
                        if info:
                            path = save_uploaded_file(info, f"{product_name}_info")
                            add_template(svc_id, "info", "안내지", path)
                        
                        st.success(f"'{product_name}' 등록됨!")
                        st.rerun()
                else:
                    st.error("상품명을 입력하세요.")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("**등록된 기성상품**")
        
        services = get_admin_services()
        if not services:
            st.info("등록된 기성상품이 없습니다.")
        else:
            for svc in services:
                with st.expander(f"📌 {svc['name']}"):
                    chapters = get_chapters_by_service(svc['id'])
                    guidelines = get_guidelines_by_service(svc['id'])
                    templates = get_templates_by_service(svc['id'])
                    
                    st.markdown(f"**목차**: {len(chapters)}개")
                    if chapters:
                        for ch in chapters:
                            st.caption(f"  • {ch['title']}")
                    
                    st.markdown(f"**지침**: {'있음' if guidelines else '없음'}")
                    
                    st.markdown("**디자인**")
                    t_cols = st.columns(3)
                    for idx, tt in enumerate(["cover", "background", "info"]):
                        with t_cols[idx]:
                            t_list = [t for t in templates if t['template_type'] == tt]
                            if t_list and t_list[0].get('image_path') and os.path.exists(t_list[0]['image_path']):
                                st.image(t_list[0]['image_path'], width=80)
                            else:
                                st.caption(f"{TEMPLATE_TYPES[tt]}: 없음")
                    
                    if st.button("🗑️ 삭제", key=f"del_{svc['id']}"):
                        delete_service(svc['id'])
                        st.rerun()

# ============================================
# 📦 서비스 작업
# ============================================

def show_service_work():
    st.title("📦 서비스 작업")
    
    user = st.session_state.user
    level = user.get('member_level', 1) if not user['is_admin'] else 3
    
    # API 확인
    api_key = get_api_key()
    
    selected_service = None
    
    # ===== 상품 타입 선택 =====
    st.markdown('<span class="section-title">1️⃣ 상품 유형 선택</span>', unsafe_allow_html=True)
    
    # 등급에 따른 옵션 표시
    if level == 1:
        options = ["📦 기성상품"]
    elif level == 2:
        options = ["🔧 개별상품"]
    else:
        options = ["📦 기성상품", "🔧 개별상품"]
    
    product_type = st.radio("상품 유형", options, horizontal=True, key="prod_type")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== 기성상품 선택 =====
    if "기성상품" in product_type:
        st.markdown('<span class="section-title">2️⃣ 기성상품 선택</span>', unsafe_allow_html=True)
        
        admin_services = get_admin_services()
        if admin_services:
            svc_names = [s['name'] for s in admin_services]
            selected_name = st.selectbox("기성상품 목록", svc_names, key="ready_svc")
            selected_service = next((s for s in admin_services if s['name'] == selected_name), None)
            
            if selected_service:
                chapters = get_chapters_by_service(selected_service['id'])
                templates = get_templates_by_service(selected_service['id'])
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.success(f"✅ '{selected_name}' 선택됨 (목차 {len(chapters)}개)")
                with col2:
                    t_cols = st.columns(3)
                    for idx, tt in enumerate(["cover", "background", "info"]):
                        with t_cols[idx]:
                            t_list = [t for t in templates if t['template_type'] == tt]
                            if t_list and t_list[0].get('image_path') and os.path.exists(t_list[0]['image_path']):
                                st.image(t_list[0]['image_path'], width=50)
        else:
            st.warning("등록된 기성상품이 없습니다.")
    
    # ===== 개별상품 =====
    elif "개별상품" in product_type:
        st.markdown('<span class="section-title">2️⃣ 개별상품</span>', unsafe_allow_html=True)
        
        my_services = get_user_services(user['id'])
        
        if my_services:
            my_names = ["➕ 새로 만들기"] + [s['name'] for s in my_services]
            selected_my = st.selectbox("내 상품 목록", my_names, key="my_svc")
            
            if selected_my != "➕ 새로 만들기":
                selected_service = next((s for s in my_services if s['name'] == selected_my), None)
                if selected_service:
                    chapters = get_chapters_by_service(selected_service['id'])
                    st.success(f"✅ '{selected_my}' 선택됨 (목차 {len(chapters)}개)")
        else:
            selected_my = "➕ 새로 만들기"
        
        if not my_services or selected_my == "➕ 새로 만들기":
            with st.expander("➕ 개별상품 만들기", expanded=True):
                my_name = st.text_input("상품명", key="my_prod")
                
                st.markdown("**📑 목차** (줄바꿈으로 구분)")
                my_chapters = st.text_area("목차 입력", height=200, key="my_ch",
                    placeholder="1. 올해의 총운\n2. 재물운\n3. 건강운")
                
                st.markdown("**📜 AI 작성 지침**")
                my_guide = st.text_area("지침 입력", height=200, key="my_g",
                    placeholder="- 긍정적인 톤\n- 300자 이상\n- 구체적 조언 포함")
                
                st.markdown("**🎨 디자인**")
                d_cols = st.columns(3)
                with d_cols[0]:
                    my_cover = st.file_uploader("📕 표지", type=["jpg","jpeg","png"], key="my_cover")
                    if my_cover:
                        st.image(my_cover, width=80)
                with d_cols[1]:
                    my_bg = st.file_uploader("📄 내지", type=["jpg","jpeg","png"], key="my_bg")
                    if my_bg:
                        st.image(my_bg, width=80)
                with d_cols[2]:
                    my_info = st.file_uploader("📋 안내지", type=["jpg","jpeg","png"], key="my_info")
                    if my_info:
                        st.image(my_info, width=80)
                
                if st.button("💾 개별상품 저장", type="primary", use_container_width=True):
                    if my_name and my_chapters:
                        result = add_service(my_name, "", user['id'])
                        if result.get("success"):
                            svc_id = result["id"]
                            
                            for idx, ch in enumerate(my_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx+1)
                            
                            if my_guide:
                                add_guideline(svc_id, f"{my_name} 지침", my_guide)
                            
                            if my_cover:
                                path = save_uploaded_file(my_cover, f"{my_name}_cover")
                                add_template(svc_id, "cover", "표지", path)
                            if my_bg:
                                path = save_uploaded_file(my_bg, f"{my_name}_bg")
                                add_template(svc_id, "background", "내지", path)
                            if my_info:
                                path = save_uploaded_file(my_info, f"{my_name}_info")
                                add_template(svc_id, "info", "안내지", path)
                            
                            st.success("저장됨!")
                            st.rerun()
                    else:
                        st.error("상품명과 목차를 입력하세요.")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== PDF 생성 영역 =====
    st.markdown('<span class="section-title">3️⃣ PDF 생성</span>', unsafe_allow_html=True)
    
    # 오류 검증
    if selected_service:
        is_ready, errors = verify_pdf_generation_ready(selected_service['id'], api_key)
        
        for err in errors:
            if "❌" in err:
                st.error(err)
            else:
                st.warning(err)
        
        if not is_ready:
            st.stop()
    else:
        st.warning("⚠️ 상품을 먼저 선택하세요.")
        st.stop()
    
    # 폰트 크기
    font_size = st.slider("글자 크기", 10, 18, 12, key="font")
    
    # 고객 파일
    uploaded = st.file_uploader("📂 고객 엑셀 파일 (.xlsx)", type=["xlsx", "xls"], key="cust")
    
    if uploaded:
        df = pd.read_excel(uploaded)
        st.session_state.customers_df = df
        st.success(f"✅ {len(df)}명 로드됨")
    
    if st.session_state.customers_df is not None:
        df = st.session_state.customers_df
        
        # 이름 컬럼 찾기
        name_col = None
        for col in ['이름', 'name', 'Name', '성명', '고객명']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            name_col = df.columns[0]
        
        st.markdown("---")
        
        # 고객 목록 헤더
        header_cols = st.columns([3, 4, 1, 1])
        header_cols[0].markdown("**이름**")
        header_cols[1].markdown("**진행률**")
        header_cols[2].markdown("**상태**")
        header_cols[3].markdown("**다운로드**")
        
        st.markdown("---")
        
        # 고객 목록
        for idx, row in df.iterrows():
            cust_name = row[name_col]
            is_done = idx in st.session_state.completed_customers
            
            col1, col2, col3, col4 = st.columns([3, 4, 1, 1])
            
            with col1:
                st.write(f"**{cust_name}**")
            
            with col2:
                if is_done:
                    st.progress(1.0, text="100%")
                else:
                    st.progress(0.0, text="0%")
            
            with col3:
                if is_done:
                    st.markdown('<span class="badge-done">✅ 완료</span>', unsafe_allow_html=True)
            
            with col4:
                if is_done:
                    pdf_data = st.session_state.generated_pdfs.get(idx)
                    if pdf_data:
                        st.download_button("⬇️", pdf_data, f"{cust_name}_운세.pdf", 
                                          "application/pdf", key=f"dl_{idx}")
        
        st.markdown("---")
        
        # 변환 버튼
        done_count = len(st.session_state.completed_customers)
        total_count = len(df)
        
        st.info(f"📊 완료: {done_count}/{total_count}")
        
        if st.button("🚀 PDF 생성 시작", type="primary", use_container_width=True):
            pending = [i for i in range(len(df)) if i not in st.session_state.completed_customers]
            
            if not pending:
                st.warning("생성할 고객이 없습니다.")
            else:
                progress_bar = st.progress(0, text="준비 중...")
                status = st.empty()
                
                for i, idx in enumerate(pending):
                    row = df.iloc[idx]
                    cust_name = row[name_col]
                    
                    # 진행률 계산
                    progress = (i + 1) / len(pending)
                    progress_bar.progress(progress, text=f"{int(progress * 100)}%")
                    status.text(f"📝 {cust_name} 생성 중... ({i+1}/{len(pending)})")
                    
                    pdf_bytes = generate_pdf_for_customer(
                        row.to_dict(),
                        selected_service['id'],
                        font_size,
                        api_key
                    )
                    
                    if pdf_bytes:
                        st.session_state.completed_customers[idx] = True
                        st.session_state.generated_pdfs[idx] = pdf_bytes
                        st.toast(f"🔔 {cust_name} 완료!")
                
                status.text("✅ 모든 PDF 생성 완료!")
                st.balloons()
                play_sound()
                st.rerun()

# ============================================
# 👤 MyPage
# ============================================

def show_mypage():
    st.title("👤 MyPage")
    user = st.session_state.user
    
    tab1, tab2 = st.tabs(["📋 내 정보", "🔑 API/이메일"])
    
    with tab1:
        new_name = st.text_input("이름", value=user['name'])
        st.text_input("이메일", value=user['email'], disabled=True)
        
        if st.button("💾 저장"):
            result = update_user_profile(user['id'], name=new_name)
            if result["success"]:
                st.session_state.user['name'] = new_name
                st.success("저장됨")
        
        st.markdown("---")
        old_pw = st.text_input("현재 비밀번호", type="password")
        new_pw = st.text_input("새 비밀번호", type="password")
        
        if st.button("🔒 비밀번호 변경"):
            if old_pw and new_pw:
                result = change_password(user['id'], old_pw, new_pw)
                if result["success"]:
                    st.success("변경됨")
                else:
                    st.error(result["error"])
    
    with tab2:
        if user.get('api_mode') == 'separated':
            my_api = st.text_input("내 API 키", value=user.get('api_key', '') or '', type="password")
            if st.button("💾 API 저장"):
                result = update_user_profile(user['id'], api_key=my_api)
                if result["success"]:
                    st.session_state.user['api_key'] = my_api
                    st.success("저장됨")
        else:
            st.info("🔒 API: 관리자 통합 모드")
        
        if user.get('email_mode') == 'separated':
            my_gmail = st.text_input("Gmail", value=user.get('gmail_address', '') or '')
            my_pw = st.text_input("앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
            if st.button("💾 이메일 저장"):
                result = update_user_profile(user['id'], gmail_address=my_gmail, gmail_app_password=my_pw)
                if result["success"]:
                    st.session_state.user['gmail_address'] = my_gmail
                    st.session_state.user['gmail_app_password'] = my_pw
                    st.success("저장됨")
        else:
            st.info("🔒 이메일: 관리자 통합 모드")

# ============================================
# 📢 공지사항
# ============================================

def show_notices():
    st.title("📢 공지사항")
    
    if is_admin():
        with st.expander("✏️ 새 공지", expanded=False):
            title = st.text_input("제목", key="n_title")
            content = st.text_area("내용", height=150, key="n_content")
            pinned = st.checkbox("📌 고정")
            
            if st.button("💾 등록", type="primary"):
                if title and content:
                    create_notice(st.session_state.user['id'], title, content, None, pinned)
                    st.success("등록됨!")
                    st.rerun()
    
    st.markdown("---")
    
    notices = get_all_notices()
    if not notices:
        st.info("공지가 없습니다.")
    else:
        for n in notices:
            pin = "📌 " if n['is_pinned'] else ""
            with st.expander(f"{pin}**{n['title']}**"):
                if is_admin():
                    ed_title = st.text_input("제목", value=n['title'], key=f"et_{n['id']}")
                    ed_content = st.text_area("내용", value=n['content'], height=80, key=f"ec_{n['id']}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("💾 수정", key=f"sv_{n['id']}"):
                            update_notice(n['id'], ed_title, ed_content)
                            st.rerun()
                    with c2:
                        if st.button("📌 고정", key=f"pn_{n['id']}"):
                            toggle_pin_notice(n['id'])
                            st.rerun()
                    with c3:
                        if st.button("🗑️ 삭제", key=f"dl_{n['id']}"):
                            delete_notice(n['id'])
                            st.rerun()
                else:
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
