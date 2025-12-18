# -*- coding: utf-8 -*-
"""
🔐 인증 및 사용자 관리
회원 등급 1/2/3단계 버전
"""

import bcrypt
from datetime import datetime
from database import SessionLocal, User

# ============================================
# 비밀번호 처리
# ============================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# ============================================
# 회원가입 / 로그인
# ============================================

def register_user(email: str, password: str, name: str) -> dict:
    """회원가입"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if not email or not password or not name:
        return {"success": False, "error": "모든 필드를 입력해주세요."}
    
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return {"success": False, "error": "이미 등록된 이메일입니다."}
        
        new_user = User(
            email=email.strip().lower(),
            password_hash=hash_password(password),
            name=name.strip(),
            is_admin=False,
            member_level=1,  # 기본: 관리자 상품만 사용
            status="pending"
        )
        
        db.add(new_user)
        db.commit()
        
        return {"success": True, "message": "회원가입 완료! 관리자 승인 후 이용 가능합니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"회원가입 실패: {str(e)}"}
    finally:
        db.close()


def login_user(email: str, password: str) -> dict:
    """로그인"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        
        if not user:
            return {"success": False, "error": "존재하지 않는 이메일입니다."}
        
        if not verify_password(password, user.password_hash):
            return {"success": False, "error": "비밀번호가 일치하지 않습니다."}
        
        if user.status == "pending":
            return {"success": False, "error": "관리자 승인 대기 중입니다."}
        
        if user.status == "suspended":
            return {"success": False, "error": "정지된 계정입니다."}
        
        user.last_login = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_admin": user.is_admin,
                "member_level": user.member_level,
                "status": user.status,
                "api_mode": user.api_mode,
                "email_mode": user.email_mode,
                "api_key": user.api_key,
                "gmail_address": user.gmail_address,
                "gmail_app_password": user.gmail_app_password,
            }
        }
    
    except Exception as e:
        return {"success": False, "error": f"로그인 실패: {str(e)}"}
    finally:
        db.close()


def create_first_admin(email: str, password: str, name: str) -> dict:
    """최초 관리자 생성"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.is_admin == True).first()
        if admin_exists:
            return {"success": False, "error": "이미 관리자가 존재합니다."}
        
        admin = User(
            email=email.strip().lower(),
            password_hash=hash_password(password),
            name=name.strip(),
            is_admin=True,
            member_level=3,  # 관리자는 둘 다 사용
            status="approved"
        )
        
        db.add(admin)
        db.commit()
        
        return {"success": True, "message": "관리자 계정이 생성되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"관리자 생성 실패: {str(e)}"}
    finally:
        db.close()


def check_admin_exists() -> bool:
    """관리자 존재 여부 확인"""
    if not SessionLocal:
        return False
    
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.is_admin == True).first()
        return admin is not None
    except:
        return False
    finally:
        db.close()

# ============================================
# 사용자 조회
# ============================================

def get_all_users() -> list:
    """모든 사용자 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.is_admin.desc(), User.created_at.desc()).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "is_admin": u.is_admin,
                "member_level": u.member_level,
                "status": u.status,
                "api_mode": u.api_mode,
                "email_mode": u.email_mode,
                "created_at": u.created_at.strftime("%Y-%m-%d") if u.created_at else "",
            }
            for u in users
        ]
    except Exception as e:
        print(f"사용자 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_pending_users() -> list:
    """승인 대기 사용자 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.status == "pending").all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "created_at": u.created_at.strftime("%Y-%m-%d") if u.created_at else "",
            }
            for u in users
        ]
    except:
        return []
    finally:
        db.close()

# ============================================
# 사용자 관리
# ============================================

def approve_user(user_id: int) -> dict:
    """사용자 승인"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.status = "approved"
        db.commit()
        return {"success": True, "message": f"{user.name}님이 승인되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def suspend_user(user_id: int) -> dict:
    """사용자 정지"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.status = "suspended"
        db.commit()
        return {"success": True, "message": f"{user.name}님이 정지되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def activate_user(user_id: int) -> dict:
    """사용자 활성화"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.status = "approved"
        db.commit()
        return {"success": True, "message": f"{user.name}님이 활성화되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def update_user_settings(user_id: int, member_level: int = None, 
                         api_mode: str = None, email_mode: str = None) -> dict:
    """회원 설정 변경 (관리자용)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        if member_level is not None:
            user.member_level = member_level
        if api_mode is not None:
            user.api_mode = api_mode
        if email_mode is not None:
            user.email_mode = email_mode
        
        db.commit()
        return {"success": True, "message": "설정이 변경되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def update_user_profile(user_id: int, name: str = None, api_key: str = None,
                       gmail_address: str = None, gmail_app_password: str = None) -> dict:
    """사용자 프로필 업데이트"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        if name is not None:
            user.name = name.strip()
        if api_key is not None:
            user.api_key = api_key
        if gmail_address is not None:
            user.gmail_address = gmail_address
        if gmail_app_password is not None:
            user.gmail_app_password = gmail_app_password
        
        db.commit()
        return {"success": True, "message": "저장되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def change_password(user_id: int, old_password: str, new_password: str) -> dict:
    """비밀번호 변경"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        if not verify_password(old_password, user.password_hash):
            return {"success": False, "error": "현재 비밀번호가 일치하지 않습니다."}
        
        user.password_hash = hash_password(new_password)
        db.commit()
        return {"success": True, "message": "비밀번호가 변경되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
