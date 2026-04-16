"""Email notification service for FlowBridge."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config

logger = logging.getLogger(__name__)


class EmailService:
    """Send email notifications via SMTP."""

    @staticmethod
    def send_share_notification(to_email: str, share_link: str, otp: str,
                                  filename: str, sender_name: str,
                                  message: str = '', expires_at: str = ''):
        """Send share link notification email."""
        if not Config.EMAIL_ENABLED:
            logger.debug("Email not configured, skipping notification")
            return False

        subject = f"📁 {sender_name} shared a file with you — FlowBridge"

        html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;
                    background:#0F0F1A;color:#EAEAEA;border-radius:16px;overflow:hidden;">
            <div style="background:linear-gradient(135deg,#6C63FF,#00D2FF);padding:24px;text-align:center;">
                <h1 style="margin:0;font-size:24px;color:white;">🌉 FlowBridge</h1>
                <p style="margin:4px 0 0;color:rgba(255,255,255,0.9);font-size:14px;">Secure File Transfer</p>
            </div>
            <div style="padding:32px;">
                <h2 style="color:#6C63FF;margin-top:0;">{sender_name} sent you a file</h2>
                <div style="background:#1A1A2E;border-radius:12px;padding:20px;margin:16px 0;">
                    <div style="font-size:18px;font-weight:600;">📄 {filename}</div>
                </div>
                {"<div style='background:#1A1A2E;border-radius:12px;padding:16px;margin:16px 0;border-left:4px solid #6C63FF;'><p style='margin:0;color:#A0A0B8;font-size:14px;'>Message from sender:</p><p style='margin:8px 0 0;font-size:16px;'>" + message + "</p></div>" if message else ""}
                <div style="margin:24px 0;">
                    <p style="color:#A0A0B8;font-size:14px;margin-bottom:8px;">Your OTP code:</p>
                    <div style="font-family:monospace;font-size:32px;font-weight:700;color:#00D2FF;
                                letter-spacing:8px;text-align:center;padding:16px;
                                background:#1A1A2E;border-radius:12px;">{otp}</div>
                </div>
                <a href="{share_link}" style="display:block;text-align:center;background:#6C63FF;color:white;
                   padding:14px 24px;border-radius:12px;text-decoration:none;font-weight:600;
                   font-size:16px;margin:24px 0;">
                    ⬇️ Download File
                </a>
                {"<p style='color:#6B6B80;font-size:13px;text-align:center;'>Expires: " + expires_at + "</p>" if expires_at else ""}
            </div>
            <div style="background:#1A1A2E;padding:16px;text-align:center;">
                <p style="color:#6B6B80;font-size:12px;margin:0;">
                    Sent via FlowBridge • Secure file sharing
                </p>
            </div>
        </div>
        """

        return EmailService._send(to_email, subject, html)

    @staticmethod
    def _send(to: str, subject: str, html_body: str) -> bool:
        """Send an email via SMTP."""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = f"FlowBridge <{Config.EMAIL_USER}>"
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(html_body, 'html'))

            with smtplib.SMTP(Config.EMAIL_SMTP_HOST, Config.EMAIL_SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(Config.EMAIL_USER, Config.EMAIL_PASS)
                server.sendmail(Config.EMAIL_USER, to, msg.as_string())

            logger.info(f"Email sent to {to}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
