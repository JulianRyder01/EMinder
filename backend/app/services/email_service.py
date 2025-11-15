# backend/app/services/email_service.py (已修改)
import smtplib
import ssl
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ..core.config import settings

class EmailService:
    """处理所有邮件发送的业务逻辑"""

    def __init__(self):
        self.accounts = settings.SENDER_ACCOUNTS
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        if not self.accounts:
            raise ValueError("没有可用的发信邮箱账户，请检查 .env 文件！")

    def _get_random_account(self) -> dict:
        """从账户池中随机选择一个账户用于发送，实现发信源轮换"""
        return random.choice(self.accounts)

    def send_email(self, receiver_email: str, subject: str, html_content: str) -> bool:
        """发送邮件的核心方法"""
        sender_account = self._get_random_account()
        sender_email = sender_account["email"]
        sender_password = sender_account["password"]
        
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"EMinder <{sender_email}>"
        message["To"] = receiver_email
        message.attach(MIMEText(html_content, "html"))

        try:
            # 使用 SSL 以确保连接安全
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_email, message.as_string())
            
            # 如果代码执行到这里，说明 sendmail 已经成功，邮件已被服务器接受
            print(f"邮件已通过 [{sender_email}] 成功发送至 [{receiver_email}]")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print(f"邮件发送失败：发信源 [{sender_email}] 认证失败！请检查邮箱和授权码。")
            return False
        except Exception as e:
            # 【修改点】核心修复逻辑：专门处理邮件已发送但连接关闭时产生的特定错误
            # 这个错误是 smtplib 在某些 SMTP 服务器（如QQ）上可能遇到的非标准行为
            # 它的特征是一个元组 (-1, b'\x00\x00\x00')
            if isinstance(e, tuple) and e == (-1, b'\x00\x00\x00'):
                # 因为邮件实际上已经发送成功，我们在这里将状态报告为成功
                # 并打印一条警告信息，而不是错误信息
                print(f"邮件已通过 [{sender_email}] 成功发送至 [{receiver_email}]。(连接关闭时出现非致命错误，可安全忽略)")
                return True  # 返回 True，修正状态显示问题
            else:
                # 对于所有其他未知的、真正的错误，仍然报告失败
                print(f"邮件发送失败，发信源 [{sender_email}] -> [{receiver_email}]。错误: {e}")
                return False

# 创建一个全局邮件服务实例
email_service = EmailService()