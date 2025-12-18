# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
자료실 + 폰트설정 + 진행률 개선 버전
"""

import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="PDF 자동 생성 플랫폼", page_icon="🔮", layout="wide")

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
    add_service, update_service, delete_service, 
    get_system_config, set_system_config, ConfigKeys,
    get_chapter_library, add_chapter_library, update_chapter_library, delete_chapter_library,
    get_guideline_library, add_guideline_library, update_guideline_library, delete_guideline_library
)
from contents import (
    get_chapters_by_service, add_chapter, update_chapter, delete_chapter,
    get_guidelines_by_service, add_guideline, update_guideline, delete_guideline,
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
    
    section[data-testid="stSidebar"] .stRadio > div > label > div:first-child { display: none !important; }
    section[data-testid="stSidebar"] .stRadio > div > label {
        cursor: pointer !important; padding: 10px 15px; border-radius: 8px; margin: 2px 0;
    }
    
    .section-title {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 8px 20px; border-radius: 20px; color: white; font-weight: bold;
        font-size: 1rem; margin: 15px 0 10px 0;
    }
    .divider { border-top: 1px solid rgba(255,255,255,0.1); margin: 20px 0; }
    
    .badge-admin { background: #dc3545; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level1 { background: #6c757d; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level2 { background: #17a2b8; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level3 { background: #28a745; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ============================================
# 세션 상태 초기화
# ============================================

defaults = {
    'logged_in': False, 'user': None, 'customers_df': None,
    'completed_customers': {}, 'generated_pdfs': {}, 'selected_customers': set(),
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
# 상수 / 유틸리티
# ============================================

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)

TEMPLATE_TYPES = {"cover": "📕 표지", "background": "📄 내지", "info": "📋 안내지"}
FONT_OPTIONS = {"NanumGothic": "나눔고딕", "NanumMyeongjo": "나눔명조", "NanumBarunGothic": "나눔바른고딕"}
CATEGORIES = ["사주", "타로", "연애", "기타"]

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

def verify_pdf_generation_ready(service_id: int, api_key: str) -> tuple:
    errors = []
    if not api_key:
        errors.append("❌ API 키가 설정되지 않았습니다.")
    if not service_id:
        errors.append("❌ 상품이 선택되지 않았습니다.")
        return False, errors
    chapters = get_chapters_by_service(service_id)
    if not chapters:
        errors.append("❌ 목차가 등록되지 않았습니다.")
    if errors and any("❌" in e for e in errors):
        return False, errors
    return True, errors

def render_font_settings(prefix: str, defaults: dict = None):
    """폰트/여백 설정 UI"""
    if defaults is None:
        defaults = {"font_family": "NanumGothic", "font_size_title": 24, "font_size_subtitle": 16,
                    "font_size_body": 12, "letter_spacing": 0, "line_height": 180, "char_width": 100,
                    "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25}
    
    st.markdown("**🎨 폰트 설정**")
    col1, col2, col3 = st.columns(3)
    with col1:
        font_idx = list(FONT_OPTIONS.keys()).index(defaults.get("font_family", "NanumGothic")) if defaults.get("font_family") in FONT_OPTIONS else 0
        font_family = st.selectbox("폰트", list(FONT_OPTIONS.keys()), index=font_idx,
                                   format_func=lambda x: FONT_OPTIONS[x], key=f"{prefix}_font")
    with col2:
        line_height = st.slider("행간 (%)", 100, 300, defaults.get("line_height", 180), 10, key=f"{prefix}_lh")
    with col3:
        letter_spacing = st.slider("자간 (%)", -20, 50, defaults.get("letter_spacing", 0), 5, key=f"{prefix}_ls")
    
    col4, col5, col6, col7 = st.columns(4)
    with col4:
        font_size_title = st.number_input("대제목", 16, 40, defaults.get("font_size_title", 24), key=f"{prefix}_title")
    with col5:
        font_size_subtitle = st.number_input("소제목", 12, 30, defaults.get("font_size_subtitle", 16), key=f"{prefix}_sub")
    with col6:
        font_size_body = st.number_input("본문", 8, 24, defaults.get("font_size_body", 12), key=f"{prefix}_body")
    with col7:
        char_width = st.slider("장평 (%)", 50, 150, defaults.get("char_width", 100), 5, key=f"{prefix}_cw")
    
    st.markdown("**📐 여백 설정 (mm)**")
    m_cols = st.columns(4)
    with m_cols[0]:
        margin_top = st.number_input("상단", 5, 50, defaults.get("margin_top", 25), key=f"{prefix}_mt")
    with m_cols[1]:
        margin_bottom = st.number_input("하단", 5, 50, defaults.get("margin_bottom", 25), key=f"{prefix}_mb")
    with m_cols[2]:
        margin_left = st.number_input("좌측", 5, 50, defaults.get("margin_left", 25), key=f"{prefix}_ml")
    with m_cols[3]:
        margin_right = st.number_input("우측", 5, 50, defaults.get("margin_right", 25), key=f"{prefix}_mr")
    
    return {"font_family": font_family, "font_size_title": font_size_title, "font_size_subtitle": font_size_subtitle,
            "font_size_body": font_size_body, "letter_spacing": letter_spacing, "line_height": line_height,
            "char_width": char_width, "margin_top": margin_top, "margin_bottom": margin_bottom,
            "margin_left": margin_left, "margin_right": margin_right}

# ============================================
# PDF 생성 함수
# ============================================

def generate_content_with_gpt(api_key: str, chapter_title: str, guideline: str, customer_data: dict) -> str:
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
            model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}],
            max_tokens=1000, temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[내용 생성 오류: {str(e)}]"


def create_pdf_document(customer_name: str, chapters_content: list, templates: dict, font_settings: dict) -> bytes:
    """PDF 문서 생성"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import black
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        
        buffer = BytesIO()
        page_width, page_height = A4
        
        # 한글 폰트 등록
        font_name = 'Helvetica'
        try:
            font_paths = {
                'NanumGothic': '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                'NanumMyeongjo': '/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf',
                'NanumBarunGothic': '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
            }
            selected_font = font_settings.get('font_family', 'NanumGothic')
            font_path = font_paths.get(selected_font)
            if font_path and os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('KoreanFont', font_path))
                font_name = 'KoreanFont'
            else:
                for fp in font_paths.values():
                    if os.path.exists(fp):
                        pdfmetrics.registerFont(TTFont('KoreanFont', fp))
                        font_name = 'KoreanFont'
                        break
        except:
            pass
        
        # 폰트 설정
        title_size = font_settings.get('font_size_title', 24)
        subtitle_size = font_settings.get('font_size_subtitle', 16)
        body_size = font_settings.get('font_size_body', 12)
        line_height_pct = font_settings.get('line_height', 180)
        
        # 여백 설정
        margin_top = font_settings.get('margin_top', 25) * mm
        margin_bottom = font_settings.get('margin_bottom', 25) * mm
        margin_left = font_settings.get('margin_left', 25) * mm
        margin_right = font_settings.get('margin_right', 25) * mm
        
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # 1. 표지
        cover_path = templates.get('cover')
        if cover_path and os.path.exists(cover_path):
            try:
                c.drawImage(cover_path, 0, 0, width=page_width, height=page_height)
            except:
                c.setFont(font_name, title_size)
                c.drawCentredString(page_width/2, page_height/2, f"{customer_name}님의 운세")
        else:
            c.setFont(font_name, title_size)
            c.drawCentredString(page_width/2, page_height/2, f"{customer_name}님의 운세")
        c.showPage()
        
        # 2. 본문
        for idx, chapter in enumerate(chapters_content):
            y_pos = page_height - margin_top
            max_width = page_width - margin_left - margin_right
            
            # 소제목
            c.setFont(font_name, subtitle_size)
            c.drawString(margin_left, y_pos, f"● {chapter['title']}")
            y_pos -= subtitle_size * 2
            
            # 본문
            c.setFont(font_name, body_size)
            line_spacing = body_size * (line_height_pct / 100)
            
            for para in chapter['content'].split('\n'):
                if not para.strip():
                    continue
                current_line = ""
                for char in para.strip():
                    test_line = current_line + char
                    if c.stringWidth(test_line, font_name, body_size) < max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            if y_pos < margin_bottom + 30:
                                c.setFont(font_name, 10)
                                c.drawCentredString(page_width/2, 15*mm, f"- {idx + 2} -")
                                c.showPage()
                                y_pos = page_height - margin_top
                                c.setFont(font_name, body_size)
                            c.drawString(margin_left, y_pos, current_line)
                            y_pos -= line_spacing
                        current_line = char
                if current_line:
                    if y_pos < margin_bottom + 30:
                        c.setFont(font_name, 10)
                        c.drawCentredString(page_width/2, 15*mm, f"- {idx + 2} -")
                        c.showPage()
                        y_pos = page_height - margin_top
                        c.setFont(font_name, body_size)
                    c.drawString(margin_left, y_pos, current_line)
                    y_pos -= line_spacing
                y_pos -= line_spacing * 0.5
            
            c.setFont(font_name, 10)
            c.drawCentredString(page_width/2, 15*mm, f"- {idx + 2} -")
            c.showPage()
        
        # 3. 안내지
        info_path = templates.get('info')
        if info_path and os.path.exists(info_path):
            try:
                c.drawImage(info_path, 0, 0, width=page_width, height=page_height)
            except:
                c.setFont(font_name, title_size)
                c.drawCentredString(page_width/2, page_height/2, "감사합니다")
        else:
            c.setFont(font_name, title_size)
            c.drawCentredString(page_width/2, page_height/2, "감사합니다")
        
        c.save()
        return buffer.getvalue()
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None


def generate_pdf_for_customer(customer_data: dict, service: dict, api_key: str, 
                              progress_callback=None, customer_idx=None) -> bytes:
    """고객용 PDF 생성 (진행률 콜백 포함)"""
    service_id = service['id']
    chapters = get_chapters_by_service(service_id)
    guidelines = get_guidelines_by_service(service_id)
    guideline_text = guidelines[0]['content'] if guidelines else "친절하고 긍정적인 톤으로 작성하세요."
    
    templates_list = get_templates_by_service(service_id)
    templates = {t['template_type']: t['image_path'] for t in templates_list 
                 if t.get('image_path') and os.path.exists(t['image_path'])}
    
    name_col = None
    for col in ['이름', 'name', 'Name', '성명', '고객명']:
        if col in customer_data:
            name_col = col
            break
    customer_name = customer_data.get(name_col, "고객") if name_col else "고객"
    
    font_settings = {k: service.get(k, v) for k, v in 
                     {"font_family": "NanumGothic", "font_size_title": 24, "font_size_subtitle": 16,
                      "font_size_body": 12, "letter_spacing": 0, "line_height": 180, "char_width": 100,
                      "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25}.items()}
    
    chapters_content = []
    total_chapters = len(chapters)
    
    for i, ch in enumerate(chapters):
        content = generate_content_with_gpt(api_key, ch['title'], guideline_text, customer_data)
        chapters_content.append({"title": ch['title'], "content": content})
        
        # 진행률 업데이트 (챕터별)
        if progress_callback and customer_idx is not None:
            progress = (i + 1) / total_chapters
            progress_callback(customer_idx, progress)
    
    return create_pdf_document(customer_name, chapters_content, templates, font_settings)


def generate_pdf_with_progress(customer_data: dict, service: dict, api_key: str,
                               progress_bar, detail_text) -> bytes:
    """고객용 PDF 생성 - 실시간 진행률 표시"""
    service_id = service['id']
    chapters = get_chapters_by_service(service_id)
    guidelines = get_guidelines_by_service(service_id)
    guideline_text = guidelines[0]['content'] if guidelines else "친절하고 긍정적인 톤으로 작성하세요."
    
    templates_list = get_templates_by_service(service_id)
    templates = {t['template_type']: t['image_path'] for t in templates_list 
                 if t.get('image_path') and os.path.exists(t['image_path'])}
    
    name_col = None
    for col in ['이름', 'name', 'Name', '성명', '고객명']:
        if col in customer_data:
            name_col = col
            break
    customer_name = customer_data.get(name_col, "고객") if name_col else "고객"
    
    font_settings = {k: service.get(k, v) for k, v in 
                     {"font_family": "NanumGothic", "font_size_title": 24, "font_size_subtitle": 16,
                      "font_size_body": 12, "letter_spacing": 0, "line_height": 180, "char_width": 100,
                      "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25}.items()}
    
    chapters_content = []
    total_chapters = len(chapters)
    
    # 초기 진행률 0%
    progress_bar.progress(0.0, text="0%")
    detail_text.caption("준비 중...")
    
    for i, ch in enumerate(chapters):
        # 현재 챕터 표시
        detail_text.caption(f"📝 {ch['title']} 작성 중...")
        
        content = generate_content_with_gpt(api_key, ch['title'], guideline_text, customer_data)
        chapters_content.append({"title": ch['title'], "content": content})
        
        # 진행률 실시간 업데이트
        progress = (i + 1) / total_chapters
        progress_bar.progress(progress, text=f"{int(progress * 100)}%")
        time.sleep(0.1)  # 시각적 효과
    
    detail_text.caption("📄 PDF 생성 중...")
    return create_pdf_document(customer_name, chapters_content, templates, font_settings)

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
                        st.success(result["message"]) if result["success"] else st.error(result["error"])
        
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
                            st.success("✅ 관리자 계정 생성됨!")
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
            badges = {1: "badge-level1", 2: "badge-level2", 3: "badge-level3"}
            st.markdown(f'<span class="{badges[level]}">{level}단계</span>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        menu = []
        if user['is_admin']:
            menu.append("⚙️ 관리자 설정")
        menu.extend(["📦 서비스 작업", "📚 자료실", "👤 MyPage", "📢 공지사항"])
        
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
    elif selected == "📚 자료실":
        show_library()
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
    
    with tab2:
        st.markdown('<span class="section-title">👥 회원 관리</span>', unsafe_allow_html=True)
        st.markdown("**1단계**: 기성상품만 | **2단계**: 개별상품만 | **3단계**: 둘 다")
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        subtab1, subtab2 = st.tabs(["전체 회원", "승인 대기"])
        with subtab1:
            for u in get_all_users():
                if u['id'] == st.session_state.user['id']:
                    continue
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                with col1:
                    status_icon = "🟢" if u['status'] == 'approved' else "🔴"
                    admin_mark = "👑" if u['is_admin'] else ""
                    st.write(f"{status_icon} {admin_mark} **{u['name']}**")
                    st.caption(u['email'])
                with col2:
                    new_level = st.selectbox("등급", [1, 2, 3], index=u.get('member_level', 1) - 1,
                                            format_func=lambda x: f"{x}단계", key=f"lvl_{u['id']}")
                with col3:
                    new_api = st.selectbox("API", ["unified", "separated"],
                                          index=0 if u.get('api_mode') == 'unified' else 1,
                                          format_func=lambda x: "통합" if x == "unified" else "분리",
                                          key=f"api_{u['id']}")
                with col4:
                    new_email = st.selectbox("이메일", ["unified", "separated"],
                                            index=0 if u.get('email_mode') == 'unified' else 1,
                                            format_func=lambda x: "통합" if x == "unified" else "분리",
                                            key=f"email_{u['id']}")
                with col5:
                    if st.button("💾", key=f"save_{u['id']}"):
                        update_user_settings(u['id'], new_level, new_api, new_email)
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
    
    with tab3:
        st.markdown('<span class="section-title">📦 기성상품 등록</span>', unsafe_allow_html=True)
        
        with st.expander("➕ 새 기성상품 등록", expanded=False):
            product_name = st.text_input("상품명", key="new_prod")
            
            # 목차/지침 좌우 배치
            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown("**📑 목차** (줄바꿈 구분)")
                new_chapters = st.text_area("목차", height=567, key="new_ch", placeholder="1. 총운\n2. 재물운\n3. 건강운")
            with col_right:
                st.markdown("**📜 AI 작성 지침**")
                new_guideline = st.text_area("지침", height=567, key="new_g", placeholder="- 긍정적 톤\n- 300자 이상")
            
            font_settings = render_font_settings("new_admin")
            
            st.markdown("**🖼️ 디자인**")
            d_cols = st.columns(3)
            with d_cols[0]:
                cover = st.file_uploader("📕 표지", type=["jpg","jpeg","png"], key="new_cover")
            with d_cols[1]:
                bg = st.file_uploader("📄 내지", type=["jpg","jpeg","png"], key="new_bg")
            with d_cols[2]:
                info = st.file_uploader("📋 안내지", type=["jpg","jpeg","png"], key="new_info")
            
            if st.button("💾 기성상품 등록", type="primary", use_container_width=True):
                if product_name:
                    result = add_service(product_name, "", None, **font_settings)
                    if result.get("success"):
                        svc_id = result["id"]
                        if new_chapters:
                            for idx, ch in enumerate(new_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx+1)
                        if new_guideline:
                            add_guideline(svc_id, f"{product_name} 지침", new_guideline)
                        if cover:
                            add_template(svc_id, "cover", "표지", save_uploaded_file(cover, f"{product_name}_cover"))
                        if bg:
                            add_template(svc_id, "background", "내지", save_uploaded_file(bg, f"{product_name}_bg"))
                        if info:
                            add_template(svc_id, "info", "안내지", save_uploaded_file(info, f"{product_name}_info"))
                        st.success(f"'{product_name}' 등록됨!")
                        st.rerun()
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("**등록된 기성상품**")
        
        services = get_admin_services()
        if not services:
            st.info("등록된 기성상품이 없습니다.")
        else:
            for svc in services:
                with st.expander(f"📌 {svc['name']}"):
                    show_service_edit_form(svc, "admin")

def show_service_edit_form(svc: dict, prefix: str):
    """상품 수정 폼"""
    svc_id = svc['id']
    chapters = get_chapters_by_service(svc_id)
    guidelines = get_guidelines_by_service(svc_id)
    templates = get_templates_by_service(svc_id)
    
    edit_name = st.text_input("상품명", value=svc['name'], key=f"{prefix}_name_{svc_id}")
    
    # 좌우 배치
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("**📑 목차**")
        current_chapters = "\n".join([ch['title'] for ch in chapters])
        edit_chapters = st.text_area("목차", value=current_chapters, height=400, key=f"{prefix}_ch_{svc_id}")
    with col_right:
        st.markdown("**📜 지침**")
        current_guideline = guidelines[0]['content'] if guidelines else ""
        edit_guideline = st.text_area("지침", value=current_guideline, height=400, key=f"{prefix}_g_{svc_id}")
    
    font_defaults = {k: svc.get(k, v) for k, v in 
                     {"font_family": "NanumGothic", "font_size_title": 24, "font_size_subtitle": 16,
                      "font_size_body": 12, "letter_spacing": 0, "line_height": 180, "char_width": 100,
                      "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25}.items()}
    font_settings = render_font_settings(f"{prefix}_{svc_id}", font_defaults)
    
    st.markdown("**🖼️ 디자인**")
    t_cols = st.columns(3)
    for idx, tt in enumerate(["cover", "background", "info"]):
        with t_cols[idx]:
            t_list = [t for t in templates if t['template_type'] == tt]
            if t_list and t_list[0].get('image_path') and os.path.exists(t_list[0]['image_path']):
                st.image(t_list[0]['image_path'], width=80)
            st.file_uploader(TEMPLATE_TYPES[tt], type=["jpg","jpeg","png"], key=f"{prefix}_{tt}_{svc_id}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 저장", key=f"{prefix}_save_{svc_id}", type="primary", use_container_width=True):
            update_service(svc_id, name=edit_name, **font_settings)
            for ch in chapters:
                delete_chapter(ch['id'])
            for idx, ch in enumerate(edit_chapters.strip().split("\n")):
                if ch.strip():
                    add_chapter(svc_id, ch.strip(), "", idx+1)
            if guidelines:
                update_guideline(guidelines[0]['id'], guidelines[0]['title'], edit_guideline)
            elif edit_guideline:
                add_guideline(svc_id, f"{edit_name} 지침", edit_guideline)
            
            for tt in ["cover", "background", "info"]:
                new_file = st.session_state.get(f"{prefix}_{tt}_{svc_id}")
                if new_file:
                    for t in templates:
                        if t['template_type'] == tt:
                            delete_template(t['id'])
                    add_template(svc_id, tt, TEMPLATE_TYPES[tt], save_uploaded_file(new_file, f"{edit_name}_{tt}"))
            st.success("저장됨!")
            st.rerun()
    with col2:
        if st.button("🗑️ 삭제", key=f"{prefix}_del_{svc_id}", use_container_width=True):
            delete_service(svc_id)
            st.rerun()

# ============================================
# 📚 자료실
# ============================================

def show_library():
    st.title("📚 자료실")
    user = st.session_state.user
    
    tab1, tab2 = st.tabs(["📑 목차 게시판", "📜 지침 게시판"])
    
    with tab1:
        st.markdown('<span class="section-title">📑 목차 게시판</span>', unsafe_allow_html=True)
        
        with st.expander("➕ 새 목차 등록", expanded=False):
            ch_title = st.text_input("제목", key="lib_ch_title")
            ch_category = st.selectbox("카테고리", CATEGORIES, key="lib_ch_cat")
            ch_content = st.text_area("목차 내용 (줄바꿈 구분)", height=300, key="lib_ch_content",
                                     placeholder="1. 총운\n2. 재물운\n3. 건강운\n4. 연애운")
            
            if st.button("💾 목차 등록", type="primary", key="lib_ch_save"):
                if ch_title and ch_content:
                    user_id = None if is_admin() else user['id']
                    add_chapter_library(ch_title, ch_content, ch_category, user_id)
                    st.success("등록됨!")
                    st.rerun()
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # 필터
        filter_cat = st.selectbox("카테고리 필터", ["전체"] + CATEGORIES, key="lib_ch_filter")
        cat_filter = None if filter_cat == "전체" else filter_cat
        
        items = get_chapter_library(user['id'] if not is_admin() else None, cat_filter)
        if not items:
            st.info("등록된 목차가 없습니다.")
        else:
            for item in items:
                with st.expander(f"{'🔓' if item['user_id'] is None else '🔒'} {item['title']} ({item['category'] or '미분류'})"):
                    ed_title = st.text_input("제목", value=item['title'], key=f"lib_ch_t_{item['id']}")
                    ed_cat = st.selectbox("카테고리", CATEGORIES, 
                                         index=CATEGORIES.index(item['category']) if item['category'] in CATEGORIES else 0,
                                         key=f"lib_ch_c_{item['id']}")
                    ed_content = st.text_area("내용", value=item['content'], height=200, key=f"lib_ch_ct_{item['id']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 수정", key=f"lib_ch_sv_{item['id']}"):
                            update_chapter_library(item['id'], ed_title, ed_content, ed_cat)
                            st.success("수정됨!")
                            st.rerun()
                    with col2:
                        if st.button("📋 복사", key=f"lib_ch_cp_{item['id']}"):
                            st.session_state['clipboard_chapters'] = ed_content
                            st.success("클립보드에 복사됨!")
                    with col3:
                        if st.button("🗑️ 삭제", key=f"lib_ch_dl_{item['id']}"):
                            delete_chapter_library(item['id'])
                            st.rerun()
    
    with tab2:
        st.markdown('<span class="section-title">📜 지침 게시판</span>', unsafe_allow_html=True)
        
        with st.expander("➕ 새 지침 등록", expanded=False):
            g_title = st.text_input("제목", key="lib_g_title")
            g_category = st.selectbox("카테고리", CATEGORIES, key="lib_g_cat")
            g_content = st.text_area("지침 내용", height=400, key="lib_g_content",
                                    placeholder="- 긍정적이고 희망적인 톤으로 작성\n- 300-500자 분량\n- 고객 정보 자연스럽게 반영")
            
            if st.button("💾 지침 등록", type="primary", key="lib_g_save"):
                if g_title and g_content:
                    user_id = None if is_admin() else user['id']
                    add_guideline_library(g_title, g_content, g_category, user_id)
                    st.success("등록됨!")
                    st.rerun()
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        filter_cat2 = st.selectbox("카테고리 필터", ["전체"] + CATEGORIES, key="lib_g_filter")
        cat_filter2 = None if filter_cat2 == "전체" else filter_cat2
        
        items2 = get_guideline_library(user['id'] if not is_admin() else None, cat_filter2)
        if not items2:
            st.info("등록된 지침이 없습니다.")
        else:
            for item in items2:
                with st.expander(f"{'🔓' if item['user_id'] is None else '🔒'} {item['title']} ({item['category'] or '미분류'})"):
                    ed_title = st.text_input("제목", value=item['title'], key=f"lib_g_t_{item['id']}")
                    ed_cat = st.selectbox("카테고리", CATEGORIES,
                                         index=CATEGORIES.index(item['category']) if item['category'] in CATEGORIES else 0,
                                         key=f"lib_g_c_{item['id']}")
                    ed_content = st.text_area("내용", value=item['content'], height=300, key=f"lib_g_ct_{item['id']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 수정", key=f"lib_g_sv_{item['id']}"):
                            update_guideline_library(item['id'], ed_title, ed_content, ed_cat)
                            st.success("수정됨!")
                            st.rerun()
                    with col2:
                        if st.button("📋 복사", key=f"lib_g_cp_{item['id']}"):
                            st.session_state['clipboard_guideline'] = ed_content
                            st.success("클립보드에 복사됨!")
                    with col3:
                        if st.button("🗑️ 삭제", key=f"lib_g_dl_{item['id']}"):
                            delete_guideline_library(item['id'])
                            st.rerun()

# ============================================
# 📦 서비스 작업
# ============================================

def show_service_work():
    st.title("📦 서비스 작업")
    
    user = st.session_state.user
    level = user.get('member_level', 1) if not user['is_admin'] else 3
    api_key = get_api_key()
    selected_service = None
    
    # 1. 상품 유형 선택
    st.markdown('<span class="section-title">1️⃣ 상품 유형 선택</span>', unsafe_allow_html=True)
    if level == 1:
        options = ["📦 기성상품"]
    elif level == 2:
        options = ["🔧 개별상품"]
    else:
        options = ["📦 기성상품", "🔧 개별상품"]
    product_type = st.radio("상품 유형", options, horizontal=True, key="prod_type")
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # 2. 기성상품
    if "기성상품" in product_type:
        st.markdown('<span class="section-title">2️⃣ 기성상품 선택</span>', unsafe_allow_html=True)
        admin_services = get_admin_services()
        if admin_services:
            svc_names = [s['name'] for s in admin_services]
            selected_name = st.selectbox("기성상품 목록", svc_names, key="ready_svc")
            selected_service = next((s for s in admin_services if s['name'] == selected_name), None)
            if selected_service:
                chapters = get_chapters_by_service(selected_service['id'])
                st.success(f"✅ '{selected_name}' 선택됨 (목차 {len(chapters)}개)")
        else:
            st.warning("등록된 기성상품이 없습니다.")
    
    # 2. 개별상품
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
                    with st.expander("✏️ 상품 수정", expanded=False):
                        show_service_edit_form(selected_service, "my")
        else:
            selected_my = "➕ 새로 만들기"
        
        if not my_services or selected_my == "➕ 새로 만들기":
            with st.expander("➕ 개별상품 만들기", expanded=True):
                my_name = st.text_input("상품명", key="my_prod")
                
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("**📑 목차**")
                    my_chapters = st.text_area("목차", height=400, key="my_ch")
                with col_right:
                    st.markdown("**📜 지침**")
                    my_guide = st.text_area("지침", height=400, key="my_g")
                
                font_settings = render_font_settings("new_my")
                
                st.markdown("**🖼️ 디자인**")
                d_cols = st.columns(3)
                with d_cols[0]:
                    my_cover = st.file_uploader("표지", type=["jpg","jpeg","png"], key="my_cover")
                with d_cols[1]:
                    my_bg = st.file_uploader("내지", type=["jpg","jpeg","png"], key="my_bg")
                with d_cols[2]:
                    my_info = st.file_uploader("안내지", type=["jpg","jpeg","png"], key="my_info")
                
                if st.button("💾 저장", type="primary", use_container_width=True):
                    if my_name and my_chapters:
                        result = add_service(my_name, "", user['id'], **font_settings)
                        if result.get("success"):
                            svc_id = result["id"]
                            for idx, ch in enumerate(my_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx+1)
                            if my_guide:
                                add_guideline(svc_id, f"{my_name} 지침", my_guide)
                            if my_cover:
                                add_template(svc_id, "cover", "표지", save_uploaded_file(my_cover, f"{my_name}_cover"))
                            if my_bg:
                                add_template(svc_id, "background", "내지", save_uploaded_file(my_bg, f"{my_name}_bg"))
                            if my_info:
                                add_template(svc_id, "info", "안내지", save_uploaded_file(my_info, f"{my_name}_info"))
                            st.success("저장됨!")
                            st.rerun()
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # 3. PDF 생성
    st.markdown('<span class="section-title">3️⃣ PDF 생성</span>', unsafe_allow_html=True)
    
    if selected_service:
        is_ready, errors = verify_pdf_generation_ready(selected_service['id'], api_key)
        for err in errors:
            st.error(err) if "❌" in err else st.warning(err)
        if not is_ready:
            st.stop()
    else:
        st.warning("⚠️ 상품을 먼저 선택하세요.")
        st.stop()
    
    # 고객 파일 업로드
    uploaded = st.file_uploader("📂 고객 엑셀 파일 (.xlsx)", type=["xlsx", "xls"], key="cust")
    
    if uploaded:
        df = pd.read_excel(uploaded)
        st.session_state.customers_df = df
        st.session_state.selected_customers = set(range(len(df)))
        st.success(f"✅ {len(df)}명 로드됨")
    
    if st.session_state.customers_df is not None:
        df = st.session_state.customers_df
        
        name_col = None
        for col in ['이름', 'name', 'Name', '성명', '고객명']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            name_col = df.columns[0]
        
        st.markdown("---")
        
        # 전체 선택 + 초기화
        col_ctrl1, col_ctrl2 = st.columns([1, 1])
        with col_ctrl1:
            if st.checkbox("전체 선택", value=len(st.session_state.selected_customers) == len(df)):
                st.session_state.selected_customers = set(range(len(df)))
            else:
                if len(st.session_state.selected_customers) == len(df):
                    st.session_state.selected_customers = set()
        with col_ctrl2:
            if st.button("🔄 초기화", use_container_width=True):
                st.session_state.completed_customers = {}
                st.session_state.generated_pdfs = {}
                st.session_state.selected_customers = set(range(len(df)))
                st.rerun()
        
        st.markdown("---")
        
        # 헤더
        header_cols = st.columns([0.5, 2.5, 2, 1, 1])
        header_cols[0].markdown("**선택**")
        header_cols[1].markdown("**이름**")
        header_cols[2].markdown("**상태**")
        header_cols[3].markdown("**완료**")
        header_cols[4].markdown("**다운**")
        
        for idx, row in df.iterrows():
            cust_name = row[name_col]
            is_done = idx in st.session_state.completed_customers
            
            col0, col1, col2, col3, col4 = st.columns([0.5, 2.5, 2, 1, 1])
            
            with col0:
                checked = st.checkbox("", value=idx in st.session_state.selected_customers,
                                     key=f"chk_{idx}", label_visibility="collapsed")
                if checked:
                    st.session_state.selected_customers.add(idx)
                else:
                    st.session_state.selected_customers.discard(idx)
            
            with col1:
                st.write(f"**{cust_name}**")
            
            with col2:
                if is_done:
                    st.progress(1.0, text="100%")
                else:
                    st.progress(0.0, text="대기")
            
            with col3:
                if is_done:
                    st.markdown("✅")
            
            with col4:
                if is_done:
                    pdf_data = st.session_state.generated_pdfs.get(idx)
                    if pdf_data:
                        st.download_button("⬇️", pdf_data, f"{cust_name}_운세.pdf",
                                          "application/pdf", key=f"dl_{idx}")
        
        st.markdown("---")
        
        pending_selected = [i for i in st.session_state.selected_customers
                          if i not in st.session_state.completed_customers]
        
        st.info(f"📊 선택: {len(st.session_state.selected_customers)}명 | 완료: {len(st.session_state.completed_customers)}/{len(df)}")
        
        if st.button(f"🚀 선택한 {len(pending_selected)}명 PDF 생성", type="primary", use_container_width=True):
            if not pending_selected:
                st.warning("생성할 고객을 선택하세요.")
            else:
                # 진행 상황 표시 영역
                status_area = st.empty()
                current_progress_bar = st.empty()
                current_detail = st.empty()
                
                for i, idx in enumerate(pending_selected):
                    row = df.iloc[idx]
                    cust_name = row[name_col]
                    
                    status_area.markdown(f"### 📝 {cust_name} 생성 중... ({i+1}/{len(pending_selected)})")
                    
                    # 이 고객의 PDF 생성 (진행바 직접 업데이트)
                    pdf_bytes = generate_pdf_with_progress(
                        row.to_dict(), selected_service, api_key,
                        current_progress_bar, current_detail
                    )
                    
                    if pdf_bytes:
                        st.session_state.completed_customers[idx] = True
                        st.session_state.generated_pdfs[idx] = pdf_bytes
                        st.toast(f"🔔 {cust_name} 완료!")
                    
                    current_progress_bar.progress(1.0, text="100% 완료")
                    time.sleep(0.3)
                
                status_area.markdown("### ✅ 모든 PDF 생성 완료!")
                current_progress_bar.empty()
                current_detail.empty()
                st.balloons()
                time.sleep(1)
                st.rerun()

# ============================================
# 👤 MyPage / 📢 공지사항
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
                st.success("변경됨") if result["success"] else st.error(result["error"])
    
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
                        if st.button("💾", key=f"sv_{n['id']}"):
                            update_notice(n['id'], ed_title, ed_content)
                            st.rerun()
                    with c2:
                        if st.button("📌", key=f"pn_{n['id']}"):
                            toggle_pin_notice(n['id'])
                            st.rerun()
                    with c3:
                        if st.button("🗑️", key=f"dl_{n['id']}"):
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
