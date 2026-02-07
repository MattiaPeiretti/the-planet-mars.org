import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import List

class NotificationService:
    def __init__(self):
        self.enabled = all([
            os.getenv("SMTP_HOST"),
            os.getenv("SMTP_PORT"),
            os.getenv("SMTP_USER"),
            os.getenv("SMTP_PASS")
        ])

    def notify_subscribers(self, emails: List[str], post_title: str, post_url: str):
        if not self.enabled or not emails:
            return

        msg = MIMEMultipart()
        msg['From'] = os.getenv("SMTP_FROM", "mission-control@the-planet-mars.org")
        msg['Subject'] = f"New Research: {post_title}"

        body = f"""
        New research has been published on the-planet-mars.org:
        
        {post_title}
        
        Read the full report here: {post_url}
        
        -- Mission Control
        """
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            server.sendmail(msg['From'], emails, msg.as_string())
