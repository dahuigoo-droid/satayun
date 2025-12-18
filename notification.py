# -*- coding: utf-8 -*-
"""
📧 알림 발송 모듈
- 이메일 발송 (Gmail SMTP)
- 카카오 알림톡 (향후 구현)
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

# ============================================
# 이메일 발송
# ============================================

def send_email(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    attachment_path: str = None,
    attachment_name: str = None
) -> dict:
    """
    Gmail SMTP로 이메일 발송
    
    Args:
        sender_email: 발신자 Gmail 주소
        sender_password: Gmail 앱 비밀번호 (16자리)
        recipient_email: 수신자 이메일
        subject: 제목
        body: 본문 (HTML 가능)
        attachment_path: 첨부파일 경로
        attachment_name: 첨부파일 이름 (없으면 경로에서 추출)
    
    Returns:
        {"success": True/False, "message": "..."}
    """
    try:
        # 이메일 메시지 생성
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # 본문 추가
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        # 첨부파일 추가
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                
                filename = attachment_name or os.path.basename(attachment_path)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
                msg.attach(part)
        
        # Gmail SMTP 연결 및 발송
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return {"success": True, "message": f"이메일 발송 완료: {recipient_email}"}
    
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "message": "Gmail 인증 실패. 앱 비밀번호를 확인해주세요."}
    except smtplib.SMTPRecipientsRefused:
        return {"success": False, "message": f"수신자 이메일 주소 오류: {recipient_email}"}
    except Exception as e:
        return {"success": False, "message": f"이메일 발송 실패: {str(e)}"}


def send_email_with_pdf(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    recipient_name: str,
    service_type: str,
    pdf_path: str
) -> dict:
    """
    PDF 첨부 이메일 발송 (템플릿 적용)
    """
    subject = f"[{service_type}] {recipient_name}님의 감정서가 도착했습니다"
    
    body = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; padding: 30px; border-radius: 10px;">
            <h2 style="color: #333; border-bottom: 2px solid #6c5ce7; padding-bottom: 10px;">
                🔮 {service_type} 감정서
            </h2>
            
            <p style="font-size: 16px; color: #555; line-height: 1.8;">
                안녕하세요, <strong>{recipient_name}</strong>님!<br><br>
                요청하신 <strong>{service_type}</strong> 감정서가 완성되었습니다.<br>
                첨부된 PDF 파일을 확인해주세요.
            </p>
            
            <div style="background: #6c5ce7; color: white; padding: 15px; border-radius: 8px; margin: 20px 0;">
                📎 첨부파일: {os.path.basename(pdf_path)}
            </div>
            
            <p style="font-size: 14px; color: #888; margin-top: 30px;">
                본 메일은 자동 발송되었습니다.<br>
                문의사항은 회신해주시기 바랍니다.
            </p>
            
            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
            
            <p style="font-size: 12px; color: #aaa; text-align: center;">
                발송일시: {datetime.now().strftime("%Y년 %m월 %d일 %H:%M")}
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_email(
        sender_email=sender_email,
        sender_password=sender_password,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        attachment_path=pdf_path
    )


def send_bulk_emails(
    sender_email: str,
    sender_password: str,
    recipients: list,
    service_type: str,
    progress_callback=None
) -> dict:
    """
    대량 이메일 발송
    
    Args:
        recipients: [{"name": "이름", "email": "이메일", "pdf_path": "경로"}, ...]
        progress_callback: 진행 콜백 함수 (progress, message)
    
    Returns:
        {"success_count": N, "fail_count": M, "results": [...]}
    """
    results = []
    success_count = 0
    fail_count = 0
    total = len(recipients)
    
    for idx, recipient in enumerate(recipients):
        if progress_callback:
            progress_callback((idx + 1) / total, f"{recipient['name']}에게 발송 중...")
        
        result = send_email_with_pdf(
            sender_email=sender_email,
            sender_password=sender_password,
            recipient_email=recipient['email'],
            recipient_name=recipient['name'],
            service_type=service_type,
            pdf_path=recipient['pdf_path']
        )
        
        if result['success']:
            success_count += 1
        else:
            fail_count += 1
        
        results.append({
            "name": recipient['name'],
            "email": recipient['email'],
            "success": result['success'],
            "message": result['message']
        })
    
    return {
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results
    }


# ============================================
# 카카오 알림톡 (향후 구현)
# ============================================

def send_kakao_notification(
    channel_id: str,
    api_key: str,
    recipient_phone: str,
    recipient_name: str,
    service_type: str,
    download_link: str
) -> dict:
    """
    카카오 알림톡 발송 (비즈니스 채널 필요)
    
    ⚠️ 카카오 비즈니스 채널 설정 후 구현 필요:
    1. https://business.kakao.com 에서 채널 생성
    2. 비즈메시지 신청
    3. 알림톡 템플릿 등록 및 승인
    4. API 연동
    """
    # TODO: 카카오 API 연동
    return {
        "success": False,
        "message": "카카오 알림톡은 비즈니스 채널 설정 후 사용 가능합니다."
    }


def send_sms_notification(
    recipient_phone: str,
    recipient_name: str,
    message: str
) -> dict:
    """
    SMS 발송 (향후 구현)
    
    ⚠️ SMS 발송 서비스 연동 필요:
    - NHN Cloud, Twilio, 알리고 등
    """
    # TODO: SMS API 연동
    return {
        "success": False,
        "message": "SMS 발송 서비스 연동이 필요합니다."
    }


# ============================================
# 알림 로그 저장
# ============================================

def log_notification(
    user_id: int,
    customer_name: str,
    customer_contact: str,
    notification_type: str,  # 'email', 'kakao', 'sms'
    status: str,  # 'success', 'failed'
    message: str = None
):
    """
    알림 발송 로그 저장 (향후 DB 저장 구현)
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "customer_name": customer_name,
        "customer_contact": customer_contact,
        "type": notification_type,
        "status": status,
        "message": message
    }
    
    # TODO: DB에 저장
    print(f"[알림 로그] {log_entry}")
    
    return log_entry
