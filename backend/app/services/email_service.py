# backend/app/services/email_service.py (已修改)
import aiosmtplib # 导入异步 SMTP 库
import ssl
import os
import random
import os # <-- 修改点：新增导入 os 模块
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication # <-- 修改点：新增导入 MIMEApplication
# ========================== START: MODIFICATION (Requirement ③) ==========================
# DESIGNER'S NOTE:
# 导入 MIMEImage 模块，这是处理邮件内嵌图片所必需的。
from email.mime.image import MIMEImage
# ========================== END: MODIFICATION (Requirement ③) ============================
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

    # ========================== START: 修改区域 (需求 ①) ==========================
    # DESIGNER'S NOTE:
    # 这是对邮件发送逻辑的彻底重构，旨在解决图片无法内嵌的问题。
    # - 邮件主体现在被构造成一个 MIMEMultipart('mixed') 容器，这是支持内容和附件混合的最佳实践。
    # - HTML 内容和其内嵌图片被包裹在一个 MIMEMultipart('related') 子容器中。
    # - 这种标准的嵌套结构能被绝大多数邮件客户端（包括QQ邮箱）正确识别。
    async def send_email(
        self, 
        receiver_email: str, 
        subject: str, 
        html_content: str, 
        attachments: list[str] = None, 
        embedded_images: list[dict] = None
    ) -> bool:
        """
        【异步改造 & 功能增强】发送邮件的核心方法。
        使用 aiosmtplib 实现非阻塞的邮件发送。
        新增对文件附件和正文内嵌图片的支持。

        :param receiver_email: 收件人邮箱。
        :param subject: 邮件主题。
        :param html_content: 邮件的 HTML 内容。
        :param attachments: 一个包含服务器上文件绝对路径的列表 (可选，作为附件)。
        :param embedded_images: 一个包含图片信息的字典列表 (可选，用于在正文显示)。
                                每个字典格式: {"path": "/path/to/img.jpg", "cid": "my_image_cid"}
        """
        sender_account = self._get_random_account()
        sender_email = sender_account["email"]
        sender_password = sender_account["password"]
        
        # 步骤 1: 创建最外层的容器，使用 'mixed' 以支持附件
        message = MIMEMultipart('mixed')
        message["Subject"] = subject
        message["From"] = f"EMinder <{sender_email}>"
        message["To"] = receiver_email
        
        # 步骤 2: 创建 'related' 容器，用于存放 HTML 和其内嵌的图片
        msg_related = MIMEMultipart('related')
        
        # 将 HTML 内容附加到 'related' 容器中
        msg_html = MIMEText(html_content, "html", "utf-8")
        msg_related.attach(msg_html)

        # 处理并附加所有内嵌图片到 'related' 容器中
        if embedded_images:
            for img_data in embedded_images:
                img_path = img_data.get("path")
                img_cid = img_data.get("cid")
                if not all([img_path, img_cid]):
                    print(f"警告: 无效的内嵌图片数据，已跳过: {img_data}")
                    continue
                
                if not os.path.exists(img_path):
                    print(f"警告: 内嵌图片文件未找到，已跳过: {img_path}")
                    continue
                    
                try:
                    with open(img_path, 'rb') as fp:
                        img_part = MIMEImage(fp.read())
                    
                    # ========================== START: MODIFICATION (Fix Image Embedding) ==========================
                    # DESIGNER'S NOTE: 这是解决图片显示问题的关键一步。
                    # 我们为每个内嵌图片添加了两个至关重要的头信息：
                    # 1. 'Content-ID': 用于在 HTML 的 <img> 标签中通过 "cid:" 引用。
                    # 2. 'Content-Disposition': 'inline' 值明确告诉邮件客户端，这不是一个普通附件，
                    #    而是应该直接在邮件正文中显示的内容。
                    img_part.add_header('Content-ID', f'<{img_cid}>')
                    img_part.add_header('Content-Disposition', 'inline', filename=os.path.basename(img_path))
                    # ========================== END: MODIFICATION (Fix Image Embedding) ============================
                    
                    msg_related.attach(img_part)
                    print(f"成功将图片 {img_path} 关联到邮件正文。")
                except Exception as e:
                    print(f"错误: 关联图片 {img_path} 时失败: {e}")

        # 步骤 3: 将包含 HTML 和图片的 'related' 容器作为一个整体，附加到最外层的 'mixed' 容器中
        message.attach(msg_related)
        
        # 步骤 4: 处理并附加所有传统文件附件到最外层的 'mixed' 容器中
        if attachments:
            for file_path in attachments:
                if not os.path.exists(file_path) or not os.path.isfile(file_path):
                    print(f"警告: 附件文件未找到，已跳过: {file_path}")
                    continue
                
                try:
                    with open(file_path, "rb") as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                    
                    # 添加必要的头信息
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    message.attach(part)
                    print(f"成功附加文件: {file_path}")
                except Exception as e:
                    print(f"错误: 附加文件 {file_path} 时失败: {e}")

        try:
            # aiosmtplib 使用与 smtplib 类似的参数，use_tls=True 对应 SMTP_SSL
            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
                port=self.smtp_port,
                username=sender_email,
                password=sender_password,
                use_tls=True, # 启用 SSL
            )
            # 如果代码执行到这里，说明邮件已成功发送
            print(f"邮件已通过 [{sender_email}] 成功发送至 [{receiver_email}]")
            return True
            
        except aiosmtplib.SMTPAuthenticationError:
            print(f"邮件发送失败：发信源 [{sender_email}] 认证失败！请检查邮箱和授权码。")
            return False
        except aiosmtplib.SMTPServerDisconnected:
            # 【核心修正逻辑】
            # aiosmtplib 中，服务器在发送后立即关闭连接会引发 SMTPServerDisconnected 错误。
            # 这与原代码中处理 (-1, b'\x00\x00\x00') 元组的逻辑目的一致。
            # 我们在此将其视为成功发送，并打印警告。
            print(f"邮件已通过 [{sender_email}] 成功发送至 [{receiver_email}]。(服务器提前关闭连接，可安全忽略)")
            return True
        except Exception as e:
            # 对于所有其他未知的、真正的错误，仍然报告失败
            print(f"邮件发送失败，发信源 [{sender_email}] -> [{receiver_email}]。错误: {e}")
            return False
    # ========================== END: 修改区域 (需求 ①) ============================

# 创建一个全局邮件服务实例
email_service = EmailService()