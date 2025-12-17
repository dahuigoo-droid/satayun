# -*- coding: utf-8 -*-
"""
🔐 인증 시스템
회원가입, 로그인, 비밀번호 관리
"""

import bcrypt
from database import SessionLocal, User, UserStatus, UserRole

# ============================================
# 비밀번호 해시 함수
# ============================================

def hash_password(password: str) -> str:
    """비밀번호를 해시하여 반환"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """비밀번호 검증"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# ============================================
# 회원가입
# ============================================

def register_user(email: str, password: str, name: str) -> dict:
    """
    회원가입
    - 성공 시: {"success": True, "message": "..."}
    - 실패 시: {"success": False, "error": "..."}
    """
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        # 이메일 중복 확인
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return {"success": False, "error": "이미 사용 중인 이메일입니다."}
        
        # 비밀번호 해시
        password_hash = hash_password(password)
        
        # 새 사용자 생성 (승인 대기 상태)
        new_user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            role=UserRole.LEVEL_1,
            status=UserStatus.PENDING.value
        )
        
        db.add(new_user)
        db.commit()
        
        return {"success": True, "message": "회원가입이 완료되었습니다. 관리자 승인 후 이용 가능합니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"회원가입 실패: {str(e)}"}
    finally:
        db.close()


# ============================================
# 로그인
# ============================================

def login_user(email: str, password: str) -> dict:
    """
    로그인
    - 성공 시: {"success": True, "user": User 객체}
    - 실패 시: {"success": False, "error": "..."}
    """
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        # 사용자 조회
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            return {"success": False, "error": "존재하지 않는 이메일입니다."}
        
        # 비밀번호 확인
        if not verify_password(password, user.password_hash):
            return {"success": False, "error": "비밀번호가 일치하지 않습니다."}
        
        # 상태 확인
        if user.status == UserStatus.PENDING.value:
            return {"success": False, "error": "관리자 승인 대기 중입니다."}
        
        if user.status == UserStatus.SUSPENDED.value:
            return {"success": False, "error": "사용이 중지된 계정입니다. 관리자에게 문의하세요."}
        
        if user.status == UserStatus.BANNED.value:
            return {"success": False, "error": "강퇴된 계정입니다."}
        
        # 로그인 성공 - 사용자 정보 반환
        user_data = {
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
        
        return {"success": True, "user": user_data}
    
    except Exception as e:
        return {"success": False, "error": f"로그인 실패: {str(e)}"}
    finally:
        db.close()


# ============================================
# 사용자 정보 업데이트
# ============================================

def update_user_profile(user_id: int, **kwargs) -> dict:
    """사용자 프로필 업데이트"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        # 업데이트 가능한 필드
        allowed_fields = [
            'name', 'api_key', 'use_admin_api', 
            'gmail_address', 'gmail_app_password'
        ]
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(user, field, value)
        
        db.commit()
        return {"success": True, "message": "프로필이 업데이트되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"업데이트 실패: {str(e)}"}
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
        
        # 기존 비밀번호 확인
        if not verify_password(old_password, user.password_hash):
            return {"success": False, "error": "기존 비밀번호가 일치하지 않습니다."}
        
        # 새 비밀번호 설정
        user.password_hash = hash_password(new_password)
        db.commit()
        
        return {"success": True, "message": "비밀번호가 변경되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"비밀번호 변경 실패: {str(e)}"}
    finally:
        db.close()


# ============================================
# 관리자 기능 - 회원 관리
# ============================================

def get_all_users() -> list:
    """모든 사용자 목록 조회"""
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
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
            }
            for u in users
        ]
    except Exception as e:
        print(f"사용자 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_pending_users() -> list:
    """승인 대기 중인 사용자 목록"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.status == UserStatus.PENDING.value).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
            }
            for u in users
        ]
    except:
        return []
    finally:
        db.close()


def approve_user(user_id: int) -> dict:
    """사용자 승인"""
    return update_user_status(user_id, UserStatus.APPROVED.value)


def suspend_user(user_id: int) -> dict:
    """사용자 사용 중지"""
    return update_user_status(user_id, UserStatus.SUSPENDED.value)


def ban_user(user_id: int) -> dict:
    """사용자 강퇴"""
    return update_user_status(user_id, UserStatus.BANNED.value)


def update_user_status(user_id: int, status: str) -> dict:
    """사용자 상태 변경"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.status = status
        db.commit()
        
        status_text = {
            "approved": "승인",
            "suspended": "사용 중지",
            "banned": "강퇴"
        }
        
        return {"success": True, "message": f"사용자가 {status_text.get(status, status)} 처리되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"상태 변경 실패: {str(e)}"}
    finally:
        db.close()


def update_user_role(user_id: int, role: int) -> dict:
    """사용자 등급 변경"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if role not in [1, 2, 3]:
        return {"success": False, "error": "유효하지 않은 등급입니다."}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.role = role
        db.commit()
        
        return {"success": True, "message": f"사용자 등급이 {role}단계로 변경되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"등급 변경 실패: {str(e)}"}
    finally:
        db.close()


def update_user_api_limit(user_id: int, limit: int) -> dict:
    """사용자 API 사용 한도 변경"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.api_usage_limit = limit
        db.commit()
        
        return {"success": True, "message": f"API 사용 한도가 {limit}으로 변경되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"한도 변경 실패: {str(e)}"}
    finally:
        db.close()


def reset_user_api_usage(user_id: int) -> dict:
    """사용자 API 사용량 초기화"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        
        user.api_usage_count = 0
        db.commit()
        
        return {"success": True, "message": "API 사용량이 초기화되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"초기화 실패: {str(e)}"}
    finally:
        db.close()


# ============================================
# 첫 관리자 생성 (시스템 초기화용)
# ============================================

def create_first_admin(email: str, password: str, name: str) -> dict:
    """첫 번째 관리자 계정 생성"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        # 이미 관리자가 있는지 확인
        existing_admin = db.query(User).filter(User.role == UserRole.LEVEL_3).first()
        if existing_admin:
            return {"success": False, "error": "이미 관리자가 존재합니다."}
        
        # 관리자 계정 생성
        password_hash = hash_password(password)
        admin = User(
            email=email,
            password_hash=password_hash,
            name=name,
            role=UserRole.LEVEL_3,
            status=UserStatus.APPROVED.value
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
        admin = db.query(User).filter(User.role == UserRole.LEVEL_3).first()
        return admin is not None
    except:
        return False
    finally:
        db.close()
