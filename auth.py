# -*- coding: utf-8 -*-
"""
🔐 인증 및 사용자 관리
회원별 권한 관리 기능 추가
"""

import bcrypt
from datetime import datetime
from database import SessionLocal, User, UserRole, UserStatus, PermissionType

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
            role=UserRole.NORMAL,
            status=UserStatus.PENDING,
            permission_type=PermissionType.EXECUTE
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
        
        if user.status == UserStatus.PENDING:
            return {"success": False, "error": "관리자 승인 대기 중입니다."}
        
        if user.status == UserStatus.SUSPENDED:
            return {"success": False, "error": "정지된 계정입니다."}
        
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
                "permission_type": user.permission_type,
                "api_mode": user.api_mode,
                "email_mode": user.email_mode,
                "service_mode": user.service_mode,
                "design_mode": user.design_mode,
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
        admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if admin_exists:
            return {"success": False, "error": "이미 관리자가 존재합니다."}
        
        admin = User(
            email=email.strip().lower(),
            password_hash=hash_password(password),
            name=name.strip(),
            role=UserRole.ADMIN,
            status=UserStatus.APPROVED,
            permission_type=PermissionType.INDIVIDUAL
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
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
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
        users = db.query(User).order_by(User.role.desc(), User.created_at.desc()).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "status": u.status,
                "permission_type": u.permission_type,
                "api_mode": u.api_mode,
                "email_mode": u.email_mode,
                "service_mode": u.service_mode,
                "design_mode": u.design_mode,
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


def get_user_by_id(user_id: int) -> dict:
    """ID로 사용자 조회"""
    if not SessionLocal:
        return None
    
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if u:
            return {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "status": u.status,
                "permission_type": u.permission_type,
                "api_mode": u.api_mode,
                "email_mode": u.email_mode,
                "service_mode": u.service_mode,
                "design_mode": u.design_mode,
                "api_key": u.api_key,
                "gmail_address": u.gmail_address,
                "gmail_app_password": u.gmail_app_password,
            }
        return None
    except:
        return None
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
        
        user.status = UserStatus.APPROVED
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
        
        user.status = UserStatus.SUSPENDED
        db.commit()
        return {"success": True, "message": f"{user.name}님이 정지되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def update_user_role(user_id: int, role: int) -> dict:
    """사용자 등급 변경"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.role = role
        db.commit()
        return {"success": True, "message": "등급이 변경되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def update_user_permission(user_id: int, permission_type: str) -> dict:
    """사용자 권한 타입 변경 (execute/individual)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.permission_type = permission_type
        db.commit()
        return {"success": True, "message": "권한이 변경되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def update_user_modes(user_id: int, api_mode: str = None, email_mode: str = None, 
                      service_mode: str = None, design_mode: str = None) -> dict:
    """사용자별 모드 설정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        if api_mode is not None:
            user.api_mode = api_mode
        if email_mode is not None:
            user.email_mode = email_mode
        if service_mode is not None:
            user.service_mode = service_mode
        if design_mode is not None:
            user.design_mode = design_mode
        
        db.commit()
        return {"success": True, "message": "모드 설정이 변경되었습니다."}
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
