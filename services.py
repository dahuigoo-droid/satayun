# -*- coding: utf-8 -*-
"""
📦 서비스 관리 + 자료실
"""

from database import SessionLocal, Service, SystemConfig, ChapterLibrary, GuidelineLibrary
from datetime import datetime

# ============================================
# 서비스 조회
# ============================================

def _service_to_dict(s) -> dict:
    """Service 객체를 dict로 변환"""
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "owner_id": s.owner_id,
        "is_active": s.is_active,
        "service_type": s.service_type or "single",
        "font_family": s.font_family or "NanumGothic",
        "font_size_title": s.font_size_title or 24,
        "font_size_subtitle": s.font_size_subtitle or 16,
        "font_size_body": s.font_size_body or 12,
        "letter_spacing": s.letter_spacing or 0,
        "line_height": s.line_height or 180,
        "char_width": s.char_width or 100,
        "margin_top": s.margin_top or 25,
        "margin_bottom": s.margin_bottom or 25,
        "margin_left": s.margin_left or 25,
        "margin_right": s.margin_right or 25,
    }


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
        return [_service_to_dict(s) for s in services]
    except Exception as e:
        print(f"서비스 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_admin_services() -> list:
    """관리자 공용 서비스 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        services = db.query(Service).filter(
            Service.owner_id == None,
            Service.is_active == True
        ).order_by(Service.created_at.desc()).all()
        return [_service_to_dict(s) for s in services]
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
        return [_service_to_dict(s) for s in services]
    except Exception as e:
        print(f"서비스 조회 오류: {e}")
        return []
    finally:
        db.close()


# ============================================
# 서비스 CRUD
# ============================================

def add_service(name: str, description: str = "", owner_id: int = None,
                service_type: str = "single",
                font_family: str = "NanumGothic", font_size_title: int = 24,
                font_size_subtitle: int = 16, font_size_body: int = 12,
                letter_spacing: int = 0, line_height: int = 180,
                char_width: int = 100, margin_top: int = 25, margin_bottom: int = 25,
                margin_left: int = 25, margin_right: int = 25) -> dict:
    """서비스 추가"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if not name or not name.strip():
        return {"success": False, "error": "서비스 이름을 입력해주세요."}
    
    db = SessionLocal()
    try:
        new_service = Service(
            name=name.strip(),
            description=description.strip() if description else "",
            owner_id=owner_id,
            is_active=True,
            service_type=service_type,
            font_family=font_family,
            font_size_title=font_size_title,
            font_size_subtitle=font_size_subtitle,
            font_size_body=font_size_body,
            letter_spacing=letter_spacing,
            line_height=line_height,
            char_width=char_width,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            margin_right=margin_right
        )
        
        db.add(new_service)
        db.commit()
        
        return {"success": True, "message": f"'{name}' 서비스가 추가되었습니다.", "id": new_service.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def update_service(service_id: int, name: str = None, description: str = None, is_active: bool = None,
                   service_type: str = None,
                   font_family: str = None, font_size_title: int = None, font_size_subtitle: int = None,
                   font_size_body: int = None, letter_spacing: int = None, line_height: int = None,
                   char_width: int = None, margin_top: int = None, margin_bottom: int = None,
                   margin_left: int = None, margin_right: int = None) -> dict:
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
        if service_type is not None:
            service.service_type = service_type
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
        if char_width is not None:
            service.char_width = char_width
        if margin_top is not None:
            service.margin_top = margin_top
        if margin_bottom is not None:
            service.margin_bottom = margin_bottom
        if margin_left is not None:
            service.margin_left = margin_left
        if margin_right is not None:
            service.margin_right = margin_right
        
        db.commit()
        return {"success": True, "message": "서비스가 수정되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def delete_service(service_id: int) -> dict:
    """서비스 삭제 (soft delete)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            return {"success": False, "error": "서비스를 찾을 수 없습니다."}
        
        service.is_active = False
        db.commit()
        return {"success": True, "message": "서비스가 삭제되었습니다."}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ============================================
# 시스템 설정
# ============================================

class ConfigKeys:
    ADMIN_API_KEY = "admin_api_key"
    ADMIN_GMAIL = "admin_gmail"
    ADMIN_GMAIL_PASSWORD = "admin_gmail_password"


def get_system_config(key: str, default: str = "") -> str:
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
        else:
            config = SystemConfig(key=key, value=value)
            db.add(config)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ============================================
# 자료실 - 목차
# ============================================

def get_chapter_library(user_id: int = None, category: str = None) -> list:
    """목차 자료실 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        query = db.query(ChapterLibrary).filter(ChapterLibrary.is_active == True)
        
        if user_id:
            # 사용자 것 + 공용
            query = query.filter((ChapterLibrary.user_id == user_id) | (ChapterLibrary.user_id == None))
        
        if category:
            query = query.filter(ChapterLibrary.category == category)
        
        items = query.order_by(ChapterLibrary.created_at.desc()).all()
        return [
            {
                "id": item.id,
                "user_id": item.user_id,
                "title": item.title,
                "content": item.content,
                "category": item.category,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in items
        ]
    except Exception as e:
        print(f"목차 자료실 조회 오류: {e}")
        return []
    finally:
        db.close()


def add_chapter_library(title: str, content: str = "", category: str = None, user_id: int = None) -> dict:
    """목차 자료실에 추가"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        item = ChapterLibrary(
            user_id=user_id,
            title=title.strip(),
            content=content.strip() if content else "",
            category=category
        )
        db.add(item)
        db.commit()
        return {"success": True, "id": item.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def update_chapter_library(item_id: int, title: str = None, content: str = None, category: str = None) -> dict:
    """목차 자료실 수정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        item = db.query(ChapterLibrary).filter(ChapterLibrary.id == item_id).first()
        if not item:
            return {"success": False, "error": "항목을 찾을 수 없습니다."}
        
        if title is not None:
            item.title = title.strip()
        if content is not None:
            item.content = content.strip()
        if category is not None:
            item.category = category
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def delete_chapter_library(item_id: int) -> dict:
    """목차 자료실에서 삭제"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        item = db.query(ChapterLibrary).filter(ChapterLibrary.id == item_id).first()
        if item:
            item.is_active = False
            db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ============================================
# 자료실 - 지침
# ============================================

def get_guideline_library(user_id: int = None, category: str = None) -> list:
    """지침 자료실 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        query = db.query(GuidelineLibrary).filter(GuidelineLibrary.is_active == True)
        
        if user_id:
            query = query.filter((GuidelineLibrary.user_id == user_id) | (GuidelineLibrary.user_id == None))
        
        if category:
            query = query.filter(GuidelineLibrary.category == category)
        
        items = query.order_by(GuidelineLibrary.created_at.desc()).all()
        return [
            {
                "id": item.id,
                "user_id": item.user_id,
                "title": item.title,
                "content": item.content,
                "category": item.category,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in items
        ]
    except Exception as e:
        print(f"지침 자료실 조회 오류: {e}")
        return []
    finally:
        db.close()


def add_guideline_library(title: str, content: str, category: str = None, user_id: int = None) -> dict:
    """지침 자료실에 추가"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        item = GuidelineLibrary(
            user_id=user_id,
            title=title.strip(),
            content=content.strip(),
            category=category
        )
        db.add(item)
        db.commit()
        return {"success": True, "id": item.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def update_guideline_library(item_id: int, title: str = None, content: str = None, category: str = None) -> dict:
    """지침 자료실 수정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        item = db.query(GuidelineLibrary).filter(GuidelineLibrary.id == item_id).first()
        if not item:
            return {"success": False, "error": "항목을 찾을 수 없습니다."}
        
        if title is not None:
            item.title = title.strip()
        if content is not None:
            item.content = content.strip()
        if category is not None:
            item.category = category
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def delete_guideline_library(item_id: int) -> dict:
    """지침 자료실에서 삭제"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        item = db.query(GuidelineLibrary).filter(GuidelineLibrary.id == item_id).first()
        if item:
            item.is_active = False
            db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
