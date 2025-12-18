# -*- coding: utf-8 -*-
"""
🗄️ 데이터베이스 모델 및 연결
Streamlit Cloud 호환 버전
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

# 방법 1: Streamlit secrets (Streamlit Cloud)
try:
    import streamlit as st
    DATABASE_URL = st.secrets.get("DATABASE_URL", None)
except:
    pass

# 방법 2: 환경변수 (로컬/Railway)
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
    LEVEL1 = 1  # 기본 (목차/지침/속지)
    LEVEL2 = 2  # + 공지작성
    LEVEL3 = 3  # 관리자

class UserStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SUSPENDED = "suspended"
    BANNED = "banned"

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
    
    role = Column(Integer, default=UserRole.LEVEL1)
    status = Column(String(20), default=UserStatus.PENDING)
    
    # API 설정
    api_key = Column(Text, nullable=True)
    use_admin_api = Column(Boolean, default=True)
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


class Service(Base):
    """서비스 테이블 (사주, 타로, 연애 등)"""
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
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
    
    service = relationship("Service", back_populates="guidelines")


class Template(Base):
    """속지/템플릿 테이블"""
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    template_type = Column(String(50), nullable=False)  # cover, background, intro, info
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
