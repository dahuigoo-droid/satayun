# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
자료실 + 폰트설정 + 진행률 개선 + 속도 최적화 버전
"""

import streamlit as st
import pandas as pd
import os
import time
import random
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
    get_chapters_by_service, add_chapter, add_chapters_bulk, update_chapter, delete_chapter, delete_chapters_by_service,
    get_guidelines_by_service, add_guideline, update_guideline, delete_guideline,
    get_templates_by_service, add_template, delete_template
)
from notices import get_all_notices, create_notice, update_notice, delete_notice, toggle_pin_notice

# ============================================
# 캐싱 함수 (속도 최적화)
# ============================================

@st.cache_data(ttl=30)  # 30초 캐싱
def cached_get_admin_services():
    """기성상품 목록 캐싱"""
    return get_admin_services()

@st.cache_data(ttl=30)
def cached_get_user_services(user_id: int):
    """개별상품 목록 캐싱"""
    return get_user_services(user_id)

@st.cache_data(ttl=30)
def cached_get_chapters(service_id: int):
    """목차 캐싱"""
    return get_chapters_by_service(service_id)

@st.cache_data(ttl=30)
def cached_get_guidelines(service_id: int):
    """지침 캐싱"""
    return get_guidelines_by_service(service_id)

@st.cache_data(ttl=30)
def cached_get_templates(service_id: int):
    """템플릿 캐싱"""
    return get_templates_by_service(service_id)

@st.cache_data(ttl=60)
def cached_get_notices():
    """공지사항 캐싱"""
    return get_all_notices()

def clear_service_cache():
    """서비스 관련 캐시 초기화 (데이터 변경 시 호출)"""
    cached_get_admin_services.clear()
    cached_get_user_services.clear()
    cached_get_chapters.clear()
    cached_get_guidelines.clear()
    cached_get_templates.clear()

def clear_notice_cache():
    """공지사항 캐시 초기화"""
    cached_get_notices.clear()

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
    
    /* text_area 힌트(Press Ctrl+Enter) 숨기기 */
    .stTextArea [data-testid="stTextAreaHelp"] { display: none !important; }
    .stTextArea small { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ============================================
# 세션 상태 초기화
# ============================================

defaults = {
    'logged_in': False, 'user': None, 'customers_df': None,
    'completed_customers': {}, 'generated_pdfs': {}, 'selected_customers': set(),
    'input_mode': 'excel', 'manual_completed': False, 'manual_pdf': None,
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
    chapters = cached_get_chapters(service_id)
    if not chapters:
        errors.append("❌ 목차가 등록되지 않았습니다.")
    if errors and any("❌" in e for e in errors):
        return False, errors
    return True, errors

def calculate_chars_per_page(font_size_body: int, line_height: int, margin_top: int, 
                            margin_bottom: int, margin_left: int, margin_right: int) -> int:
    """폰트/여백 설정 기반 페이지당 글자 수 계산
    
    A4 크기: 210mm x 297mm
    """
    # A4 사이즈 (mm)
    page_width_mm = 210
    page_height_mm = 297
    
    # 사용 가능한 영역
    usable_width = page_width_mm - margin_left - margin_right
    usable_height = page_height_mm - margin_top - margin_bottom
    
    # 글자 크기 (pt → mm 변환: 1pt ≈ 0.35mm)
    char_height_mm = font_size_body * 0.35
    char_width_mm = font_size_body * 0.35 * 0.5  # 한글은 대략 정사각형의 절반 폭
    
    # 행간 적용
    line_spacing_mm = char_height_mm * (line_height / 100)
    
    # 페이지당 줄 수
    lines_per_page = int(usable_height / line_spacing_mm)
    
    # 줄당 글자 수 (한글 기준)
    chars_per_line = int(usable_width / char_width_mm)
    
    # 페이지당 글자 수 (여유분 80% 적용)
    chars_per_page = int(lines_per_page * chars_per_line * 0.8)
    
    return max(chars_per_page, 300)  # 최소 300자


def render_font_settings(prefix: str, defaults: dict = None):
    """폰트/여백 설정 UI"""
    if defaults is None:
        defaults = {"font_family": "NanumGothic", "font_size_title": 24, "font_size_subtitle": 16,
                    "font_size_body": 12, "letter_spacing": 0, "line_height": 180, "char_width": 100,
                    "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
                    "target_pages": 30}
    
    # 목표 페이지 설정
    st.markdown("**📄 목표 페이지 수**")
    target_cols = st.columns([2, 3])
    with target_cols[0]:
        target_pages = st.number_input("목표 페이지", 10, 200, defaults.get("target_pages", 30), 
                                       step=5, key=f"{prefix}_pages",
                                       help="본문 페이지 수 (표지/목차/차트 제외)")
    
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
    
    # 페이지당 글자 수 계산 및 표시
    chars_per_page = calculate_chars_per_page(font_size_body, line_height, margin_top, 
                                               margin_bottom, margin_left, margin_right)
    with target_cols[1]:
        st.info(f"📊 현재 설정: 페이지당 약 **{chars_per_page:,}자** | 총 **{target_pages * chars_per_page:,}자** 예상")
    
    return {"font_family": font_family, "font_size_title": font_size_title, "font_size_subtitle": font_size_subtitle,
            "font_size_body": font_size_body, "letter_spacing": letter_spacing, "line_height": line_height,
            "char_width": char_width, "margin_top": margin_top, "margin_bottom": margin_bottom,
            "margin_left": margin_left, "margin_right": margin_right, "target_pages": target_pages}

# ============================================
# PDF 생성 함수
# ============================================

def generate_content_with_gpt(api_key: str, chapter_title: str, guideline: str, 
                              customer_data: dict, chars_per_chapter: int = 500,
                              all_chapters: list = None, current_index: int = 0) -> str:
    """GPT로 챕터 내용 생성
    
    Args:
        chars_per_chapter: 챕터당 목표 글자 수 (시스템이 자동 계산)
        all_chapters: 전체 목차 리스트 (맥락 제공용)
        current_index: 현재 챕터 인덱스
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        customer_info = "\n".join([f"- {k}: {v}" for k, v in customer_data.items()])
        
        # max_tokens 계산 (한글 1자 ≈ 2토큰, 여유분 1.5배)
        max_tokens = min(int(chars_per_chapter * 2 * 1.5), 4000)
        
        # 전체 목차 구조 생성
        toc_context = ""
        if all_chapters:
            toc_lines = []
            for i, ch in enumerate(all_chapters):
                if i == current_index:
                    toc_lines.append(f"  → {i+1}. {ch} ← [현재 작성할 챕터]")
                else:
                    toc_lines.append(f"     {i+1}. {ch}")
            toc_context = f"""
[전체 목차 구조]
{chr(10).join(toc_lines)}

"""
        
        prompt = f"""당신은 전문 운세 작성가입니다.

[고객 정보]
{customer_info}

[작성 지침]
{guideline}
{toc_context}
[현재 작성할 챕터]
{chapter_title}

위 정보를 바탕으로 '{chapter_title}' 챕터 내용을 작성해주세요.

🚨🚨🚨 최우선 규칙 - 글자수 🚨🚨🚨
- 목표 글자수: 정확히 {chars_per_chapter}자
- 최소 글자수: {int(chars_per_chapter * 0.9)}자 (이보다 적으면 안됨!)
- 최대 글자수: {int(chars_per_chapter * 1.1)}자
- 글자수가 부족하면 세부 내용, 예시, 조언을 더 추가하세요

📝 작성 규칙:
- 챕터 제목 '{chapter_title}'에 정확히 맞는 내용만 작성
- 다른 챕터 내용과 중복되지 않게 작성
- 고객 정보를 반영하여 개인화된 내용
- 긍정적이고 희망적인 톤
- 마크다운 없이 순수 텍스트
- 문단 나누어 가독성 높게 작성
- 내용이 풍부하고 구체적으로 작성

다시 한번 강조: 반드시 {chars_per_chapter}자 이상 작성하세요!"""
        
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens, temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[내용 생성 오류: {str(e)}]"


def generate_scores_with_gpt(api_key: str, customer_data: dict, service_type: str = "single") -> dict:
    """GPT로 운세/궁합 점수 생성"""
    try:
        from openai import OpenAI
        import json
        import random
        
        client = OpenAI(api_key=api_key)
        customer_info = "\n".join([f"- {k}: {v}" for k, v in customer_data.items()])
        
        if service_type == "couple":
            prompt = f"""당신은 전문 궁합 분석가입니다.

[고객 정보]
{customer_info}

위 두 사람의 정보를 바탕으로 궁합 점수를 JSON 형식으로 생성해주세요.
점수는 50-100 사이로 현실적으로 배분하세요.

응답 형식 (JSON만 출력):
{{
    "total_score": 82,
    "compatibility_scores": {{
        "성격궁합": 85,
        "감정궁합": 78,
        "금전궁합": 72,
        "육체궁합": 88,
        "미래궁합": 80
    }},
    "person1_elements": {{"木": 25, "火": 20, "土": 15, "金": 25, "水": 15}},
    "person2_elements": {{"木": 20, "火": 25, "土": 20, "金": 15, "水": 20}}
}}"""
        else:
            prompt = f"""당신은 전문 운세 분석가입니다.

[고객 정보]
{customer_info}

위 정보를 바탕으로 2025년 운세 점수를 JSON 형식으로 생성해주세요.
점수는 50-100 사이로 현실적으로 배분하세요.

응답 형식 (JSON만 출력):
{{
    "total_score": 78,
    "category_scores": {{
        "총운": 80,
        "재물운": 75,
        "건강운": 85,
        "애정운": 70,
        "직장운": 78
    }},
    "monthly_scores": {{
        "1월": 72, "2월": 75, "3월": 80, "4월": 78,
        "5월": 82, "6월": 85, "7월": 83, "8월": 80,
        "9월": 78, "10월": 75, "11월": 77, "12월": 82
    }},
    "five_elements": {{"木": 25, "火": 20, "土": 15, "金": 25, "水": 15}}
}}"""
        
        response = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}],
            max_tokens=500, temperature=0.7
        )
        
        result_text = response.choices[0].message.content.strip()
        # JSON 부분만 추출
        if '{' in result_text:
            start = result_text.index('{')
            end = result_text.rindex('}') + 1
            result_text = result_text[start:end]
        
        return json.loads(result_text)
    except Exception as e:
        # 오류 시 랜덤 점수 생성
        if service_type == "couple":
            return {
                "total_score": random.randint(65, 90),
                "compatibility_scores": {
                    "성격궁합": random.randint(60, 95),
                    "감정궁합": random.randint(60, 95),
                    "금전궁합": random.randint(60, 95),
                    "육체궁합": random.randint(60, 95),
                    "미래궁합": random.randint(60, 95),
                },
                "person1_elements": {"木": 22, "火": 23, "土": 18, "金": 20, "水": 17},
                "person2_elements": {"木": 20, "火": 25, "土": 15, "金": 22, "水": 18},
            }
        else:
            return {
                "total_score": random.randint(65, 90),
                "category_scores": {
                    "총운": random.randint(60, 95),
                    "재물운": random.randint(60, 95),
                    "건강운": random.randint(60, 95),
                    "애정운": random.randint(60, 95),
                    "직장운": random.randint(60, 95),
                },
                "monthly_scores": {f"{i}월": random.randint(60, 95) for i in range(1, 13)},
                "five_elements": {"木": 22, "火": 23, "土": 18, "金": 20, "水": 17},
            }


def create_pdf_document(customer_name: str, chapters_content: list, templates: dict, 
                        font_settings: dict, scores: dict = None, service_type: str = "single") -> bytes:
    """PDF 문서 생성 (차트 포함)"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import black, HexColor, white, lightgrey
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        
        # 차트 모듈 임포트
        try:
            from charts import (create_pie_chart, create_radar_chart, create_line_chart,
                              create_donut_chart, create_comparison_bar_chart,
                              save_chart_to_temp, cleanup_temp_charts)
            charts_available = True
        except ImportError:
            charts_available = False
        
        buffer = BytesIO()
        page_width, page_height = A4
        temp_chart_files = []
        
        # 한글 폰트 등록 (한자 지원 포함)
        font_name = 'Helvetica'
        try:
            font_paths = {
                'NanumGothic': '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                'NanumMyeongjo': '/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf',
                'NanumBarunGothic': '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
            }
            
            # 한자 지원 폰트 경로 (우선순위)
            cjk_font_paths = [
                '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
                '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
                '/usr/share/fonts/truetype/unfonts-core/UnBatang.ttf',
                '/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf',
            ]
            
            selected_font = font_settings.get('font_family', 'NanumGothic')
            
            # 먼저 한자 지원 폰트 시도
            font_registered = False
            for cjk_path in cjk_font_paths:
                if os.path.exists(cjk_path):
                    try:
                        if cjk_path.endswith('.ttc'):
                            pdfmetrics.registerFont(TTFont('KoreanFont', cjk_path, subfontIndex=0))
                        else:
                            pdfmetrics.registerFont(TTFont('KoreanFont', cjk_path))
                        font_name = 'KoreanFont'
                        font_registered = True
                        break
                    except:
                        continue
            
            # 한자 폰트 없으면 기존 나눔폰트 사용
            if not font_registered:
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
        
        # 내지 배경 이미지 경로
        bg_path = templates.get('background')
        
        # ========== 1. 표지 ==========
        cover_path = templates.get('cover')
        if cover_path and os.path.exists(cover_path):
            try:
                c.drawImage(cover_path, 0, 0, width=page_width, height=page_height)
                c.setFont(font_name, title_size)
                c.drawCentredString(page_width/2, 80, customer_name)
            except:
                c.setFont(font_name, title_size)
                c.drawCentredString(page_width/2, page_height/2, customer_name)
        else:
            c.setFont(font_name, title_size)
            c.drawCentredString(page_width/2, page_height/2, customer_name)
        c.showPage()
        
        # ========== 2. 목차 페이지 ==========
        # 목표 페이지 수 가져오기
        target_pages = font_settings.get('target_pages', 30)
        
        # 목차가 많으면 여러 페이지에 걸쳐 표시
        toc_page_num = 2
        items_per_page = 18  # 페이지당 목차 항목 수
        total_toc_pages = (len(chapters_content) + items_per_page - 1) // items_per_page
        
        for toc_page in range(total_toc_pages):
            if bg_path and os.path.exists(bg_path):
                try:
                    c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                except:
                    pass
            
            y_pos = page_height - margin_top
            
            # 목차 제목 (첫 페이지만)
            if toc_page == 0:
                c.setFont(font_name, subtitle_size + 4)
                c.setFillColor(HexColor('#1F2937'))
                c.drawCentredString(page_width/2, y_pos, "📋 목 차")
                y_pos -= 50
                
                # 구분선
                c.setStrokeColor(HexColor('#E5E7EB'))
                c.setLineWidth(1)
                c.line(margin_left + 30, y_pos, page_width - margin_right - 30, y_pos)
                y_pos -= 40
            else:
                y_pos -= 30
            
            # 목차 항목들
            c.setFont(font_name, body_size + 2)
            
            # 이 페이지에 표시할 항목 범위
            start_idx = toc_page * items_per_page
            end_idx = min(start_idx + items_per_page, len(chapters_content))
            
            for idx in range(start_idx, end_idx):
                chapter = chapters_content[idx]
                chapter_title = chapter['title']
                
                # 제목만 표시 (페이지 번호 없음)
                c.setFillColor(HexColor('#374151'))
                c.drawString(margin_left + 40, y_pos, chapter_title)
                
                y_pos -= 35
            
            # 목차 페이지 번호
            c.setFont(font_name, 10)
            c.setFillColor(HexColor('#9CA3AF'))
            c.drawCentredString(page_width/2, 15*mm, f"- {toc_page_num} -")
            c.showPage()
            toc_page_num += 1
        
        # ========== 3. 운세 요약 페이지 (차트) ==========
        if scores and charts_available:
            # 배경
            if bg_path and os.path.exists(bg_path):
                try:
                    c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                except:
                    pass
            
            y_pos = page_height - margin_top
            
            # 제목
            c.setFont(font_name, subtitle_size + 2)
            c.setFillColor(HexColor('#1F2937'))
            
            if service_type == "couple":
                c.drawCentredString(page_width/2, y_pos, "💑 궁합 분석 결과")
            else:
                c.drawCentredString(page_width/2, y_pos, "🔮 2025년 운세 요약")
            
            y_pos -= 30
            
            # 총점 도넛차트
            total_score = scores.get('total_score', 75)
            donut_bytes = create_donut_chart(total_score, 100, "")
            donut_path = save_chart_to_temp(donut_bytes, "donut")
            temp_chart_files.append(donut_path)
            
            c.drawImage(donut_path, page_width/2 - 50*mm, y_pos - 90*mm, 
                       width=100*mm, height=80*mm)
            
            # 총점 텍스트
            c.setFont(font_name, 14)
            c.setFillColor(HexColor('#6366F1'))
            c.drawCentredString(page_width/2, y_pos - 95*mm, "종합 운세 점수")
            
            y_pos -= 110*mm
            
            # 영역별 점수 (막대그래프)
            if service_type == "couple":
                category_scores = scores.get('compatibility_scores', {})
                c.setFont(font_name, 12)
                c.setFillColor(HexColor('#374151'))
                c.drawString(margin_left, y_pos, "📊 영역별 궁합")
            else:
                category_scores = scores.get('category_scores', {})
                c.setFont(font_name, 12)
                c.setFillColor(HexColor('#374151'))
                c.drawString(margin_left, y_pos, "📊 영역별 운세")
            
            y_pos -= 20
            
            # 막대그래프 직접 그리기
            bar_height = 15
            bar_width = page_width - margin_left - margin_right - 80
            
            for label, value in category_scores.items():
                # 라벨
                c.setFont(font_name, 10)
                c.setFillColor(HexColor('#374151'))
                c.drawRightString(margin_left + 55, y_pos + 3, label)
                
                # 배경 막대
                c.setFillColor(HexColor('#E5E7EB'))
                c.rect(margin_left + 60, y_pos, bar_width, bar_height, fill=1, stroke=0)
                
                # 값 막대
                if value >= 80:
                    bar_color = '#10B981'
                elif value >= 60:
                    bar_color = '#3B82F6'
                elif value >= 40:
                    bar_color = '#F59E0B'
                else:
                    bar_color = '#EF4444'
                
                c.setFillColor(HexColor(bar_color))
                c.rect(margin_left + 60, y_pos, bar_width * (value/100), bar_height, fill=1, stroke=0)
                
                # 값 텍스트
                c.setFillColor(HexColor('#374151'))
                c.setFont(font_name, 9)
                c.drawString(margin_left + 65 + bar_width, y_pos + 3, f'{value}점')
                
                y_pos -= 25
            
            c.setFont(font_name, 10)
            chart_page_1 = 1 + total_toc_pages + 1  # 표지 + 목차페이지들 + 1
            c.drawCentredString(page_width/2, 15*mm, f"- {chart_page_1} -")
            c.showPage()
            
            # ========== 3. 상세 차트 페이지 ==========
            if bg_path and os.path.exists(bg_path):
                try:
                    c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                except:
                    pass
            
            y_pos = page_height - margin_top
            
            if service_type == "couple":
                # 궁합: 오행 비교 차트
                c.setFont(font_name, subtitle_size)
                c.setFillColor(HexColor('#1F2937'))
                c.drawCentredString(page_width/2, y_pos, "🌟 오행 분석")
                y_pos -= 20
                
                # 두 사람 오행 파이차트
                p1_elements = scores.get('person1_elements', {})
                p2_elements = scores.get('person2_elements', {})
                
                if p1_elements:
                    pie1_bytes = create_pie_chart(p1_elements, "고객1", figsize=(3.5, 3.5))
                    pie1_path = save_chart_to_temp(pie1_bytes, "pie1")
                    temp_chart_files.append(pie1_path)
                    c.drawImage(pie1_path, margin_left, y_pos - 70*mm, width=70*mm, height=70*mm)
                
                if p2_elements:
                    pie2_bytes = create_pie_chart(p2_elements, "고객2", figsize=(3.5, 3.5))
                    pie2_path = save_chart_to_temp(pie2_bytes, "pie2")
                    temp_chart_files.append(pie2_path)
                    c.drawImage(pie2_path, page_width - margin_right - 70*mm, y_pos - 70*mm, 
                               width=70*mm, height=70*mm)
                
                y_pos -= 85*mm
                
                # 궁합 레이더 차트
                c.setFont(font_name, 12)
                c.setFillColor(HexColor('#374151'))
                c.drawCentredString(page_width/2, y_pos, "📈 궁합 종합 분석")
                
                radar_bytes = create_radar_chart(category_scores, "", figsize=(4.5, 4.5))
                radar_path = save_chart_to_temp(radar_bytes, "radar")
                temp_chart_files.append(radar_path)
                c.drawImage(radar_path, page_width/2 - 45*mm, y_pos - 95*mm, 
                           width=90*mm, height=90*mm)
                
            else:
                # 1인용: 월별 운세 + 오행
                c.setFont(font_name, subtitle_size)
                c.setFillColor(HexColor('#1F2937'))
                c.drawCentredString(page_width/2, y_pos, "📈 월별 운세 흐름")
                y_pos -= 10
                
                # 월별 라인차트
                monthly_scores = scores.get('monthly_scores', {})
                if monthly_scores:
                    line_bytes = create_line_chart(monthly_scores, "", figsize=(6.5, 2.5))
                    line_path = save_chart_to_temp(line_bytes, "line")
                    temp_chart_files.append(line_path)
                    c.drawImage(line_path, margin_left, y_pos - 55*mm, 
                               width=page_width - margin_left - margin_right, height=55*mm)
                
                y_pos -= 70*mm
                
                # 오행 밸런스
                c.setFont(font_name, 12)
                c.setFillColor(HexColor('#374151'))
                c.drawString(margin_left, y_pos, "🌟 오행 밸런스")
                
                five_elements = scores.get('five_elements', {})
                if five_elements:
                    pie_bytes = create_pie_chart(five_elements, "", figsize=(3.5, 3.5))
                    pie_path = save_chart_to_temp(pie_bytes, "pie")
                    temp_chart_files.append(pie_path)
                    c.drawImage(pie_path, margin_left + 10*mm, y_pos - 75*mm, 
                               width=70*mm, height=70*mm)
                
                # 레이더 차트
                c.setFont(font_name, 12)
                c.setFillColor(HexColor('#374151'))
                c.drawString(page_width/2 + 5*mm, y_pos, "📊 영역별 분석")
                
                radar_bytes = create_radar_chart(category_scores, "", figsize=(3.5, 3.5))
                radar_path = save_chart_to_temp(radar_bytes, "radar")
                temp_chart_files.append(radar_path)
                c.drawImage(radar_path, page_width/2 + 5*mm, y_pos - 75*mm, 
                           width=70*mm, height=70*mm)
            
            c.setFont(font_name, 10)
            chart_page_2 = 1 + total_toc_pages + 2  # 표지 + 목차페이지들 + 2
            c.drawCentredString(page_width/2, 15*mm, f"- {chart_page_2} -")
            c.showPage()
        
        # ========== 4. 본문 ==========
        # 본문 시작 페이지: 표지(1) + 목차(total_toc_pages) + 차트(2 or 0)
        chart_pages = 2 if (scores and charts_available) else 0
        page_num = 1 + total_toc_pages + chart_pages + 1
        
        for idx, chapter in enumerate(chapters_content):
            if bg_path and os.path.exists(bg_path):
                try:
                    c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                except:
                    pass
            
            y_pos = page_height - margin_top
            max_width = page_width - margin_left - margin_right
            
            c.setFont(font_name, subtitle_size)
            c.setFillColor(black)
            c.drawString(margin_left, y_pos, f"● {chapter['title']}")
            y_pos -= subtitle_size * 2
            
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
                                c.drawCentredString(page_width/2, 15*mm, f"- {page_num} -")
                                c.showPage()
                                page_num += 1
                                if bg_path and os.path.exists(bg_path):
                                    try:
                                        c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                                    except:
                                        pass
                                y_pos = page_height - margin_top
                                c.setFont(font_name, body_size)
                            c.drawString(margin_left, y_pos, current_line)
                            y_pos -= line_spacing
                        current_line = char
                if current_line:
                    if y_pos < margin_bottom + 30:
                        c.setFont(font_name, 10)
                        c.drawCentredString(page_width/2, 15*mm, f"- {page_num} -")
                        c.showPage()
                        page_num += 1
                        if bg_path and os.path.exists(bg_path):
                            try:
                                c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                            except:
                                pass
                        y_pos = page_height - margin_top
                        c.setFont(font_name, body_size)
                    c.drawString(margin_left, y_pos, current_line)
                    y_pos -= line_spacing
                y_pos -= line_spacing * 0.5
            
            c.setFont(font_name, 10)
            c.drawCentredString(page_width/2, 15*mm, f"- {page_num} -")
            c.showPage()
            page_num += 1
        
        # ========== 5. 안내지 ==========
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
        c.showPage()
        
        c.save()
        
        # 임시 차트 파일 정리
        if temp_chart_files:
            try:
                cleanup_temp_charts(temp_chart_files)
            except:
                pass
        
        return buffer.getvalue()
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None
        
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
        
        # 내지 배경 이미지 경로
        bg_path = templates.get('background')
        
        # 1. 표지
        cover_path = templates.get('cover')
        if cover_path and os.path.exists(cover_path):
            try:
                c.drawImage(cover_path, 0, 0, width=page_width, height=page_height)
                # 표지 하단에 고객 이름 표시
                c.setFont(font_name, title_size)
                c.drawCentredString(page_width/2, 80, customer_name)
            except:
                c.setFont(font_name, title_size)
                c.drawCentredString(page_width/2, page_height/2, customer_name)
        else:
            c.setFont(font_name, title_size)
            c.drawCentredString(page_width/2, page_height/2, customer_name)
        c.showPage()
        
        # 2. 본문
        page_num = 2  # 표지가 1페이지이므로 본문은 2페이지부터
        
        for idx, chapter in enumerate(chapters_content):
            # 내지 배경 이미지 그리기
            if bg_path and os.path.exists(bg_path):
                try:
                    c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                except:
                    pass
            
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
                                # 현재 페이지 마무리
                                c.setFont(font_name, 10)
                                c.drawCentredString(page_width/2, 15*mm, f"- {page_num} -")
                                c.showPage()
                                page_num += 1
                                # 새 페이지에 내지 배경 적용
                                if bg_path and os.path.exists(bg_path):
                                    try:
                                        c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                                    except:
                                        pass
                                y_pos = page_height - margin_top
                                c.setFont(font_name, body_size)
                            c.drawString(margin_left, y_pos, current_line)
                            y_pos -= line_spacing
                        current_line = char
                if current_line:
                    if y_pos < margin_bottom + 30:
                        # 현재 페이지 마무리
                        c.setFont(font_name, 10)
                        c.drawCentredString(page_width/2, 15*mm, f"- {page_num} -")
                        c.showPage()
                        page_num += 1
                        # 새 페이지에 내지 배경 적용
                        if bg_path and os.path.exists(bg_path):
                            try:
                                c.drawImage(bg_path, 0, 0, width=page_width, height=page_height)
                            except:
                                pass
                        y_pos = page_height - margin_top
                        c.setFont(font_name, body_size)
                    c.drawString(margin_left, y_pos, current_line)
                    y_pos -= line_spacing
                y_pos -= line_spacing * 0.5
            
            # 챕터 끝 - 페이지 번호 표시하고 다음 페이지로
            c.setFont(font_name, 10)
            c.drawCentredString(page_width/2, 15*mm, f"- {page_num} -")
            c.showPage()
            page_num += 1
        
        # 3. 안내지 (페이지 번호 없음)
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
        c.showPage()  # 안내지 페이지 마무리
        
        c.save()
        return buffer.getvalue()
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None


def generate_pdf_for_customer(customer_data: dict, service: dict, api_key: str, 
                              progress_callback=None, customer_idx=None) -> bytes:
    """고객용 PDF 생성 (진행률 콜백 포함)"""
    service_id = service['id']
    service_type = service.get('service_type', 'single')
    chapters = cached_get_chapters(service_id)
    guidelines = cached_get_guidelines(service_id)
    guideline_text = guidelines[0]['content'] if guidelines else "친절하고 긍정적인 톤으로 작성하세요."
    
    templates_list = cached_get_templates(service_id)
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
                      "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
                      "target_pages": 30}.items()}
    
    # ========== 챕터당 글자 수 계산 ==========
    target_pages = service.get('target_pages', 30)
    chars_per_page = calculate_chars_per_page(
        font_settings['font_size_body'],
        font_settings['line_height'],
        font_settings['margin_top'],
        font_settings['margin_bottom'],
        font_settings['margin_left'],
        font_settings['margin_right']
    )
    
    total_chapters = len(chapters)
    if total_chapters > 0:
        total_chars = target_pages * chars_per_page
        chars_per_chapter = total_chars // total_chapters
    else:
        chars_per_chapter = 500
    
    # 점수 생성 (차트용)
    scores = generate_scores_with_gpt(api_key, customer_data, service_type)
    
    chapters_content = []
    
    # 전체 목차 제목 리스트 (GPT에게 맥락 제공용)
    all_chapter_titles = [ch['title'] for ch in chapters]
    
    for i, ch in enumerate(chapters):
        content = generate_content_with_gpt(
            api_key, ch['title'], guideline_text, customer_data, 
            chars_per_chapter, all_chapter_titles, i
        )
        chapters_content.append({"title": ch['title'], "content": content})
        
        if progress_callback and customer_idx is not None:
            progress = (i + 1) / total_chapters
            progress_callback(customer_idx, progress)
    
    return create_pdf_document(f"{customer_name}님", chapters_content, templates, font_settings,
                               scores=scores, service_type=service_type)


def generate_pdf_with_progress(customer_data: dict, service: dict, api_key: str,
                               progress_bar, detail_text, custom_name: str = None) -> bytes:
    """고객용 PDF 생성 - 실시간 진행률 표시"""
    service_id = service['id']
    service_type = service.get('service_type', 'single')
    chapters = cached_get_chapters(service_id)
    guidelines = cached_get_guidelines(service_id)
    guideline_text = guidelines[0]['content'] if guidelines else "친절하고 긍정적인 톤으로 작성하세요."
    
    templates_list = cached_get_templates(service_id)
    templates = {t['template_type']: t['image_path'] for t in templates_list 
                 if t.get('image_path') and os.path.exists(t['image_path'])}
    
    # 표지용 이름 결정
    if custom_name:
        customer_name = custom_name
    else:
        name_col = None
        for col in ['이름', 'name', 'Name', '성명', '고객명']:
            if col in customer_data:
                name_col = col
                break
        customer_name = customer_data.get(name_col, "고객") if name_col else "고객"
    
    font_settings = {k: service.get(k, v) for k, v in 
                     {"font_family": "NanumGothic", "font_size_title": 24, "font_size_subtitle": 16,
                      "font_size_body": 12, "letter_spacing": 0, "line_height": 180, "char_width": 100,
                      "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
                      "target_pages": 30}.items()}
    
    # ========== 챕터당 글자 수 계산 ==========
    target_pages = service.get('target_pages', 30)
    chars_per_page = calculate_chars_per_page(
        font_settings['font_size_body'],
        font_settings['line_height'],
        font_settings['margin_top'],
        font_settings['margin_bottom'],
        font_settings['margin_left'],
        font_settings['margin_right']
    )
    
    total_chapters = len(chapters)
    if total_chapters > 0:
        # 총 글자 수 / 챕터 수 = 챕터당 글자 수
        total_chars = target_pages * chars_per_page
        chars_per_chapter = total_chars // total_chapters
    else:
        chars_per_chapter = 500  # 기본값
    
    # 초기 진행률 0%
    progress_bar.progress(0.0, text="0%")
    detail_text.caption(f"📊 운세 점수 분석 중... (목표: {target_pages}페이지, 챕터당 {chars_per_chapter:,}자)")
    
    # 점수 생성 (차트용)
    scores = generate_scores_with_gpt(api_key, customer_data, service_type)
    progress_bar.progress(0.1, text="10%")
    
    chapters_content = []
    
    # 전체 목차 제목 리스트 (GPT에게 맥락 제공용)
    all_chapter_titles = [ch['title'] for ch in chapters]
    
    for i, ch in enumerate(chapters):
        detail_text.caption(f"📝 {ch['title']} 작성 중... ({chars_per_chapter:,}자)")
        
        # 글자 수 + 전체 목차 + 현재 인덱스 전달하여 GPT 호출
        content = generate_content_with_gpt(
            api_key, ch['title'], guideline_text, customer_data, 
            chars_per_chapter, all_chapter_titles, i
        )
        chapters_content.append({"title": ch['title'], "content": content})
        
        # 진행률 실시간 업데이트 (10% ~ 95%)
        progress = 0.1 + (i + 1) / total_chapters * 0.85
        progress_bar.progress(progress, text=f"{int(progress * 100)}%")
        time.sleep(0.1)
    
    detail_text.caption("📄 PDF 생성 중...")
    
    # 표지 이름 처리
    if custom_name:
        cover_display_name = custom_name
    else:
        cover_display_name = f"{customer_name}님"
    
    return create_pdf_document(cover_display_name, chapters_content, templates, font_settings, 
                               scores=scores, service_type=service_type)

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
    tab1, tab2, tab3 = st.tabs(["📦 기성상품 등록", "👥 회원관리", "🔑 API/이메일"])
    
    with tab1:
        st.markdown('<span class="section-title">📦 기성상품 등록</span>', unsafe_allow_html=True)
        
        # 새 상품 등록 토글
        if 'show_new_product' not in st.session_state:
            st.session_state.show_new_product = False
        
        if st.button("➕ 새 기성상품 등록" if not st.session_state.show_new_product else "➖ 접기"):
            st.session_state.show_new_product = not st.session_state.show_new_product
            st.rerun()
        
        if st.session_state.show_new_product:
            st.markdown("---")
            product_name = st.text_input("상품명", key="new_prod")
            
            # 목차/지침 좌우 배치
            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown("**📑 목차** (줄바꿈 구분)")
                new_chapters = st.text_area("목차", height=500, key="new_ch", placeholder="1. 총운\n2. 재물운\n3. 건강운")
            with col_right:
                st.markdown("**📜 AI 작성 지침**")
                new_guideline = st.text_area("지침", height=500, key="new_g", placeholder="- 긍정적 톤\n- 300자 이상")
            
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
                            # 배치 처리로 한 번에 추가 (속도 개선)
                            chapter_list = [ch.strip() for ch in new_chapters.strip().split("\n") if ch.strip()]
                            add_chapters_bulk(svc_id, chapter_list)
                        if new_guideline:
                            add_guideline(svc_id, f"{product_name} 지침", new_guideline)
                        if cover:
                            add_template(svc_id, "cover", "표지", save_uploaded_file(cover, f"{product_name}_cover"))
                        if bg:
                            add_template(svc_id, "background", "내지", save_uploaded_file(bg, f"{product_name}_bg"))
                        if info:
                            add_template(svc_id, "info", "안내지", save_uploaded_file(info, f"{product_name}_info"))
                        st.success(f"'{product_name}' 등록됨!")
                        st.session_state.show_new_product = False
                        clear_service_cache()
                        st.rerun()
            st.markdown("---")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("**등록된 기성상품**")
        
        services = cached_get_admin_services()
        if not services:
            st.info("등록된 기성상품이 없습니다.")
        else:
            for svc in services:
                with st.expander(f"📌 {svc['name']}"):
                    show_service_edit_form(svc, "admin")
    
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

def show_service_edit_form(svc: dict, prefix: str):
    """상품 수정 폼"""
    svc_id = svc['id']
    chapters = cached_get_chapters(svc_id)
    guidelines = cached_get_guidelines(svc_id)
    templates = cached_get_templates(svc_id)
    
    edit_name = st.text_input("상품명", value=svc['name'], key=f"{prefix}_name_{svc_id}")
    
    # 좌우 배치
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("**📑 목차**")
        current_chapters = "\n".join([ch['title'] for ch in chapters])
        edit_chapters = st.text_area("목차", value=current_chapters, height=350, key=f"{prefix}_ch_{svc_id}")
    with col_right:
        st.markdown("**📜 지침**")
        current_guideline = guidelines[0]['content'] if guidelines else ""
        edit_guideline = st.text_area("지침", value=current_guideline, height=350, key=f"{prefix}_g_{svc_id}")
    
    font_defaults = {k: svc.get(k, v) for k, v in 
                     {"font_family": "NanumGothic", "font_size_title": 24, "font_size_subtitle": 16,
                      "font_size_body": 12, "letter_spacing": 0, "line_height": 180, "char_width": 100,
                      "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
                      "target_pages": 30}.items()}
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
            # 캐시 먼저 초기화 (중복 방지)
            clear_service_cache()
            
            # 기존 목차 배치 삭제
            delete_chapters_by_service(svc_id)
            
            # 새 목차 배치 추가
            chapter_list = [ch.strip() for ch in edit_chapters.strip().split("\n") if ch.strip()]
            add_chapters_bulk(svc_id, chapter_list)
            
            # 서비스 업데이트
            update_service(svc_id, name=edit_name, **font_settings)
            
            # 지침 업데이트
            fresh_guidelines = get_guidelines_by_service(svc_id)
            if fresh_guidelines:
                update_guideline(fresh_guidelines[0]['id'], fresh_guidelines[0]['title'], edit_guideline)
            elif edit_guideline:
                add_guideline(svc_id, f"{edit_name} 지침", edit_guideline)
            
            # 템플릿 업데이트
            fresh_templates = get_templates_by_service(svc_id)
            for tt in ["cover", "background", "info"]:
                new_file = st.session_state.get(f"{prefix}_{tt}_{svc_id}")
                if new_file:
                    for t in fresh_templates:
                        if t['template_type'] == tt:
                            delete_template(t['id'])
                    add_template(svc_id, tt, TEMPLATE_TYPES[tt], save_uploaded_file(new_file, f"{edit_name}_{tt}"))
            
            st.success("저장됨!")
            st.rerun()
    with col2:
        if st.button("🗑️ 삭제", key=f"{prefix}_del_{svc_id}", use_container_width=True):
            delete_service(svc_id)
            clear_service_cache()
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
        admin_services = cached_get_admin_services()
        if admin_services:
            svc_names = [s['name'] for s in admin_services]
            selected_idx = st.selectbox("기성상품 목록", range(len(admin_services)), 
                                       format_func=lambda x: svc_names[x], key="ready_svc")
            selected_service = admin_services[selected_idx]
            if selected_service:
                chapters = cached_get_chapters(selected_service['id'])
                st.success(f"✅ '{selected_service['name']}' 선택됨 (목차 {len(chapters)}개)")
        else:
            st.warning("등록된 기성상품이 없습니다.")
    
    # 2. 개별상품
    elif "개별상품" in product_type:
        st.markdown('<span class="section-title">2️⃣ 개별상품</span>', unsafe_allow_html=True)
        my_services = cached_get_user_services(user['id'])
        
        if my_services:
            my_names = ["➕ 새로 만들기"] + [s['name'] for s in my_services]
            selected_idx = st.selectbox("내 상품 목록", range(len(my_names)), 
                                       format_func=lambda x: my_names[x], key="my_svc")
            
            if selected_idx > 0:
                selected_service = my_services[selected_idx - 1]
                if selected_service:
                    chapters = cached_get_chapters(selected_service['id'])
                    st.success(f"✅ '{selected_service['name']}' 선택됨 (목차 {len(chapters)}개)")
                    with st.expander("✏️ 상품 수정", expanded=False):
                        show_service_edit_form(selected_service, "my")
            else:
                selected_idx = 0
        else:
            selected_idx = 0
        
        if not my_services or selected_idx == 0:
            with st.expander("➕ 개별상품 만들기", expanded=True):
                my_name = st.text_input("상품명", key="my_prod")
                
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("**📑 목차**")
                    my_chapters = st.text_area("목차", height=350, key="my_ch")
                with col_right:
                    st.markdown("**📜 지침**")
                    my_guide = st.text_area("지침", height=350, key="my_g")
                
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
                            # 배치 처리로 한 번에 추가
                            chapter_list = [ch.strip() for ch in my_chapters.strip().split("\n") if ch.strip()]
                            add_chapters_bulk(svc_id, chapter_list)
                            if my_guide:
                                add_guideline(svc_id, f"{my_name} 지침", my_guide)
                            if my_cover:
                                add_template(svc_id, "cover", "표지", save_uploaded_file(my_cover, f"{my_name}_cover"))
                            if my_bg:
                                add_template(svc_id, "background", "내지", save_uploaded_file(my_bg, f"{my_name}_bg"))
                            if my_info:
                                add_template(svc_id, "info", "안내지", save_uploaded_file(my_info, f"{my_name}_info"))
                            st.success("저장됨!")
                            clear_service_cache()
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
    
    # 고객 정보 입력 방식 선택
    st.markdown("**📋 고객 정보 입력 방식**")
    input_method = st.radio(
        "입력 방식",
        ["📂 엑셀 업로드", "✏️ 직접 입력 (최대 2명)"],
        horizontal=True,
        key="input_method"
    )
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== 엑셀 업로드 방식 =====
    if "엑셀" in input_method:
        # 컬럼 형식 안내
        st.markdown("""
        **📋 엑셀 컬럼 형식**
        - **1인용**: 이름, 생년월일, 음력양력, 태어난시간, 이메일
        - **2인용 (궁합/재회)**: 고객1_이름, 고객1_생년월일, 고객1_음력양력, 고객1_태어난시간, 고객2_이름, 고객2_생년월일, 고객2_음력양력, 고객2_태어난시간, 이메일
        """)
        
        uploaded = st.file_uploader("📂 고객 엑셀 파일 (.xlsx)", type=["xlsx", "xls"], key="cust")
        
        if uploaded:
            df = pd.read_excel(uploaded)
            st.session_state.customers_df = df
            st.session_state.selected_customers = set(range(len(df)))
            st.session_state.input_mode = "excel"
            st.success(f"✅ {len(df)}건 로드됨")
        
        if st.session_state.customers_df is not None and st.session_state.get('input_mode') == 'excel':
            df = st.session_state.customers_df
            
            # 컬럼명으로 1인/2인 자동 판별
            is_couple = any(col in df.columns for col in ['고객1_이름', '고객1이름', '고객2_이름', '고객2이름'])
            
            if is_couple:
                st.info("💑 **2인용 (궁합/재회)** 데이터로 인식됨")
                svc_type = 'couple'
                # 2인용 컬럼 찾기
                name1_col = None
                name2_col = None
                for col in ['고객1_이름', '고객1이름', 'name1', 'Name1']:
                    if col in df.columns:
                        name1_col = col
                        break
                for col in ['고객2_이름', '고객2이름', 'name2', 'Name2']:
                    if col in df.columns:
                        name2_col = col
                        break
                if not name1_col:
                    name1_col = df.columns[0]
                if not name2_col and len(df.columns) > 1:
                    name2_col = df.columns[1]
            else:
                st.info("👤 **1인용** 데이터로 인식됨")
                svc_type = 'single'
                # 1인용 컬럼 찾기
                name_col = None
                for col in ['이름', 'name', 'Name', '성명', '고객명']:
                    if col in df.columns:
                        name_col = col
                        break
                if not name_col:
                    name_col = df.columns[0]
            
            st.markdown("---")
            
            # 전체 선택 + 초기화
            col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 1])
            with col_ctrl1:
                if st.button("✅ 전체 선택", use_container_width=True):
                    st.session_state.selected_customers = set(range(len(df)))
                    st.rerun()
            with col_ctrl2:
                if st.button("⬜ 전체 해제", use_container_width=True):
                    st.session_state.selected_customers = set()
                    st.rerun()
            with col_ctrl3:
                if st.button("🔄 초기화", use_container_width=True):
                    # 모든 엑셀 관련 세션 완전 삭제
                    st.session_state.customers_df = None
                    st.session_state.completed_customers = {}
                    st.session_state.generated_pdfs = {}
                    st.session_state.selected_customers = set()
                    st.session_state.input_mode = None
                    # 체크박스 키들도 삭제
                    keys_to_delete = [k for k in st.session_state.keys() if k.startswith('chk_')]
                    for k in keys_to_delete:
                        del st.session_state[k]
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
                # 컬럼 유형에 따른 이름 표시
                if is_couple:
                    cust_name1 = row.get(name1_col, "고객1") if name1_col else "고객1"
                    cust_name2 = row.get(name2_col, "고객2") if name2_col else "고객2"
                    display_name = f"{cust_name1} & {cust_name2}"
                else:
                    display_name = row.get(name_col, "고객") if name_col else "고객"
                
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
                    st.write(f"**{display_name}**")
                
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
                            # 파일명 결정
                            if is_couple:
                                filename = f"{cust_name1}_{cust_name2}_궁합.pdf"
                            else:
                                filename = f"{display_name}_운세.pdf"
                            st.download_button("⬇️", pdf_data, filename,
                                              "application/pdf", key=f"dl_{idx}")
            
            st.markdown("---")
            
            pending_selected = [i for i in st.session_state.selected_customers
                              if i not in st.session_state.completed_customers]
            
            st.info(f"📊 선택: {len(st.session_state.selected_customers)}건 | 완료: {len(st.session_state.completed_customers)}/{len(df)}")
            
            if st.button(f"🚀 선택한 {len(pending_selected)}건 PDF 생성", type="primary", use_container_width=True):
                if not pending_selected:
                    st.warning("생성할 고객을 선택하세요.")
                else:
                    status_area = st.empty()
                    current_progress_bar = st.empty()
                    current_detail = st.empty()
                    
                    for i, idx in enumerate(pending_selected):
                        row = df.iloc[idx]
                        
                        # 컬럼 유형에 따른 이름 및 표지 이름 결정
                        if is_couple:
                            cust_name1 = row.get(name1_col, "고객1") if name1_col else "고객1"
                            cust_name2 = row.get(name2_col, "고객2") if name2_col else "고객2"
                            display_name = f"{cust_name1} & {cust_name2}"
                            cover_name = f"{cust_name1}님 & {cust_name2}님"
                            current_svc_type = "couple"
                        else:
                            display_name = row.get(name_col, "고객") if name_col else "고객"
                            cover_name = f"{display_name}님"
                            current_svc_type = "single"
                        
                        status_area.markdown(f"### 📝 {display_name} 생성 중... ({i+1}/{len(pending_selected)})")
                        
                        # 서비스에 현재 유형 임시 설정
                        temp_service = selected_service.copy()
                        temp_service['service_type'] = current_svc_type
                        
                        pdf_bytes = generate_pdf_with_progress(
                            row.to_dict(), temp_service, api_key,
                            current_progress_bar, current_detail,
                            custom_name=cover_name
                        )
                        
                        if pdf_bytes:
                            st.session_state.completed_customers[idx] = True
                            st.session_state.generated_pdfs[idx] = pdf_bytes
                            st.toast(f"🔔 {display_name} 완료!")
                        
                        current_progress_bar.progress(1.0, text="100% 완료")
                        time.sleep(0.3)
                    
                    status_area.markdown("### ✅ 모든 PDF 생성 완료!")
                    current_progress_bar.empty()
                    current_detail.empty()
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
    
    # ===== 직접 입력 방식 =====
    else:
        st.markdown("**👤 고객 정보 직접 입력** (최대 2명)")
        st.caption("💡 2명 입력 시 궁합/재회용 PDF 생성")
        
        # 초기화 버튼
        col_reset = st.columns([3, 1])
        with col_reset[1]:
            if st.button("🔄 초기화", key="reset_manual", use_container_width=True):
                # 모든 직접 입력 관련 세션 완전 삭제
                st.session_state.manual_completed = False
                st.session_state.manual_pdf = None
                # 입력 폼 키들도 삭제
                keys_to_delete = [k for k in st.session_state.keys() if k.startswith('manual_')]
                for k in keys_to_delete:
                    del st.session_state[k]
                st.rerun()
        
        # 고객 수 선택
        num_customers = st.radio("고객 수", [1, 2], horizontal=True, key="num_cust",
                                help="2명 입력 시 궁합/재회 등 합산 PDF 1개 생성")
        
        manual_customers = []
        
        for i in range(num_customers):
            st.markdown(f"**고객 {i+1}**")
            
            # 1행: 이름, 이메일
            row1 = st.columns(2)
            with row1[0]:
                name = st.text_input("이름", key=f"manual_name_{i}", placeholder="홍길동")
            with row1[1]:
                email = st.text_input("이메일", key=f"manual_email_{i}", placeholder="example@email.com")
            
            # 2행: 생년월일, 음력/양력
            row2 = st.columns([2, 1])
            with row2[0]:
                birth_date = st.date_input("생년월일", key=f"manual_birth_{i}",
                                          value=datetime(1990, 1, 1).date(),
                                          min_value=datetime(1920, 1, 1).date(),
                                          max_value=datetime(2025, 12, 31).date())
            with row2[1]:
                calendar_type = st.radio("음력/양력", ["양력", "음력"], horizontal=True, key=f"manual_cal_{i}")
            
            # 3행: 태어난 시간
            row3 = st.columns([1, 1, 1])
            with row3[0]:
                birth_hour = st.selectbox("시", list(range(1, 13)), index=8, key=f"manual_hour_{i}")
            with row3[1]:
                birth_min = st.selectbox("분", list(range(0, 60, 5)), index=0, key=f"manual_min_{i}")
            with row3[2]:
                ampm = st.radio("오전/오후", ["오전", "오후"], horizontal=True, key=f"manual_ampm_{i}")
            
            if name:
                # 시간 포맷팅
                birth_date_str = birth_date.strftime("%Y-%m-%d")
                birth_time_str = f"{ampm} {birth_hour}시 {birth_min:02d}분"
                
                manual_customers.append({
                    "이름": name,
                    "생년월일": birth_date_str,
                    "음력양력": calendar_type,
                    "태어난시간": birth_time_str,
                    "이메일": email
                })
            
            if i < num_customers - 1:
                st.markdown("---")
        
        # 세션 초기화
        if 'manual_completed' not in st.session_state:
            st.session_state.manual_completed = False
        if 'manual_pdf' not in st.session_state:
            st.session_state.manual_pdf = None
        
        # 필수 입력 확인
        required_count = num_customers
        has_all_names = len(manual_customers) == required_count
        
        if has_all_names:
            st.markdown("---")
            
            # 1명 또는 2명에 따른 표시
            if num_customers == 1:
                display_name = manual_customers[0]['이름']
                cover_name = f"{display_name}님"  # 표지용: "홍길동님"
                combined_data = manual_customers[0]
            else:
                # 2명: 궁합/재회용 - 데이터 합치기
                display_name = f"{manual_customers[0]['이름']} & {manual_customers[1]['이름']}"
                cover_name = f"{manual_customers[0]['이름']}님 & {manual_customers[1]['이름']}님"  # 표지용: "홍길동님 & 김철수님"
                combined_data = {
                    "고객1_이름": manual_customers[0]['이름'],
                    "고객1_생년월일": manual_customers[0]['생년월일'],
                    "고객1_음력양력": manual_customers[0]['음력양력'],
                    "고객1_태어난시간": manual_customers[0]['태어난시간'],
                    "고객1_이메일": manual_customers[0]['이메일'],
                    "고객2_이름": manual_customers[1]['이름'],
                    "고객2_생년월일": manual_customers[1]['생년월일'],
                    "고객2_음력양력": manual_customers[1]['음력양력'],
                    "고객2_태어난시간": manual_customers[1]['태어난시간'],
                    "고객2_이메일": manual_customers[1]['이메일'],
                }
            
            st.markdown("**📋 입력된 고객**")
            
            # 상세 정보 표시
            for idx, cust in enumerate(manual_customers):
                info_text = f"**{cust['이름']}** | {cust['생년월일']} ({cust['음력양력']}) | {cust['태어난시간']}"
                st.caption(info_text)
            
            st.markdown("---")
            
            # 상태 표시
            is_done = st.session_state.manual_completed
            
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                st.write(f"**{display_name}**")
            with col2:
                if is_done:
                    st.progress(1.0, text="100%")
                else:
                    st.progress(0.0, text="대기")
            with col3:
                if is_done:
                    st.markdown("✅")
            with col4:
                if is_done and st.session_state.manual_pdf:
                    filename = f"{manual_customers[0]['이름']}_운세.pdf" if num_customers == 1 else f"{manual_customers[0]['이름']}_{manual_customers[1]['이름']}_궁합.pdf"
                    st.download_button("⬇️", st.session_state.manual_pdf, filename,
                                      "application/pdf", key="dl_manual")
            
            st.markdown("---")
            
            if not is_done:
                if num_customers == 1:
                    st.info(f"👤 1명 입력 → 1인용 PDF 생성")
                else:
                    st.info(f"💑 2명 입력 → 궁합/재회용 PDF 생성")
                
                if st.button("🚀 PDF 생성", type="primary", use_container_width=True, key="gen_manual"):
                    status_area = st.empty()
                    current_progress_bar = st.empty()
                    current_detail = st.empty()
                    
                    status_area.markdown(f"### 📝 {display_name} 생성 중...")
                    
                    # 서비스에 현재 유형 임시 설정
                    temp_service = selected_service.copy()
                    temp_service['service_type'] = 'couple' if num_customers == 2 else 'single'
                    
                    # PDF 생성 (2명이면 합친 데이터로)
                    pdf_bytes = generate_pdf_with_progress(
                        combined_data, temp_service, api_key,
                        current_progress_bar, current_detail,
                        custom_name=cover_name
                    )
                    
                    if pdf_bytes:
                        st.session_state.manual_completed = True
                        st.session_state.manual_pdf = pdf_bytes
                        st.toast(f"🔔 {display_name} 완료!")
                    
                    current_progress_bar.progress(1.0, text="100% 완료")
                    time.sleep(0.3)
                    
                    status_area.markdown("### ✅ PDF 생성 완료!")
                    current_progress_bar.empty()
                    current_detail.empty()
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
        else:
            if num_customers == 1:
                st.warning("⚠️ 이름을 입력하세요.")
            else:
                st.warning("⚠️ 두 고객의 이름을 모두 입력하세요.")

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
                    clear_notice_cache()
                    st.rerun()
    st.markdown("---")
    notices = cached_get_notices()
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
                            clear_notice_cache()
                            st.rerun()
                    with c2:
                        if st.button("📌", key=f"pn_{n['id']}"):
                            toggle_pin_notice(n['id'])
                            clear_notice_cache()
                            st.rerun()
                    with c3:
                        if st.button("🗑️", key=f"dl_{n['id']}"):
                            delete_notice(n['id'])
                            clear_notice_cache()
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
