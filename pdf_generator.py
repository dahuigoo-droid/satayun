# -*- coding: utf-8 -*-
"""
📄 PDF 생성 모듈
- GPT 호출 (목차별 분할)
- PDF 생성 (표지→소개→본문→안내)
"""

import os
import io
from datetime import datetime
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
from reportlab.pdfgen import canvas

# ============================================
# 폰트 등록
# ============================================

def register_fonts():
    """한글 폰트 등록"""
    font_paths = [
        ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf', 'NanumGothic'),
        ('/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf', 'NanumGothicBold'),
        ('/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf', 'NanumMyeongjo'),
    ]
    
    registered_font = 'Helvetica'  # 기본값
    
    for path, name in font_paths:
        try:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont(name, path))
                registered_font = name
        except Exception as e:
            print(f"폰트 등록 실패 ({name}): {e}")
    
    return registered_font

# ============================================
# GPT 콘텐츠 생성
# ============================================

def generate_chapter_content(
    api_key: str,
    customer_info: dict,
    chapter_title: str,
    guideline: str,
    service_type: str,
    model: str = "gpt-4o-mini"
) -> str:
    """
    단일 챕터(목차) 콘텐츠 생성
    """
    try:
        client = OpenAI(api_key=api_key)
        
        # 고객 정보 포맷팅
        customer_str = "\n".join([f"- {k}: {v}" for k, v in customer_info.items() if v])
        
        prompt = f"""
[서비스 유형]
{service_type}

[고객 정보]
{customer_str}

[작성 지침]
{guideline}

[현재 작성할 챕터]
{chapter_title}

위 챕터를 상세하게 작성해주세요.
- 전문적이면서도 이해하기 쉽게
- 구체적인 조언과 예시 포함
- 따뜻하고 희망적인 톤 유지
- 최소 500자 이상 작성
"""
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": f"당신은 전문적이고 따뜻한 {service_type} 전문가입니다."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"[오류 발생: {str(e)}]"


def generate_full_content(
    api_key: str,
    customer_info: dict,
    chapters: list,
    guideline: str,
    service_type: str,
    model: str = "gpt-4o-mini",
    progress_callback=None
) -> list:
    """
    전체 콘텐츠 생성 (목차별 분할 요청)
    
    Returns:
        list: [{"title": "챕터제목", "content": "내용"}, ...]
    """
    full_content = []
    total = len(chapters)
    
    for i, chapter in enumerate(chapters):
        if progress_callback:
            progress_callback((i + 1) / total, f"'{chapter}' 작성 중... ({i+1}/{total})")
        
        content = generate_chapter_content(
            api_key=api_key,
            customer_info=customer_info,
            chapter_title=chapter,
            guideline=guideline,
            service_type=service_type,
            model=model
        )
        
        full_content.append({
            "title": chapter,
            "content": content
        })
    
    return full_content


# ============================================
# PDF 생성
# ============================================

class PDFGenerator:
    """PDF 생성 클래스"""
    
    def __init__(
        self,
        font_name: str = "NanumGothic",
        font_size: int = 12,
        line_height: int = 20,
        letter_spacing: int = 0
    ):
        self.font_name = register_fonts() if font_name == "나눔고딕" else register_fonts()
        self.font_size = font_size
        self.line_height = line_height
        self.letter_spacing = letter_spacing
        self.width, self.height = A4
        
    def create_pdf(
        self,
        chapters_content: list,
        customer_name: str,
        service_type: str,
        cover_image: str = None,
        intro_image: str = None,
        background_image: str = None,
        info_image: str = None,
        customer_name2: str = None
    ) -> bytes:
        """
        PDF 생성
        
        Args:
            chapters_content: [{"title": "제목", "content": "내용"}, ...]
            customer_name: 고객 이름
            service_type: 서비스 유형
            cover_image: 표지 이미지 경로
            intro_image: 소개 페이지 이미지 경로
            background_image: 본문 배경 이미지 경로
            info_image: 안내 페이지 이미지 경로
            customer_name2: 두 번째 이름 (연애/궁합용)
        
        Returns:
            bytes: PDF 파일 바이트
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # 1. 표지 페이지
        self._draw_cover_page(c, cover_image, customer_name, service_type, customer_name2)
        
        # 2. 소개 페이지
        if intro_image:
            self._draw_image_page(c, intro_image)
        
        # 3. 목차 페이지
        self._draw_toc_page(c, chapters_content)
        
        # 4. 본문 페이지들
        for chapter in chapters_content:
            self._draw_content_pages(c, chapter, background_image)
        
        # 5. 안내 페이지
        if info_image:
            self._draw_image_page(c, info_image)
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    def _draw_cover_page(self, c, cover_image, customer_name, service_type, customer_name2=None):
        """표지 페이지 그리기"""
        # 배경 이미지
        if cover_image and os.path.exists(cover_image):
            try:
                c.drawImage(cover_image, 0, 0, width=self.width, height=self.height, preserveAspectRatio=False, mask='auto')
            except:
                pass
        
        # 고객 이름
        c.setFont(self.font_name, 28)
        
        if customer_name2:
            name_text = f"{customer_name}  ♥  {customer_name2}"
        else:
            name_text = f"{customer_name} 님"
        
        text_width = c.stringWidth(name_text, self.font_name, 28)
        c.drawString((self.width - text_width) / 2, self.height * 0.25, name_text)
        
        # 서비스 유형
        c.setFont(self.font_name, 18)
        service_text = f"{service_type} 감정서"
        text_width = c.stringWidth(service_text, self.font_name, 18)
        c.drawString((self.width - text_width) / 2, self.height * 0.20, service_text)
        
        # 날짜
        c.setFont(self.font_name, 12)
        date_text = datetime.now().strftime("%Y년 %m월 %d일")
        text_width = c.stringWidth(date_text, self.font_name, 12)
        c.drawString((self.width - text_width) / 2, self.height * 0.15, date_text)
        
        c.showPage()
    
    def _draw_image_page(self, c, image_path):
        """이미지 전체 페이지 그리기 (소개, 안내)"""
        if image_path and os.path.exists(image_path):
            try:
                c.drawImage(image_path, 0, 0, width=self.width, height=self.height, preserveAspectRatio=False, mask='auto')
            except:
                pass
        c.showPage()
    
    def _draw_toc_page(self, c, chapters_content):
        """목차 페이지 그리기"""
        c.setFont(self.font_name, 24)
        c.drawString(70, self.height - 80, "목 차")
        
        c.setFont(self.font_name, 14)
        y_position = self.height - 140
        
        for i, chapter in enumerate(chapters_content):
            title = chapter['title']
            c.drawString(80, y_position, f"{i+1}. {title}")
            y_position -= 30
            
            if y_position < 100:
                c.showPage()
                y_position = self.height - 80
        
        c.showPage()
    
    def _draw_content_pages(self, c, chapter, background_image):
        """본문 페이지들 그리기"""
        title = chapter['title']
        content = chapter['content']
        
        # 여백 설정
        left_margin = 60
        right_margin = 60
        top_margin = 80
        bottom_margin = 80
        
        usable_width = self.width - left_margin - right_margin
        usable_height = self.height - top_margin - bottom_margin
        
        # 배경 이미지
        if background_image and os.path.exists(background_image):
            try:
                c.drawImage(background_image, 0, 0, width=self.width, height=self.height, preserveAspectRatio=False, mask='auto')
            except:
                pass
        
        # 챕터 제목
        c.setFont(self.font_name, 18)
        c.drawString(left_margin, self.height - top_margin, f"■ {title}")
        
        # 본문 내용
        c.setFont(self.font_name, self.font_size)
        
        y_position = self.height - top_margin - 40
        
        # 줄 단위로 분리
        lines = content.split('\n')
        
        for line in lines:
            # 긴 줄 자동 줄바꿈
            words = line
            while words:
                # 한 줄에 들어갈 수 있는 글자 수 계산
                chars_per_line = int(usable_width / (self.font_size * 0.6))
                
                if len(words) <= chars_per_line:
                    c.drawString(left_margin, y_position, words)
                    words = ""
                else:
                    c.drawString(left_margin, y_position, words[:chars_per_line])
                    words = words[chars_per_line:]
                
                y_position -= self.line_height
                
                # 페이지 넘김
                if y_position < bottom_margin:
                    c.showPage()
                    
                    # 새 페이지 배경
                    if background_image and os.path.exists(background_image):
                        try:
                            c.drawImage(background_image, 0, 0, width=self.width, height=self.height, preserveAspectRatio=False, mask='auto')
                        except:
                            pass
                    
                    c.setFont(self.font_name, self.font_size)
                    y_position = self.height - top_margin
        
        c.showPage()


# ============================================
# 합본 PDF 생성 (여러 서비스)
# ============================================

def generate_combined_pdf(
    api_key: str,
    customer_info: dict,
    services_data: list,
    font_settings: dict,
    progress_callback=None
) -> bytes:
    """
    여러 서비스 합본 PDF 생성
    
    Args:
        api_key: OpenAI API 키
        customer_info: 고객 정보 딕셔너리
        services_data: [
            {
                "service_name": "사주",
                "chapters": ["총운", "성격분석", ...],
                "guideline": "지침 내용",
                "cover_image": "경로",
                "intro_image": "경로",
                "background_image": "경로",
                "info_image": "경로"
            },
            ...
        ]
        font_settings: {"font": "나눔고딕", "size": 14, "line_height": 24, "letter_spacing": 0}
        progress_callback: 진행 상황 콜백 함수
    
    Returns:
        bytes: 합본 PDF 바이트
    """
    all_chapters_content = []
    
    # 총 챕터 수 계산
    total_chapters = sum(len(s['chapters']) for s in services_data)
    current_chapter = 0
    
    # 각 서비스별 콘텐츠 생성
    for service in services_data:
        service_name = service['service_name']
        chapters = service['chapters']
        guideline = service.get('guideline', '')
        
        for chapter in chapters:
            current_chapter += 1
            
            if progress_callback:
                progress_callback(
                    current_chapter / total_chapters,
                    f"[{service_name}] '{chapter}' 작성 중... ({current_chapter}/{total_chapters})"
                )
            
            content = generate_chapter_content(
                api_key=api_key,
                customer_info=customer_info,
                chapter_title=f"{service_name} - {chapter}",
                guideline=guideline,
                service_type=service_name
            )
            
            all_chapters_content.append({
                "title": f"{service_name} - {chapter}",
                "content": content
            })
    
    # PDF 생성
    pdf_gen = PDFGenerator(
        font_name=font_settings.get('font', '나눔고딕'),
        font_size=font_settings.get('size', 14),
        line_height=font_settings.get('line_height', 24),
        letter_spacing=font_settings.get('letter_spacing', 0)
    )
    
    # 첫 번째 서비스의 이미지 사용 (합본일 경우)
    first_service = services_data[0] if services_data else {}
    
    customer_name = customer_info.get('이름', customer_info.get('name', '고객'))
    customer_name2 = customer_info.get('이름2', customer_info.get('name2', None))
    
    # 서비스 유형 문자열 (합본일 경우 여러 개)
    service_types = " + ".join([s['service_name'] for s in services_data])
    
    pdf_bytes = pdf_gen.create_pdf(
        chapters_content=all_chapters_content,
        customer_name=customer_name,
        service_type=service_types,
        cover_image=first_service.get('cover_image'),
        intro_image=first_service.get('intro_image'),
        background_image=first_service.get('background_image'),
        info_image=first_service.get('info_image'),
        customer_name2=customer_name2
    )
    
    return pdf_bytes
