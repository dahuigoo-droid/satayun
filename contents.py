# -*- coding: utf-8 -*-
"""
📋 콘텐츠 관리
목차, 지침, 속지(템플릿) CRUD
"""

from database import SessionLocal, Chapter, Guideline, Template
from datetime import datetime

# ============================================
# 목차 (Chapter) CRUD
# ============================================

def get_chapters_by_service(service_id: int) -> list:
    """서비스별 목차 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        chapters = db.query(Chapter).filter(
            Chapter.service_id == service_id,
            Chapter.is_active == True
        ).order_by(Chapter.order).all()
        
        return [
            {
                "id": c.id,
                "service_id": c.service_id,
                "title": c.title,
                "description": c.description,
                "order": c.order,
            }
            for c in chapters
        ]
    except Exception as e:
        print(f"목차 조회 오류: {e}")
        return []
    finally:
        db.close()


def add_chapter(service_id: int, title: str, description: str = "", order: int = None) -> dict:
    """목차 추가"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if not title or not title.strip():
        return {"success": False, "error": "목차 제목을 입력해주세요."}
    
    db = SessionLocal()
    try:
        # 순서 결정
        if order is None:
            last_chapter = db.query(Chapter).filter(
                Chapter.service_id == service_id
            ).order_by(Chapter.order.desc()).first()
            new_order = (last_chapter.order + 1) if last_chapter else 1
        else:
            new_order = order
        
        new_chapter = Chapter(
            service_id=service_id,
            title=title.strip(),
            description=description.strip() if description else "",
            order=new_order,
            is_active=True
        )
        
        db.add(new_chapter)
        db.commit()
        
        return {"success": True, "message": f"'{title}' 목차가 추가되었습니다.", "id": new_chapter.id}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"목차 추가 실패: {str(e)}"}
    finally:
        db.close()


def update_chapter(chapter_id: int, title: str = None, description: str = None, order: int = None) -> dict:
    """목차 수정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            return {"success": False, "error": "목차를 찾을 수 없습니다."}
        
        if title is not None:
            chapter.title = title.strip()
        if description is not None:
            chapter.description = description.strip()
        if order is not None:
            chapter.order = order
        
        db.commit()
        return {"success": True, "message": "목차가 수정되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"목차 수정 실패: {str(e)}"}
    finally:
        db.close()


def delete_chapter(chapter_id: int) -> dict:
    """목차 삭제 (비활성화)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            return {"success": False, "error": "목차를 찾을 수 없습니다."}
        
        chapter.is_active = False
        db.commit()
        
        return {"success": True, "message": "목차가 삭제되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"목차 삭제 실패: {str(e)}"}
    finally:
        db.close()


def reorder_chapters(chapter_ids: list) -> dict:
    """목차 순서 변경"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        for idx, chapter_id in enumerate(chapter_ids):
            chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
            if chapter:
                chapter.order = idx + 1
        
        db.commit()
        return {"success": True, "message": "목차 순서가 변경되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"순서 변경 실패: {str(e)}"}
    finally:
        db.close()


# ============================================
# 지침 (Guideline) CRUD
# ============================================

def get_guidelines_by_service(service_id: int) -> list:
    """서비스별 지침 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        guidelines = db.query(Guideline).filter(
            Guideline.service_id == service_id,
            Guideline.is_active == True
        ).order_by(Guideline.id).all()
        
        return [
            {
                "id": g.id,
                "service_id": g.service_id,
                "title": g.title,
                "content": g.content,
                "created_at": g.created_at.strftime("%Y-%m-%d") if g.created_at else "",
                "updated_at": g.updated_at.strftime("%Y-%m-%d") if g.updated_at else "",
            }
            for g in guidelines
        ]
    except Exception as e:
        print(f"지침 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_guideline_by_id(guideline_id: int) -> dict:
    """지침 ID로 조회"""
    if not SessionLocal:
        return None
    
    db = SessionLocal()
    try:
        g = db.query(Guideline).filter(Guideline.id == guideline_id).first()
        if g:
            return {
                "id": g.id,
                "service_id": g.service_id,
                "title": g.title,
                "content": g.content,
            }
        return None
    except:
        return None
    finally:
        db.close()


def add_guideline(service_id: int, title: str, content: str) -> dict:
    """지침 추가"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if not title or not title.strip():
        return {"success": False, "error": "지침 제목을 입력해주세요."}
    
    if not content or not content.strip():
        return {"success": False, "error": "지침 내용을 입력해주세요."}
    
    db = SessionLocal()
    try:
        new_guideline = Guideline(
            service_id=service_id,
            title=title.strip(),
            content=content.strip(),
            is_active=True
        )
        
        db.add(new_guideline)
        db.commit()
        
        return {"success": True, "message": f"'{title}' 지침이 추가되었습니다.", "id": new_guideline.id}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"지침 추가 실패: {str(e)}"}
    finally:
        db.close()


def update_guideline(guideline_id: int, title: str = None, content: str = None) -> dict:
    """지침 수정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        guideline = db.query(Guideline).filter(Guideline.id == guideline_id).first()
        if not guideline:
            return {"success": False, "error": "지침을 찾을 수 없습니다."}
        
        if title is not None:
            guideline.title = title.strip()
        if content is not None:
            guideline.content = content.strip()
        
        guideline.updated_at = datetime.utcnow()
        
        db.commit()
        return {"success": True, "message": "지침이 수정되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"지침 수정 실패: {str(e)}"}
    finally:
        db.close()


def delete_guideline(guideline_id: int) -> dict:
    """지침 삭제 (비활성화)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        guideline = db.query(Guideline).filter(Guideline.id == guideline_id).first()
        if not guideline:
            return {"success": False, "error": "지침을 찾을 수 없습니다."}
        
        guideline.is_active = False
        db.commit()
        
        return {"success": True, "message": "지침이 삭제되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"지침 삭제 실패: {str(e)}"}
    finally:
        db.close()


# ============================================
# 속지/템플릿 (Template) CRUD
# ============================================

# 템플릿 타입 상수
TEMPLATE_TYPES = {
    "cover": "표지",
    "background": "속지 (본문 배경)",
    "intro": "소개",
    "info": "안내"
}


def get_templates_by_service(service_id: int, template_type: str = None) -> list:
    """서비스별 템플릿 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        query = db.query(Template).filter(
            Template.service_id == service_id,
            Template.is_active == True
        )
        
        if template_type:
            query = query.filter(Template.template_type == template_type)
        
        templates = query.order_by(Template.template_type, Template.id).all()
        
        return [
            {
                "id": t.id,
                "service_id": t.service_id,
                "template_type": t.template_type,
                "type_name": TEMPLATE_TYPES.get(t.template_type, t.template_type),
                "name": t.name,
                "image_path": t.image_path,
            }
            for t in templates
        ]
    except Exception as e:
        print(f"템플릿 조회 오류: {e}")
        return []
    finally:
        db.close()


def add_template(service_id: int, template_type: str, name: str, image_path: str = None) -> dict:
    """템플릿 추가"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if template_type not in TEMPLATE_TYPES:
        return {"success": False, "error": f"유효하지 않은 템플릿 유형입니다. ({', '.join(TEMPLATE_TYPES.keys())})"}
    
    if not name or not name.strip():
        return {"success": False, "error": "템플릿 이름을 입력해주세요."}
    
    db = SessionLocal()
    try:
        new_template = Template(
            service_id=service_id,
            template_type=template_type,
            name=name.strip(),
            image_path=image_path,
            is_active=True
        )
        
        db.add(new_template)
        db.commit()
        
        return {"success": True, "message": f"'{name}' 템플릿이 추가되었습니다.", "id": new_template.id}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"템플릿 추가 실패: {str(e)}"}
    finally:
        db.close()


def update_template(template_id: int, name: str = None, image_path: str = None) -> dict:
    """템플릿 수정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            return {"success": False, "error": "템플릿을 찾을 수 없습니다."}
        
        if name is not None:
            template.name = name.strip()
        if image_path is not None:
            template.image_path = image_path
        
        db.commit()
        return {"success": True, "message": "템플릿이 수정되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"템플릿 수정 실패: {str(e)}"}
    finally:
        db.close()


def delete_template(template_id: int) -> dict:
    """템플릿 삭제 (비활성화)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            return {"success": False, "error": "템플릿을 찾을 수 없습니다."}
        
        template.is_active = False
        db.commit()
        
        return {"success": True, "message": "템플릿이 삭제되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"템플릿 삭제 실패: {str(e)}"}
    finally:
        db.close()


def get_template_by_id(template_id: int) -> dict:
    """템플릿 ID로 조회"""
    if not SessionLocal:
        return None
    
    db = SessionLocal()
    try:
        t = db.query(Template).filter(Template.id == template_id).first()
        if t:
            return {
                "id": t.id,
                "service_id": t.service_id,
                "template_type": t.template_type,
                "name": t.name,
                "image_path": t.image_path,
            }
        return None
    except:
        return None
    finally:
        db.close()
