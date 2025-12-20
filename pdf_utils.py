# -*- coding: utf-8 -*-
"""
🔮 PDF 생성 유틸리티
"""

import streamlit as st
import os
import hashlib
import random
import time
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import (
    cached_get_chapters, cached_get_guidelines, cached_get_templates,
    get_registered_font, calculate_chars_per_page, UPLOAD_DIR, OUTPUT_DIR
)
from services import get_system_config, ConfigKeys

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


def generate_order_hash(customer_data: dict, service_id: int) -> str:
    """주문 고유 해시 생성 (멱등성 체크용)"""
    hash_input = f"{service_id}:{str(sorted(customer_data.items()))}"
    return hashlib.md5(hash_input.encode()).hexdigest()


def is_already_generated(order_hash: str) -> bool:
    """이미 생성된 주문인지 확인"""
    return order_hash in st.session_state.get('pdf_hashes', {})


def mark_as_generated(order_hash: str, pdf_bytes: bytes):
    """생성 완료 표시"""
    if 'pdf_hashes' not in st.session_state:
        st.session_state.pdf_hashes = {}
    st.session_state.pdf_hashes[order_hash] = pdf_bytes


def generate_chapters_parallel(api_key: str, chapters: list, guideline_text: str, 
                                customer_data: dict, chars_per_chapter: int,
                                progress_callback=None) -> list:
    """GPT 챕터 내용 병렬 생성 (최대 3배 빠름)"""
    all_chapter_titles = [ch['title'] for ch in chapters]
    results = [None] * len(chapters)
    
    def generate_single(args):
        idx, ch = args
        content = generate_content_with_gpt(
            api_key, ch['title'], guideline_text, customer_data,
            chars_per_chapter, all_chapter_titles, idx
        )
        return idx, {"title": ch['title'], "content": content}
    
    # 병렬 실행 (최대 4개 동시)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(generate_single, (i, ch)): i 
                   for i, ch in enumerate(chapters)}
        
        completed = 0
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result
            completed += 1
            
            if progress_callback:
                progress_callback(completed, len(chapters))
    
    return results


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
        
        # 캐싱된 폰트 사용 (성능 최적화)
        font_name = CACHED_FONT_NAME
        
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
    
    # ========== GPT 병렬 호출 (속도 3배 향상) ==========
    detail_text.caption(f"📝 {total_chapters}개 챕터 동시 작성 중... (병렬 처리)")
    
    def update_progress(completed, total):
        """병렬 처리 진행률 콜백"""
        progress = 0.1 + (completed / total) * 0.85
        progress_bar.progress(progress, text=f"{int(progress * 100)}%")
        detail_text.caption(f"📝 {completed}/{total} 챕터 완료...")
    
    # 병렬로 모든 챕터 동시 생성
    chapters_content = generate_chapters_parallel(
        api_key, chapters, guideline_text, customer_data,
        chars_per_chapter, progress_callback=update_progress
    )
    
    detail_text.caption("📄 PDF 생성 중...")
    
    # 표지 이름 처리
    if custom_name:
        cover_display_name = custom_name
    else:
        cover_display_name = f"{customer_name}님"
    
    return create_pdf_document(cover_display_name, chapters_content, templates, font_settings, 
                               scores=scores, service_type=service_type)
