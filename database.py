# -*- coding: utf-8 -*-
"""
🗄️ 데이터베이스 설정 및 모델 정의
PostgreSQL (Railway)
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum

# ============================================
# 데이터베이스 연결
# ============================================

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway PostgreSQL URL 형식 변환 (postgres:// → postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL) if DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None
Base = declarative_base()

# ============================================
# Enum 정의
# ============================================

class UserRole(enum.IntEnum):
    """사용자 등급"""
    LEVEL_1 = 1  # 목차/지침/속지 설정
    LEVEL_2 = 2  # 1단계 + 공지사항 작성
    LEVEL_3 = 3  # 관리자 (전체 권한)

class UserStatus(enum.Enum):
    """사용자 상태"""
    PENDING = "pending"      # 승인 대기
    APPROVED = "approved"    # 승인됨
    SUSPENDED = "suspended"  # 사용 중지
    BANNED = "banned"        # 강퇴

class TemplateType(enum.Enum):
    """속지 템플릿 유형"""
    COVER = "cover"          # 표지
    BACKGROUND = "background" # 속지 (본문 배경)
    INTRO = "intro"          # 소개
    INFO = "info"            # 안내

# ============================================
# 모델 정의
# ============================================

class User(Base):
    """사용자 테이블"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    
    # 권한 및 상태
    role = Column(Integer, default=UserRole.LEVEL_1)
    status = Column(String(20), default=UserStatus.PENDING.value)
    
    # API 설정
    api_key = Column(String(255), nullable=True)  # 개인 API 키
    use_admin_api = Column(Boolean, default=True)  # 관리자 API 사용 여부
    api_usage_count = Column(Integer, default=0)   # API 사용량 (관리자 API 사용 시)
    api_usage_limit = Column(Integer, default=100) # API 사용 한도
    
    # 이메일 설정
    gmail_address = Column(String(255), nullable=True)
    gmail_app_password = Column(String(255), nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    customers = relationship("Customer", back_populates="user")
    notices = relationship("Notice", back_populates="author")


class Service(Base):
    """서비스 테이블 (사주, 타로, 연애 등)"""
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    chapters = relationship("Chapter", back_populates="service")
    guidelines = relationship("Guideline", back_populates="service")
    templates = relationship("Template", back_populates="service")


class Chapter(Base):
    """목차 테이블"""
    __tablename__ = "chapters"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    service = relationship("Service", back_populates="chapters")


class Guideline(Base):
    """지침 테이블"""
    __tablename__ = "guidelines"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    service = relationship("Service", back_populates="guidelines")


class Template(Base):
    """속지 템플릿 테이블"""
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    template_type = Column(String(20), nullable=False)  # cover, background, intro, info
    name = Column(String(100), nullable=False)
    image_path = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    service = relationship("Service", back_populates="templates")


class Customer(Base):
    """고객 테이블"""
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String(100), nullable=False)
    name2 = Column(String(100), nullable=True)  # 궁합용 두번째 이름
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # 사주 정보
    birth_date = Column(String(20), nullable=True)
    birth_time = Column(String(10), nullable=True)
    year_pillar = Column(String(10), nullable=True)   # 년주
    month_pillar = Column(String(10), nullable=True)  # 월주
    day_pillar = Column(String(10), nullable=True)    # 일주
    hour_pillar = Column(String(10), nullable=True)   # 시주
    
    # 상태
    status = Column(String(20), default="pending")  # pending, completed, sent
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    user = relationship("User", back_populates="customers")


class Notice(Base):
    """공지사항 테이블"""
    __tablename__ = "notices"
    
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    image_path = Column(String(500), nullable=True)
    is_pinned = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    author = relationship("User", back_populates="notices")


class SystemConfig(Base):
    """시스템 설정 테이블"""
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================
# 데이터베이스 초기화 함수
# ============================================

def init_db():
    """데이터베이스 테이블 생성"""
    if engine:
        Base.metadata.create_all(bind=engine)
        print("✅ 데이터베이스 테이블 생성 완료!")
        
        # 기본 서비스 추가
        init_default_services()
    else:
        print("❌ DATABASE_URL이 설정되지 않았습니다.")


def init_default_services():
    """기본 서비스 데이터 추가"""
    if not SessionLocal:
        return
    
    db = SessionLocal()
    try:
        # 이미 서비스가 있는지 확인
        existing = db.query(Service).first()
        if existing:
            return
        
        # 기본 서비스 추가
        default_services = [
            Service(name="사주", description="사주팔자 풀이 서비스", order=1),
            Service(name="타로", description="타로 카드 해석 서비스", order=2),
            Service(name="연애", description="연애/궁합 풀이 서비스", order=3),
        ]
        
        for service in default_services:
            db.add(service)
        
        db.commit()
        print("✅ 기본 서비스 데이터 추가 완료!")
    except Exception as e:
        print(f"❌ 기본 데이터 추가 오류: {e}")
        db.rollback()
    finally:
        db.close()


def get_db():
    """DB 세션 가져오기"""
    if not SessionLocal:
        return None
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        return None
