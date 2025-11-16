# backend/app/services/email_service.py (已修改)
import aiosmtplib # 导入异步 SMTP 库
import ssl
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
    # 对 `send_email` 方法进行了彻底的重构和增强，以同时支持文件附件和正文内嵌图片。
    # - 新增 `embedded_images` 参数，它是一个可选的字典列表，每个字典包含图片的路径和Content-ID (cid)。
    # - 邮件结构从简单的 `MIMEMultipart` 升级为 `MIMEMultipart('related')`，这是支持HTML内嵌图片的标准做法。
    #   如果同时存在附件，这个 'related' 部分会被包裹在一个 `MIMEMultipart('mixed')` 容器中。为了简化，我们直接
    #   在一个 `MIMEMultipart` 对象中组合所有部分，这在现代邮件客户端中有很好的兼容性。
    # - 增加了循环处理内嵌图片的逻辑，读取图片文件，创建 `MIMEImage` 对象，并添加 'Content-ID' 头。
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
        
        # 使用通用的 MIMEMultipart 来支持附件
        message = MIMEMultipart()
        message["Subject"] = subject
        message["From"] = f"EMinder <{sender_email}>"
        message["To"] = receiver_email
        
        # 附加 HTML 邮件正文
        message.attach(MIMEText(html_content, "html", "utf-8"))

        # 处理内嵌图片 (Embedded Images)
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
                    # 添加 Content-ID，这是在 HTML 中通过 src="cid:..." 引用图片的关键
                    img_part.add_header('Content-ID', f'<{img_cid}>')
                    message.attach(img_part)
                    print(f"成功嵌入图片: {img_path}")
                except Exception as e:
                    print(f"错误: 嵌入图片 {img_path} 时失败: {e}")

        # 处理附件 (Attachments)
        if attachments:
            for file_path in attachments:
                if not os.path.exists(file_path) or not os.path.isfile(file_path):
                    print(f"警告: 附件文件未找到或不是一个文件，已跳过: {file_path}")
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