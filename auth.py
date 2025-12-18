# -*- coding: utf-8 -*-
"""
🔐 인증 모듈
회원가입, 로그인, 회원 관리
"""

import bcrypt
from datetime import datetime
from database import SessionLocal, User, UserRole, UserStatus

# ============================================
# 비밀번호 해싱
# ============================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except:
        return False

# ============================================
# 관리자 확인
# ============================================

def check_admin_exists() -> bool:
    """관리자가 존재하는지 확인"""
    if not SessionLocal:
        return False
    
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.LEVEL3).first()
        return admin is not None
    except Exception as e:
        print(f"관리자 확인 오류: {e}")
        return False
    finally:
        db.close()

def create_first_admin(email: str, password: str, name: str) -> dict:
    """최초 관리자 생성"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        # 이미 관리자가 있는지 확인
        existing_admin = db.query(User).filter(User.role == UserRole.LEVEL3).first()
        if existing_admin:
            return {"success": False, "error": "이미 관리자가 존재합니다."}
        
        # 이메일 중복 확인
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            return {"success": False, "error": "이미 사용 중인 이메일입니다."}
        
        # 관리자 생성
        admin = User(
            email=email,
            password_hash=hash_password(password),
            name=name,
            role=UserRole.LEVEL3,
            status=UserStatus.APPROVED,
            use_admin_api=True,
            api_usage_limit=9999
        )
        
        db.add(admin)
        db.commit()
        
        return {"success": True, "message": "✅ 관리자 계정이 생성되었습니다!"}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"생성 실패: {str(e)}"}
    finally:
        db.close()

# ============================================
# 회원가입 / 로그인
# ============================================

def register_user(email: str, password: str, name: str) -> dict:
    """회원가입"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        # 이메일 중복 확인
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return {"success": False, "error": "이미 사용 중인 이메일입니다."}
        
        # 사용자 생성
        user = User(
            email=email,
            password_hash=hash_password(password),
            name=name,
            role=UserRole.LEVEL1,
            status=UserStatus.PENDING
        )
        
        db.add(user)
        db.commit()
        
        return {"success": True, "message": "회원가입 완료! 관리자 승인을 기다려주세요."}
    
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
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            return {"success": False, "error": "존재하지 않는 이메일입니다."}
        
        if not verify_password(password, user.password_hash):
            return {"success": False, "error": "비밀번호가 일치하지 않습니다."}
        
        if user.status == UserStatus.PENDING:
            return {"success": False, "error": "관리자 승인 대기 중입니다."}
        
        if user.status == UserStatus.SUSPENDED:
            return {"success": False, "error": "계정이 정지되었습니다."}
        
        if user.status == UserStatus.BANNED:
            return {"success": False, "error": "계정이 강퇴되었습니다."}
        
        # 마지막 로그인 시간 업데이트
        user.last_login = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "status": user.status,
                "api_key": user.api_key,
                "use_admin_api": user.use_admin_api,
                "api_usage_count": user.api_usage_count,
                "api_usage_limit": user.api_usage_limit,
                "gmail_address": user.gmail_address,
                "gmail_app_password": user.gmail_app_password,
            }
        }
    
    except Exception as e:
        return {"success": False, "error": f"로그인 실패: {str(e)}"}
    finally:
        db.close()

# ============================================
# 회원 관리
# ============================================

def get_all_users() -> list:
    """모든 회원 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "status": u.status,
                "api_usage_count": u.api_usage_count,
                "api_usage_limit": u.api_usage_limit,
                "created_at": u.created_at.strftime("%Y-%m-%d") if u.created_at else "",
            }
            for u in users
        ]
    except:
        return []
    finally:
        db.close()

def get_pending_users() -> list:
    """승인 대기 회원 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.status == UserStatus.PENDING).all()
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

def approve_user(user_id: int) -> dict:
    """회원 승인"""
    if not SessionLocal:
        return {"success": False, "error": "DB 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.status = UserStatus.APPROVED
            db.commit()
            return {"success": True, "message": "승인되었습니다."}
        return {"success": False, "error": "사용자를 찾을 수 없습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def suspend_user(user_id: int) -> dict:
    """회원 정지"""
    if not SessionLocal:
        return {"success": False, "error": "DB 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.status = UserStatus.SUSPENDED
            db.commit()
            return {"success": True, "message": "정지되었습니다."}
        return {"success": False, "error": "사용자를 찾을 수 없습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def ban_user(user_id: int) -> dict:
    """회원 강퇴"""
    if not SessionLocal:
        return {"success": False, "error": "DB 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.status = UserStatus.BANNED
            db.commit()
            return {"success": True, "message": "강퇴되었습니다."}
        return {"success": False, "error": "사용자를 찾을 수 없습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def update_user_role(user_id: int, new_role: int) -> dict:
    """회원 등급 변경"""
    if not SessionLocal:
        return {"success": False, "error": "DB 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.role = new_role
            db.commit()
            return {"success": True, "message": "등급이 변경되었습니다."}
        return {"success": False, "error": "사용자를 찾을 수 없습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def update_user_api_limit(user_id: int, new_limit: int) -> dict:
    """API 한도 변경"""
    if not SessionLocal:
        return {"success": False, "error": "DB 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.api_usage_limit = new_limit
            db.commit()
            return {"success": True}
        return {"success": False}
    except:
        db.rollback()
        return {"success": False}
    finally:
        db.close()

def reset_user_api_usage(user_id: int) -> dict:
    """API 사용량 초기화"""
    if not SessionLocal:
        return {"success": False, "error": "DB 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.api_usage_count = 0
            db.commit()
            return {"success": True}
        return {"success": False}
    except:
        db.rollback()
        return {"success": False}
    finally:
        db.close()

# ============================================
# 프로필 업데이트
# ============================================

def update_user_profile(user_id: int, **kwargs) -> dict:
    """사용자 프로필 업데이트"""
    if not SessionLocal:
        return {"success": False, "error": "DB 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        user.updated_at = datetime.utcnow()
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
        return {"success": False, "error": "DB 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        if not verify_password(old_password, user.password_hash):
            return {"success": False, "error": "현재 비밀번호가 일치하지 않습니다."}
        
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.utcnow()
        db.commit()
        
        return {"success": True, "message": "비밀번호가 변경되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
