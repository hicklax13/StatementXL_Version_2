"""
Email notification service.

Provides email sending capabilities for notifications.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EmailConfig:
    """Email service configuration."""
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    from_email: str = os.getenv("FROM_EMAIL", "noreply@statementxl.com")
    from_name: str = os.getenv("FROM_NAME", "StatementXL")


class EmailService:
    """Email sending service."""
    
    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or EmailConfig()
        self._enabled = bool(self.config.smtp_user and self.config.smtp_password)
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML body content
            body_text: Plain text body (optional)
            
        Returns:
            True if sent successfully
        """
        if not self._enabled:
            logger.warning("email_disabled", to=to_email, subject=subject)
            return False
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = to_email
            
            # Add plain text and HTML parts
            if body_text:
                msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))
            
            # Send via SMTP
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_email, to_email, msg.as_string())
            
            logger.info("email_sent", to=to_email, subject=subject)
            return True
            
        except Exception as e:
            logger.error("email_failed", to=to_email, error=str(e))
            return False
    
    def send_welcome_email(self, to_email: str, name: str) -> bool:
        """Send welcome email to new user."""
        subject = "Welcome to StatementXL!"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #16a34a;">Welcome to StatementXL!</h1>
            <p>Hi {name or 'there'},</p>
            <p>Thank you for signing up! You're ready to start extracting data from financial PDFs.</p>
            <p><a href="https://app.statementxl.com" style="background: #16a34a; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Get Started</a></p>
            <p>Best,<br>The StatementXL Team</p>
        </body>
        </html>
        """
        return self.send_email(to_email, subject, body_html)
    
    def send_verification_email(self, to_email: str, verification_token: str) -> bool:
        """Send email verification link."""
        verify_url = f"https://app.statementxl.com/verify-email?token={verification_token}"
        subject = "Verify Your StatementXL Email"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #16a34a;">Verify Your Email</h1>
            <p>Welcome to StatementXL! Please verify your email by clicking the button below:</p>
            <p><a href="{verify_url}" style="background: #16a34a; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a></p>
            <p>This link expires in 24 hours.</p>
            <p>If you didn't create an account, you can ignore this email.</p>
        </body>
        </html>
        """
        return self.send_email(to_email, subject, body_html)

    def send_password_reset_email(self, to_email: str, reset_token: str) -> bool:
        """Send password reset email."""
        reset_url = f"https://app.statementxl.com/reset-password?token={reset_token}"
        subject = "Reset Your StatementXL Password"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #16a34a;">Password Reset</h1>
            <p>You requested a password reset. Click the button below:</p>
            <p><a href="{reset_url}" style="background: #16a34a; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
            <p>This link expires in 1 hour.</p>
            <p>If you didn't request this, you can ignore this email.</p>
        </body>
        </html>
        """
        return self.send_email(to_email, subject, body_html)
    
    def send_processing_complete_email(
        self,
        to_email: str,
        document_name: str,
        document_id: str,
    ) -> bool:
        """Send notification when document processing completes."""
        view_url = f"https://app.statementxl.com/documents/{document_id}"
        subject = f"Processing Complete: {document_name}"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #16a34a;">Processing Complete!</h1>
            <p>Your document <strong>{document_name}</strong> has finished processing.</p>
            <p><a href="{view_url}" style="background: #16a34a; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Results</a></p>
        </body>
        </html>
        """
        return self.send_email(to_email, subject, body_html)


# Global email service instance
email_service = EmailService()
