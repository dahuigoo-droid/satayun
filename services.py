# -*- coding: utf-8 -*-
"""
📦 서비스 관리
서비스 추가/수정/삭제, 시스템 설정
"""

from database import SessionLocal, Service, SystemConfig
from datetime import datetime

# ============================================
# 서비스 CRUD
# ============================================

def get_all_services(include_inactive=False) -> list:
    """모든 서비스 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        query = db.query(Service)
        if not include_inactive:
            query = query.filter(Service.is_active == True)
        
        services = query.order_by(Service.created_at.desc()).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "owner_id": s.owner_id,
                "is_active": s.is_active,
                "font_family": s.font_family or "NanumGothic",
                "font_size_title": s.font_size_title or 24,
                "font_size_subtitle": s.font_size_subtitle or 16,
                "font_size_body": s.font_size_body or 12,
                "letter_spacing": s.letter_spacing or 0,
                "line_height": s.line_height or 180,
            }
            for s in services
        ]
    except Exception as e:
        print(f"서비스 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_admin_services() -> list:
    """관리자 공용 서비스 조회 (owner_id가 NULL인 것)"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        services = db.query(Service).filter(
            Service.owner_id == None,
            Service.is_active == True
        ).order_by(Service.created_at.desc()).all()
        
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "owner_id": s.owner_id,
                "is_active": s.is_active,
                "font_family": s.font_family or "NanumGothic",
                "font_size_title": s.font_size_title or 24,
                "font_size_subtitle": s.font_size_subtitle or 16,
                "font_size_body": s.font_size_body or 12,
                "letter_spacing": s.letter_spacing or 0,
                "line_height": s.line_height or 180,
            }
            for s in services
        ]
    except Exception as e:
        print(f"서비스 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_user_services(user_id: int) -> list:
    """특정 사용자의 개별 서비스 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        services = db.query(Service).filter(
            Service.owner_id == user_id,
            Service.is_active == True
        ).order_by(Service.created_at.desc()).all()
        
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "owner_id": s.owner_id,
                "is_active": s.is_active,
                "font_family": s.font_family or "NanumGothic",
                "font_size_title": s.font_size_title or 24,
                "font_size_subtitle": s.font_size_subtitle or 16,
                "font_size_body": s.font_size_body or 12,
                "letter_spacing": s.letter_spacing or 0,
                "line_height": s.line_height or 180,
            }
            for s in services
        ]
    except Exception as e:
        print(f"서비스 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_service_by_id(service_id: int) -> dict:
    """서비스 ID로 조회"""
    if not SessionLocal:
        return None
    
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if service:
            return {
                "id": service.id,
                "name": service.name,
                "description": service.description,
                "owner_id": service.owner_id,
                "is_active": service.is_active,
            }
        return None
    except:
        return None
    finally:
        db.close()


def add_service(name: str, description: str = "", owner_id: int = None,
                font_family: str = "NanumGothic", font_size_title: int = 24,
                font_size_subtitle: int = 16, font_size_body: int = 12,
                letter_spacing: int = 0, line_height: int = 180) -> dict:
    """서비스 추가 (owner_id=None이면 관리자 공용)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if not name or not name.strip():
        return {"success": False, "error": "서비스 이름을 입력해주세요."}
    
    db = SessionLocal()
    try:
        # 새 서비스 생성
        new_service = Service(
            name=name.strip(),
            description=description.strip() if description else "",
            owner_id=owner_id,
            is_active=True,
            font_family=font_family,
            font_size_title=font_size_title,
            font_size_subtitle=font_size_subtitle,
            font_size_body=font_size_body,
            letter_spacing=letter_spacing,
            line_height=line_height
        )
        
        db.add(new_service)
        db.commit()
        
        return {"success": True, "message": f"'{name}' 서비스가 추가되었습니다.", "id": new_service.id}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"서비스 추가 실패: {str(e)}"}
    finally:
        db.close()


def update_service(service_id: int, name: str = None, description: str = None, is_active: bool = None,
                   font_family: str = None, font_size_title: int = None, font_size_subtitle: int = None,
                   font_size_body: int = None, letter_spacing: int = None, line_height: int = None) -> dict:
    """서비스 수정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            return {"success": False, "error": "서비스를 찾을 수 없습니다."}
        
        if name is not None:
            service.name = name.strip()
        
        if description is not None:
            service.description = description.strip()
        
        if is_active is not None:
            service.is_active = is_active
        
        if font_family is not None:
            service.font_family = font_family
        
        if font_size_title is not None:
            service.font_size_title = font_size_title
        
        if font_size_subtitle is not None:
            service.font_size_subtitle = font_size_subtitle
        
        if font_size_body is not None:
            service.font_size_body = font_size_body
        
        if letter_spacing is not None:
            service.letter_spacing = letter_spacing
        
        if line_height is not None:
            service.line_height = line_height
        
        db.commit()
        return {"success": True, "message": "서비스가 수정되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"서비스 수정 실패: {str(e)}"}
    finally:
        db.close()


def delete_service(service_id: int) -> dict:
    """서비스 삭제 (실제 삭제가 아닌 비활성화)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            return {"success": False, "error": "서비스를 찾을 수 없습니다."}
        
        service.is_active = False
        db.commit()
        
        return {"success": True, "message": f"'{service.name}' 서비스가 비활성화되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"서비스 삭제 실패: {str(e)}"}
    finally:
        db.close()


def restore_service(service_id: int) -> dict:
    """서비스 복구 (활성화)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            return {"success": False, "error": "서비스를 찾을 수 없습니다."}
        
        service.is_active = True
        db.commit()
        
        return {"success": True, "message": f"'{service.name}' 서비스가 복구되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"서비스 복구 실패: {str(e)}"}
    finally:
        db.close()


def reorder_services(service_ids: list) -> dict:
    """서비스 순서 변경"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        for idx, service_id in enumerate(service_ids):
            service = db.query(Service).filter(Service.id == service_id).first()
            if service:
                service.order = idx + 1
        
        db.commit()
        return {"success": True, "message": "서비스 순서가 변경되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"순서 변경 실패: {str(e)}"}
    finally:
        db.close()


# ============================================
# 시스템 설정
# ============================================

def get_system_config(key: str, default=None):
    """시스템 설정 조회"""
    if not SessionLocal:
        return default
    
    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        return config.value if config else default
    except:
        return default
    finally:
        db.close()


def set_system_config(key: str, value: str) -> dict:
    """시스템 설정 저장"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        
        if config:
            config.value = value
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(key=key, value=value)
            db.add(config)
        
        db.commit()
        return {"success": True, "message": "설정이 저장되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"설정 저장 실패: {str(e)}"}
    finally:
        db.close()


def get_all_system_configs() -> dict:
    """모든 시스템 설정 조회"""
    if not SessionLocal:
        return {}
    
    db = SessionLocal()
    try:
        configs = db.query(SystemConfig).all()
        return {c.key: c.value for c in configs}
    except:
        return {}
    finally:
        db.close()


# ============================================
# 시스템 설정 키 상수
# ============================================

class ConfigKeys:
    ADMIN_API_KEY = "admin_api_key"
    ADMIN_GMAIL = "admin_gmail"
    ADMIN_GMAIL_PASSWORD = "admin_gmail_password"
    DEFAULT_API_LIMIT = "default_api_limit"
    KAKAO_CHANNEL_ID = "kakao_channel_id"
    KAKAO_API_KEY = "kakao_api_key"
