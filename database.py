# -*- coding: utf-8 -*-
"""
🗄️ 데이터베이스 모델 및 연결
회원별 권한 모드 추가 버전
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum

# ============================================
# Streamlit Cloud 환경변수 읽기
# ============================================

DATABASE_URL = None

try:
    import streamlit as st
    DATABASE_URL = st.secrets.get("DATABASE_URL", None)
except:
    pass

if not DATABASE_URL:
    DATABASE_URL = os.environ.get("DATABASE_URL")

# ============================================
# 데이터베이스 엔진 생성
# ============================================

engine = None
SessionLocal = None
Base = declarative_base()

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    except Exception as e:
        print(f"DB 연결 오류: {e}")

# ============================================
# Enum 정의
# ============================================

class UserRole(enum.IntEnum):
    NORMAL = 1   # 일반 사용자
    ADMIN = 2    # 관리자

class PermissionType(str, enum.Enum):
    EXECUTE = "execute"       # 수행 - 관리자가 만든 것만 사용
    INDIVIDUAL = "individual" # 개별 - 스스로 작성/수정 가능

class UserStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SUSPENDED = "suspended"

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
    
    # 등급: 1=일반, 2=관리자
    role = Column(Integer, default=UserRole.NORMAL)
    status = Column(String(20), default=UserStatus.PENDING)
    
    # 권한 타입: execute(수행), individual(개별)
    permission_type = Column(String(20), default=PermissionType.EXECUTE)
    
    # 회원별 모드 설정 (관리자가 각 회원에게 개별 설정)
    api_mode = Column(String(20), default="unified")      # unified/separated
    email_mode = Column(String(20), default="unified")    # unified/separated
    service_mode = Column(String(20), default="unified")  # unified/separated
    design_mode = Column(String(20), default="unified")   # unified/separated
    
    # API 설정
    api_key = Column(Text, nullable=True)
    api_usage_count = Column(Integer, default=0)
    api_usage_limit = Column(Integer, default=100)
    
    # 이메일 설정
    gmail_address = Column(String(255), nullable=True)
    gmail_app_password = Column(String(255), nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # 관계
    notices = relationship("Notice", back_populates="author")
    services = relationship("Service", back_populates="owner")


class Service(Base):
    """서비스(상품) 테이블 - 목차+지침+디자인 통합"""
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL이면 관리자 공용
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # 1차 분류 (사주, 타로, 연애 - 콤마로 구분)
    categories = Column(String(100), nullable=True)
    
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    owner = relationship("User", back_populates="services")
    chapters = relationship("Chapter", back_populates="service", cascade="all, delete-orphan")
    guidelines = relationship("Guideline", back_populates="service", cascade="all, delete-orphan")
    templates = relationship("Template", back_populates="service", cascade="all, delete-orphan")


class Chapter(Base):
    """목차 테이블"""
    __tablename__ = "chapters"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    service = relationship("Service", back_populates="chapters")


class Guideline(Base):
    """지침 테이블"""
    __tablename__ = "guidelines"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    service = relationship("Service", back_populates="guidelines")


class Template(Base):
    """속지/디자인 테이블"""
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    template_type = Column(String(50), nullable=False)  # cover, background, info
    name = Column(String(200), nullable=False)
    image_path = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    service = relationship("Service", back_populates="templates")


class SystemConfig(Base):
    """시스템 설정 테이블"""
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notice(Base):
    """공지사항 테이블"""
    __tablename__ = "notices"
    
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    image_path = Column(Text, nullable=True)
    is_pinned = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    author = relationship("User", back_populates="notices")


# ============================================
# 데이터베이스 초기화
# ============================================

def init_db():
    """데이터베이스 테이블 생성"""
    if engine:
        Base.metadata.create_all(bind=engine)
        print("✅ 데이터베이스 테이블 생성 완료")
    else:
        print("⚠️ DATABASE_URL이 설정되지 않았습니다.")


def get_db():
    """DB 세션 가져오기"""
    if SessionLocal:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        yield None
