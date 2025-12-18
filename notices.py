# -*- coding: utf-8 -*-
"""
📢 공지사항 관리
공지 작성, 수정, 삭제, 조회
"""

from database import SessionLocal, Notice
from datetime import datetime

# ============================================
# 공지사항 CRUD
# ============================================

def get_all_notices(include_inactive=False) -> list:
    """모든 공지사항 조회 (고정 공지 우선, 최신순)"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        query = db.query(Notice)
        
        if not include_inactive:
            query = query.filter(Notice.is_active == True)
        
        # 고정 공지 우선, 그 다음 최신순
        notices = query.order_by(Notice.is_pinned.desc(), Notice.created_at.desc()).all()
        
        return [
            {
                "id": n.id,
                "author_id": n.author_id,
                "author_name": n.author.name if n.author else "알 수 없음",
                "title": n.title,
                "content": n.content,
                "image_path": n.image_path,
                "is_pinned": n.is_pinned,
                "is_active": n.is_active,
                "created_at": n.created_at.strftime("%Y-%m-%d %H:%M") if n.created_at else "",
                "updated_at": n.updated_at.strftime("%Y-%m-%d %H:%M") if n.updated_at else "",
            }
            for n in notices
        ]
    except Exception as e:
        print(f"공지사항 조회 오류: {e}")
        return []
    finally:
        db.close()


def get_notice_by_id(notice_id: int) -> dict:
    """공지사항 ID로 조회"""
    if not SessionLocal:
        return None
    
    db = SessionLocal()
    try:
        n = db.query(Notice).filter(Notice.id == notice_id).first()
        if n:
            return {
                "id": n.id,
                "author_id": n.author_id,
                "author_name": n.author.name if n.author else "알 수 없음",
                "title": n.title,
                "content": n.content,
                "image_path": n.image_path,
                "is_pinned": n.is_pinned,
                "is_active": n.is_active,
                "created_at": n.created_at.strftime("%Y-%m-%d %H:%M") if n.created_at else "",
                "updated_at": n.updated_at.strftime("%Y-%m-%d %H:%M") if n.updated_at else "",
            }
        return None
    except:
        return None
    finally:
        db.close()


def create_notice(author_id: int, title: str, content: str, image_path: str = None, is_pinned: bool = False) -> dict:
    """공지사항 작성"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    if not title or not title.strip():
        return {"success": False, "error": "제목을 입력해주세요."}
    
    if not content or not content.strip():
        return {"success": False, "error": "내용을 입력해주세요."}
    
    db = SessionLocal()
    try:
        new_notice = Notice(
            author_id=author_id,
            title=title.strip(),
            content=content.strip(),
            image_path=image_path,
            is_pinned=is_pinned,
            is_active=True
        )
        
        db.add(new_notice)
        db.commit()
        
        return {"success": True, "message": "공지사항이 등록되었습니다.", "id": new_notice.id}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"공지사항 등록 실패: {str(e)}"}
    finally:
        db.close()


def update_notice(notice_id: int, title: str = None, content: str = None, image_path: str = None, is_pinned: bool = None) -> dict:
    """공지사항 수정"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        notice = db.query(Notice).filter(Notice.id == notice_id).first()
        if not notice:
            return {"success": False, "error": "공지사항을 찾을 수 없습니다."}
        
        if title is not None:
            notice.title = title.strip()
        if content is not None:
            notice.content = content.strip()
        if image_path is not None:
            notice.image_path = image_path
        if is_pinned is not None:
            notice.is_pinned = is_pinned
        
        notice.updated_at = datetime.utcnow()
        
        db.commit()
        return {"success": True, "message": "공지사항이 수정되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"공지사항 수정 실패: {str(e)}"}
    finally:
        db.close()


def delete_notice(notice_id: int) -> dict:
    """공지사항 삭제 (비활성화)"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        notice = db.query(Notice).filter(Notice.id == notice_id).first()
        if not notice:
            return {"success": False, "error": "공지사항을 찾을 수 없습니다."}
        
        notice.is_active = False
        db.commit()
        
        return {"success": True, "message": "공지사항이 삭제되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"공지사항 삭제 실패: {str(e)}"}
    finally:
        db.close()


def toggle_pin_notice(notice_id: int) -> dict:
    """공지사항 고정/해제 토글"""
    if not SessionLocal:
        return {"success": False, "error": "데이터베이스 연결 실패"}
    
    db = SessionLocal()
    try:
        notice = db.query(Notice).filter(Notice.id == notice_id).first()
        if not notice:
            return {"success": False, "error": "공지사항을 찾을 수 없습니다."}
        
        notice.is_pinned = not notice.is_pinned
        db.commit()
        
        status = "고정" if notice.is_pinned else "고정 해제"
        return {"success": True, "message": f"공지사항이 {status}되었습니다."}
    
    except Exception as e:
        db.rollback()
        return {"success": False, "error": f"처리 실패: {str(e)}"}
    finally:
        db.close()


def get_pinned_notices() -> list:
    """고정된 공지사항만 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        notices = db.query(Notice).filter(
            Notice.is_active == True,
            Notice.is_pinned == True
        ).order_by(Notice.created_at.desc()).all()
        
        return [
            {
                "id": n.id,
                "title": n.title,
                "created_at": n.created_at.strftime("%Y-%m-%d") if n.created_at else "",
            }
            for n in notices
        ]
    except:
        return []
    finally:
        db.close()


def get_recent_notices(limit: int = 5) -> list:
    """최근 공지사항 조회"""
    if not SessionLocal:
        return []
    
    db = SessionLocal()
    try:
        notices = db.query(Notice).filter(
            Notice.is_active == True
        ).order_by(Notice.is_pinned.desc(), Notice.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": n.id,
                "title": n.title,
                "is_pinned": n.is_pinned,
                "created_at": n.created_at.strftime("%Y-%m-%d") if n.created_at else "",
            }
            for n in notices
        ]
    except:
        return []
    finally:
        db.close()
