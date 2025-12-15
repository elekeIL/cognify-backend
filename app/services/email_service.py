"""
Production Email Service for Cognify.

Supports multiple providers:
- SMTP (default, works with any email provider)
- Console logging (development fallback)

IMPORTANT: Never log OTP values or sensitive data.
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import asyncio

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailService:
    """Production email service with SMTP support."""

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password
        self.smtp_from_email = settings.smtp_from_email
        self.smtp_from_name = settings.smtp_from_name
        self.smtp_use_tls = settings.smtp_use_tls

        self.is_configured = bool(
            self.smtp_host and
            self.smtp_port and
            self.smtp_user and
            self.smtp_password
        )

        if self.is_configured:
            logger.info(f"Email service configured with SMTP: {self.smtp_host}:{self.smtp_port}")
        else:
            logger.warning("Email service not configured - emails will be logged to console")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """
        Send an email asynchronously.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text fallback (optional)

        Returns:
            True if sent successfully
        """
        if not self.is_configured:
            # Development fallback - log to console (but NOT sensitive data)
            logger.info(f"[EMAIL] To: {to_email}, Subject: {subject}")
            logger.info(f"[EMAIL] Body preview: {text_body[:100] if text_body else html_body[:100]}...")
            return True

        try:
            # Run SMTP send in thread pool to avoid blocking
            return await asyncio.to_thread(
                self._send_smtp,
                to_email,
                subject,
                html_body,
                text_body,
            )
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def _send_smtp(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP (synchronous)."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
        msg["To"] = to_email

        # Add plain text version
        if text_body:
            part1 = MIMEText(text_body, "plain")
            msg.attach(part1)

        # Add HTML version
        part2 = MIMEText(html_body, "html")
        msg.attach(part2)

        try:
            if self.smtp_use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_from_email, to_email, msg.as_string())
            else:
                # SSL connection (port 465)
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_from_email, to_email, msg.as_string())

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed - check credentials")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False

    async def send_password_reset_otp(
        self,
        to_email: str,
        otp: str,
        user_name: str = "User",
        expiry_minutes: int = 10,
    ) -> bool:
        """
        Send password reset OTP email.

        Args:
            to_email: User's email
            otp: The OTP code (will be in email only, NOT logged)
            user_name: User's name for personalization
            expiry_minutes: OTP validity period

        Returns:
            True if sent successfully
        """
        subject = "Cognify - Password Reset Code"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Cognify</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Password Reset Request</p>
    </div>

    <div style="background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px;">
        <p style="font-size: 16px;">Hi {user_name},</p>

        <p style="font-size: 16px;">You requested to reset your password. Use the verification code below:</p>

        <div style="background: #f8f9fa; border: 2px dashed #667eea; border-radius: 8px; padding: 20px; text-align: center; margin: 25px 0;">
            <p style="font-size: 14px; color: #666; margin: 0 0 10px 0;">Your verification code:</p>
            <p style="font-size: 36px; font-weight: bold; color: #667eea; margin: 0; letter-spacing: 8px;">{otp}</p>
        </div>

        <p style="font-size: 14px; color: #666;">
            <strong>This code will expire in {expiry_minutes} minutes.</strong>
        </p>

        <p style="font-size: 14px; color: #666;">
            If you didn't request this password reset, please ignore this email or contact support if you have concerns.
        </p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 25px 0;">

        <p style="font-size: 12px; color: #999; text-align: center;">
            This is an automated message from Cognify. Please do not reply to this email.
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
Cognify - Password Reset

Hi {user_name},

You requested to reset your password. Use the verification code below:

{otp}

This code will expire in {expiry_minutes} minutes.

If you didn't request this password reset, please ignore this email or contact support if you have concerns.

- The Cognify Team
"""

        # IMPORTANT: We do NOT log the OTP value
        logger.info(f"Sending password reset OTP email to {to_email}")

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def send_password_reset_confirmation(
        self,
        to_email: str,
        user_name: str = "User",
    ) -> bool:
        """
        Send confirmation email after successful password reset.

        Args:
            to_email: User's email
            user_name: User's name

        Returns:
            True if sent successfully
        """
        subject = "Cognify - Password Changed Successfully"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Cognify</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Security Notification</p>
    </div>

    <div style="background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="font-size: 48px;">✓</span>
        </div>

        <p style="font-size: 16px;">Hi {user_name},</p>

        <p style="font-size: 16px;">Your password has been successfully changed.</p>

        <p style="font-size: 14px; color: #666;">
            For your security, all your active sessions have been logged out. You'll need to sign in again on all your devices.
        </p>

        <p style="font-size: 14px; color: #e74c3c;">
            <strong>If you didn't make this change</strong>, please contact our support team immediately.
        </p>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 25px 0;">

        <p style="font-size: 12px; color: #999; text-align: center;">
            This is an automated message from Cognify. Please do not reply to this email.
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
Cognify - Password Changed Successfully

Hi {user_name},

Your password has been successfully changed.

For your security, all your active sessions have been logged out. You'll need to sign in again on all your devices.

If you didn't make this change, please contact our support team immediately.

- The Cognify Team
"""

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
