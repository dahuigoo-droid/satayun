"""
PDF용 차트 및 시각화 모듈
- matplotlib: 파이차트, 레이더차트, 라인차트
- ReportLab: 막대그래프, 박스/카드, 별점
"""

import os
import io
import tempfile
import functools
from typing import Dict, List, Tuple, Optional

# matplotlib 설정
import matplotlib
matplotlib.use('Agg')  # GUI 없이 사용
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# 한글 폰트 설정 (한 번만 실행)
_font_initialized = False

def setup_korean_font():
    """한글 폰트 설정 (캐싱됨)"""
    global _font_initialized
    if _font_initialized:
        return
    
    font_paths = [
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            fm.fontManager.addfont(fp)
            plt.rcParams['font.family'] = fm.FontProperties(fname=fp).get_name()
            break
    plt.rcParams['axes.unicode_minus'] = False
    _font_initialized = True

setup_korean_font()

# 색상 팔레트
COLORS = {
    'primary': '#6366F1',      # 인디고
    'secondary': '#EC4899',    # 핑크
    'success': '#10B981',      # 그린
    'warning': '#F59E0B',      # 앰버
    'danger': '#EF4444',       # 레드
    'info': '#3B82F6',         # 블루
    'purple': '#8B5CF6',       # 퍼플
    'teal': '#14B8A6',         # 틸
    'gradient': ['#6366F1', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981'],
}

# 오행 색상
FIVE_ELEMENTS_COLORS = {
    '木': '#22C55E',  # 초록
    '火': '#EF4444',  # 빨강
    '土': '#F59E0B',  # 노랑
    '金': '#F8FAFC',  # 흰색 (테두리 있음)
    '水': '#3B82F6',  # 파랑
}


# ============================================
# matplotlib 차트 생성 함수들
# ============================================

def create_pie_chart(data: Dict[str, float], title: str = "", figsize: Tuple = (4, 4)) -> bytes:
    """파이차트 생성 (오행 밸런스 등)
    
    Args:
        data: {'木': 25, '火': 30, '土': 10, '金': 20, '水': 15}
        title: 차트 제목
    
    Returns:
        PNG 이미지 bytes
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    labels = list(data.keys())
    values = list(data.values())
    colors = [FIVE_ELEMENTS_COLORS.get(k, COLORS['primary']) for k in labels]
    
    # 파이차트
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct='%1.0f%%',
        colors=colors,
        startangle=90,
        explode=[0.02] * len(values),
        shadow=True,
        textprops={'fontsize': 12, 'fontweight': 'bold'}
    )
    
    # 퍼센트 텍스트 스타일
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
    
    if title:
        ax.set_title(title, fontsize=14, fontweight='bold', pad=10)
    
    ax.axis('equal')
    
    # PNG로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def create_radar_chart(data: Dict[str, float], title: str = "", figsize: Tuple = (5, 5)) -> bytes:
    """레이더차트 생성 (영역별 운세 등)
    
    Args:
        data: {'총운': 80, '재물운': 70, '건강운': 95, '애정운': 60, '직장운': 85}
        title: 차트 제목
    
    Returns:
        PNG 이미지 bytes
    """
    fig, ax = plt.subplots(figsize=figsize, subplot_kw=dict(projection='polar'))
    
    labels = list(data.keys())
    values = list(data.values())
    num_vars = len(labels)
    
    # 각도 계산
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    
    # 닫힌 도형을 위해 첫 번째 값을 끝에 추가
    values = values + [values[0]]
    angles = angles + [angles[0]]
    
    # 레이더 차트 그리기
    ax.fill(angles, values, color=COLORS['primary'], alpha=0.25)
    ax.plot(angles, values, color=COLORS['primary'], linewidth=2, marker='o', markersize=6)
    
    # 라벨 설정
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11, fontweight='bold')
    
    # Y축 범위
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=8, color='gray')
    
    # 그리드 스타일
    ax.grid(True, linestyle='--', alpha=0.5)
    
    if title:
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    # PNG로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def create_line_chart(data: Dict[str, float], title: str = "", figsize: Tuple = (6, 3)) -> bytes:
    """라인차트 생성 (월별 운세 흐름)
    
    Args:
        data: {'1월': 70, '2월': 75, '3월': 80, ...}
        title: 차트 제목
    
    Returns:
        PNG 이미지 bytes
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    labels = list(data.keys())
    values = list(data.values())
    x = range(len(labels))
    
    # 그라데이션 효과를 위한 영역 채우기
    ax.fill_between(x, values, alpha=0.3, color=COLORS['primary'])
    
    # 라인 그리기
    ax.plot(x, values, color=COLORS['primary'], linewidth=2.5, marker='o', 
            markersize=6, markerfacecolor='white', markeredgewidth=2)
    
    # 값 표시
    for i, (xi, yi) in enumerate(zip(x, values)):
        ax.annotate(f'{yi}', (xi, yi), textcoords="offset points", 
                   xytext=(0, 8), ha='center', fontsize=8, fontweight='bold')
    
    # 축 설정
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_ylabel('운세 지수', fontsize=10)
    
    # 그리드
    ax.grid(True, axis='y', linestyle='--', alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    if title:
        ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
    
    # PNG로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def create_comparison_bar_chart(data1: Dict[str, float], data2: Dict[str, float],
                                 label1: str, label2: str, title: str = "",
                                 figsize: Tuple = (6, 4)) -> bytes:
    """비교 막대차트 (궁합 - 두 사람 비교)
    
    Args:
        data1: 첫 번째 사람 데이터
        data2: 두 번째 사람 데이터
        label1: 첫 번째 사람 이름
        label2: 두 번째 사람 이름
    
    Returns:
        PNG 이미지 bytes
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    labels = list(data1.keys())
    values1 = list(data1.values())
    values2 = list(data2.values())
    
    x = np.arange(len(labels))
    width = 0.35
    
    # 막대 그리기
    bars1 = ax.barh(x - width/2, values1, width, label=label1, 
                    color=COLORS['primary'], alpha=0.8)
    bars2 = ax.barh(x + width/2, values2, width, label=label2,
                    color=COLORS['secondary'], alpha=0.8)
    
    # 값 표시
    for bar in bars1:
        width_val = bar.get_width()
        ax.text(width_val + 2, bar.get_y() + bar.get_height()/2,
                f'{int(width_val)}', va='center', fontsize=9)
    
    for bar in bars2:
        width_val = bar.get_width()
        ax.text(width_val + 2, bar.get_y() + bar.get_height()/2,
                f'{int(width_val)}', va='center', fontsize=9)
    
    # 축 설정
    ax.set_yticks(x)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlim(0, 110)
    ax.set_xlabel('점수', fontsize=10)
    ax.legend(loc='lower right', fontsize=9)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    if title:
        ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
    
    # PNG로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def create_donut_chart(score: int, max_score: int = 100, 
                       title: str = "", figsize: Tuple = (3, 3)) -> bytes:
    """도넛차트 (총점 표시)
    
    Args:
        score: 점수
        max_score: 최대 점수
        title: 차트 제목
    
    Returns:
        PNG 이미지 bytes
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # 색상 결정
    if score >= 80:
        color = COLORS['success']
    elif score >= 60:
        color = COLORS['info']
    elif score >= 40:
        color = COLORS['warning']
    else:
        color = COLORS['danger']
    
    # 도넛 차트
    sizes = [score, max_score - score]
    colors_list = [color, '#E5E7EB']
    
    wedges, _ = ax.pie(sizes, colors=colors_list, startangle=90,
                       wedgeprops=dict(width=0.3))
    
    # 중앙에 점수 표시
    ax.text(0, 0, f'{score}점', ha='center', va='center',
            fontsize=20, fontweight='bold', color=color)
    
    if title:
        ax.set_title(title, fontsize=12, fontweight='bold', pad=10)
    
    ax.axis('equal')
    
    # PNG로 저장
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ============================================
# ReportLab 직접 그리기 함수들
# ============================================

def draw_horizontal_bar(canvas, x: float, y: float, width: float, height: float,
                        value: float, max_value: float = 100,
                        label: str = "", show_value: bool = True,
                        bar_color: str = None):
    """수평 막대그래프 그리기 (ReportLab canvas에 직접)
    
    Args:
        canvas: ReportLab canvas 객체
        x, y: 시작 좌표
        width: 전체 너비
        height: 막대 높이
        value: 현재 값
        max_value: 최대 값
        label: 라벨
        show_value: 값 표시 여부
        bar_color: 막대 색상 (hex)
    """
    from reportlab.lib.colors import HexColor, lightgrey
    
    # 기본 색상
    if bar_color is None:
        if value >= 80:
            bar_color = COLORS['success']
        elif value >= 60:
            bar_color = COLORS['info']
        elif value >= 40:
            bar_color = COLORS['warning']
        else:
            bar_color = COLORS['danger']
    
    # 배경 막대 (회색)
    canvas.setFillColor(lightgrey)
    canvas.rect(x, y, width, height, fill=1, stroke=0)
    
    # 값 막대
    bar_width = (value / max_value) * width
    canvas.setFillColor(HexColor(bar_color))
    canvas.rect(x, y, bar_width, height, fill=1, stroke=0)
    
    # 라벨 (왼쪽)
    if label:
        canvas.setFillColor(HexColor('#374151'))
        canvas.setFont('KoreanFont', 10)
        canvas.drawRightString(x - 5, y + height/2 - 4, label)
    
    # 값 (오른쪽)
    if show_value:
        canvas.setFillColor(HexColor('#374151'))
        canvas.setFont('KoreanFont', 9)
        canvas.drawString(x + width + 5, y + height/2 - 4, f'{int(value)}%')


def draw_star_rating(canvas, x: float, y: float, score: float, 
                     max_score: float = 100, num_stars: int = 5,
                     star_size: float = 12):
    """별점 그리기
    
    Args:
        canvas: ReportLab canvas 객체
        x, y: 시작 좌표
        score: 점수 (0-100)
        max_score: 최대 점수
        num_stars: 별 개수
        star_size: 별 크기
    """
    filled_stars = int((score / max_score) * num_stars + 0.5)
    
    canvas.setFont('Helvetica', star_size)
    
    for i in range(num_stars):
        if i < filled_stars:
            canvas.setFillColor(HexColor('#F59E0B'))  # 노란색
            canvas.drawString(x + i * (star_size + 2), y, '★')
        else:
            canvas.setFillColor(HexColor('#D1D5DB'))  # 회색
            canvas.drawString(x + i * (star_size + 2), y, '☆')


def draw_score_card(canvas, x: float, y: float, width: float, height: float,
                    title: str, score: int, description: str = "",
                    icon: str = ""):
    """점수 카드 그리기
    
    Args:
        canvas: ReportLab canvas 객체
        x, y: 시작 좌표 (왼쪽 하단)
        width, height: 카드 크기
        title: 카드 제목
        score: 점수
        description: 설명
        icon: 아이콘 (이모지)
    """
    from reportlab.lib.colors import HexColor, white
    
    # 색상 결정
    if score >= 80:
        bg_color = COLORS['success']
    elif score >= 60:
        bg_color = COLORS['info']
    elif score >= 40:
        bg_color = COLORS['warning']
    else:
        bg_color = COLORS['danger']
    
    # 카드 배경 (둥근 모서리)
    canvas.setFillColor(HexColor(bg_color))
    canvas.roundRect(x, y, width, height, 8, fill=1, stroke=0)
    
    # 텍스트
    canvas.setFillColor(white)
    
    # 아이콘 + 제목
    canvas.setFont('KoreanFont', 11)
    title_text = f"{icon} {title}" if icon else title
    canvas.drawCentredString(x + width/2, y + height - 20, title_text)
    
    # 점수
    canvas.setFont('KoreanFont', 22)
    canvas.drawCentredString(x + width/2, y + height/2 - 5, f'{score}점')
    
    # 설명
    if description:
        canvas.setFont('KoreanFont', 9)
        canvas.drawCentredString(x + width/2, y + 12, description)


def draw_summary_box(canvas, x: float, y: float, width: float, height: float,
                     title: str, items: List[Tuple[str, int]]):
    """요약 박스 그리기 (여러 항목의 막대그래프)
    
    Args:
        canvas: ReportLab canvas 객체
        x, y: 시작 좌표
        width, height: 박스 크기
        title: 박스 제목
        items: [(라벨, 값), ...] 리스트
    """
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.units import mm
    
    # 박스 배경
    canvas.setFillColor(HexColor('#F9FAFB'))
    canvas.setStrokeColor(HexColor('#E5E7EB'))
    canvas.roundRect(x, y, width, height, 6, fill=1, stroke=1)
    
    # 제목
    canvas.setFillColor(HexColor('#1F2937'))
    canvas.setFont('KoreanFont', 12)
    canvas.drawString(x + 10, y + height - 20, title)
    
    # 구분선
    canvas.setStrokeColor(HexColor('#E5E7EB'))
    canvas.line(x + 10, y + height - 28, x + width - 10, y + height - 28)
    
    # 막대그래프들
    bar_height = 14
    bar_width = width - 100
    start_y = y + height - 50
    
    for i, (label, value) in enumerate(items):
        bar_y = start_y - i * 25
        draw_horizontal_bar(canvas, x + 70, bar_y, bar_width, bar_height,
                           value, 100, label, True)


# ============================================
# 차트 이미지 저장 유틸리티
# ============================================

def save_chart_to_temp(chart_bytes: bytes, prefix: str = "chart") -> str:
    """차트 이미지를 임시 파일로 저장
    
    Args:
        chart_bytes: PNG 이미지 bytes
        prefix: 파일명 접두사
    
    Returns:
        임시 파일 경로
    """
    fd, path = tempfile.mkstemp(suffix='.png', prefix=f'{prefix}_')
    with os.fdopen(fd, 'wb') as f:
        f.write(chart_bytes)
    return path


def cleanup_temp_charts(paths: List[str]):
    """임시 차트 파일 정리"""
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass


# ============================================
# 테스트용 샘플 데이터 생성
# ============================================

def generate_sample_scores() -> Dict:
    """테스트용 샘플 점수 생성"""
    import random
    
    return {
        'total_score': random.randint(60, 95),
        'category_scores': {
            '총운': random.randint(50, 100),
            '재물운': random.randint(50, 100),
            '건강운': random.randint(50, 100),
            '애정운': random.randint(50, 100),
            '직장운': random.randint(50, 100),
        },
        'monthly_scores': {
            '1월': random.randint(50, 100),
            '2월': random.randint(50, 100),
            '3월': random.randint(50, 100),
            '4월': random.randint(50, 100),
            '5월': random.randint(50, 100),
            '6월': random.randint(50, 100),
            '7월': random.randint(50, 100),
            '8월': random.randint(50, 100),
            '9월': random.randint(50, 100),
            '10월': random.randint(50, 100),
            '11월': random.randint(50, 100),
            '12월': random.randint(50, 100),
        },
        'five_elements': {
            '木': random.randint(10, 35),
            '火': random.randint(10, 35),
            '土': random.randint(10, 35),
            '金': random.randint(10, 35),
            '水': random.randint(10, 35),
        },
    }


def generate_couple_sample_scores() -> Dict:
    """궁합용 샘플 점수 생성"""
    import random
    
    return {
        'total_score': random.randint(60, 95),
        'compatibility_scores': {
            '성격궁합': random.randint(50, 100),
            '감정궁합': random.randint(50, 100),
            '금전궁합': random.randint(50, 100),
            '육체궁합': random.randint(50, 100),
            '미래궁합': random.randint(50, 100),
        },
        'person1_elements': {
            '木': random.randint(10, 35),
            '火': random.randint(10, 35),
            '土': random.randint(10, 35),
            '金': random.randint(10, 35),
            '水': random.randint(10, 35),
        },
        'person2_elements': {
            '木': random.randint(10, 35),
            '火': random.randint(10, 35),
            '土': random.randint(10, 35),
            '金': random.randint(10, 35),
            '水': random.randint(10, 35),
        },
    }


if __name__ == "__main__":
    # 테스트
    print("차트 생성 테스트...")
    
    # 파이차트 테스트
    pie_data = {'木': 25, '火': 30, '土': 10, '金': 20, '水': 15}
    pie_bytes = create_pie_chart(pie_data, "오행 밸런스")
    print(f"파이차트: {len(pie_bytes)} bytes")
    
    # 레이더차트 테스트
    radar_data = {'총운': 80, '재물운': 70, '건강운': 95, '애정운': 60, '직장운': 85}
    radar_bytes = create_radar_chart(radar_data, "영역별 운세")
    print(f"레이더차트: {len(radar_bytes)} bytes")
    
    # 라인차트 테스트
    line_data = {f'{i}월': 50 + i*3 for i in range(1, 13)}
    line_bytes = create_line_chart(line_data, "월별 운세 흐름")
    print(f"라인차트: {len(line_bytes)} bytes")
    
    # 도넛차트 테스트
    donut_bytes = create_donut_chart(78, 100, "총점")
    print(f"도넛차트: {len(donut_bytes)} bytes")
    
    print("✅ 모든 차트 생성 완료!")
