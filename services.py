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
        
        services = query.order_by(Service.order).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "categories": s.categories,
                "owner_id": s.owner_id,
                "is_active": s.is_active,
                "order": s.order,
            }
            for s in services
        ]
    except Exception as e:
        print(f"서비스 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_services_by_owner(owner_id) -> list:
    """소유자별 서비스 조회 (owner_id=None이면 관리자 공용)"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        if owner_id is None:
            query = db.query(Service).filter(Service.owner_id == None, Service.is_active == True)
        else:
            query = db.query(Service).filter(Service.owner_id == owner_id, Service.is_active == True)
        
        services = query.order_by(Service.order).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "categories": s.categories,
                "owner_id": s.owner_id,
                "is_active": s.is_active,
                "order": s.order,
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
                "is_active": service.is_active,
                "order": service.order,
            }
        return None
    except:
        return None
    finally:
        db.close()


def add_service(name: str, description: str = "", categories: str = "", owner_id: int = None) -> dict:
    """서비스 추가"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if not name or not name.strip():
        return {"success": False, "error": "서비스 이름을 입력해주세요."}
    
    db = SessionLocal()
    try:
        # 마지막 순서 가져오기
        last_service = db.query(Service).order_by(Service.order.desc()).first()
        new_order = (last_service.order + 1) if last_service else 1
        
        # 새 서비스 생성
        new_service = Service(
            name=name.strip(),
            description=description.strip() if description else "",
            categories=categories,
            owner_id=owner_id,
            order=new_order,
            is_active=True
        )
        
        db.add(new_service)
        db.commit()
        
        return {"success": True, "message": f"'{name}' 서비스가 추가되었습니다.", "id": new_service.id}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"서비스 추가 실패: {str(e)}"}
    finally:
        db.close()


def update_service(service_id: int, name: str = None, description: str = None, is_active: bool = None, order: int = None) -> dict:
    """서비스 수정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            return {"success": False, "error": "서비스를 찾을 수 없습니다."}
        
        if name is not None:
            # 이름 중복 확인 (자기 자신 제외)
            existing = db.query(Service).filter(
                Service.name == name.strip(),
                Service.id != service_id
            ).first()
            if existing:
                return {"success": False, "error": "이미 존재하는 서비스 이름입니다."}
            service.name = name.strip()
        
        if description is not None:
            service.description = description.strip()
        
        if is_active is not None:
            service.is_active = is_active
        
        if order is not None:
            service.order = order
        
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
