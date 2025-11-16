
# EMinder 脚本执行类模板开发规范

## 1. 概述

本文档为 EMinder 的“执行脚本并获取输出”类邮件模板提供了一套标准的开发规范。遵循本规范开发的模板将自动支持以下高级功能：

1.  **完成时发送通知**：脚本执行完毕后，自动发送一封包含执行结果的邮件。
2.  **内嵌图片**：可以将脚本生成的图片（如图表、状态截图）直接嵌入邮件正文进行展示，而非作为附件。
3.  **定时获取与时间戳**：用户可以通过 EMinder 的调度系统定时执行脚本，模板会自动在邮件中包含任务的执行时间。
4.  **文件附件**：支持将脚本生成的日志、报告等文件作为标准附件发送。

## 2. 核心设计：模板函数返回值

为了实现上述功能，模板的生成函数 (`func`) **必须**返回一个具有特定结构的 Python 字典。系统将根据此字典的键来构建最终的邮件。

### 2.1. 标准返回结构

```python
{
    "subject": "邮件主题 (必填)",
    "html": "邮件正文的 HTML 内容 (必填)",
    "attachments": [
        "/path/to/server/file1.log", 
        "/path/to/server/report.pdf"
    ],
    "embedded_images": [
        {
            "path": "/path/to/server/image1.png",
            "cid": "unique_image_id_01"
        },
        {
            "path": "/path/to/server/chart.jpg",
            "cid": "performance_chart"
        }
    ]
}
```

### 2.2. 字段详解

| 键 (`key`) | 类型 | 是否必须 | 描述 |
| :--- | :--- | :--- | :--- |
| `subject` | `str` | **是** | 邮件的主题。 |
| `html` | `str` | **是** | 邮件正文的 **HTML** 代码。您可以在这里包含执行时间、结果、日志等信息。 |
| `attachments` | `list[str]` | 否 | 一个包含**文件绝对路径**的列表。列表中的每个文件都将作为标准附件添加到邮件中。如果不需要附件，可以省略此键。 |
| `embedded_images` | `list[dict]`| 否 | 一个包含**字典**的列表，用于在邮件正文中内嵌图片。如果不需要内嵌图片，可以省略此键。 |

### 2.3. `embedded_images` 详解

`embedded_images` 列表中的每个字典都必须包含两个键：

| 键 (`key`) | 类型 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `path` | `str` | 图片在**服务器上的绝对路径**。 | `"/opt/eminder/reports/success.png"` |
| `cid` | `str` | **内容ID (Content-ID)**，这是一个在邮件中唯一标识此图片的字符串。 | `"completion_status_image"` |

**重要**: 要在邮件正文中显示这张图片，您需要在 `html` 内容中使用 `<img>` 标签，并将其 `src` 属性设置为 `cid:` 加上您定义的 `cid` 值。

**示例**:
如果 `embedded_images` 中定义了 `"cid": "completion_status_image"`，那么在 `html` 中应该这样引用：
```html
<p>任务执行完毕！状态如下：</p>
<img src="cid:completion_status_image" alt="执行状态" />
```

## 3. 功能实现指南

### 功能一：完成时发送图片提示

1.  **生成图片**：您的脚本逻辑需要先在服务器上生成或准备好一张图片（例如，`success.png` 或 `failure.png`）。
2.  **定义返回值**：在模板函数中，将该图片的路径和唯一的 `cid` 添加到 `embedded_images` 列表中。
3.  **嵌入HTML**：在返回的 `html` 字符串中，使用 `<img src="cid:your_cid">` 来引用这张图片。

### 功能二：定时获取并包含时间戳

1.  **获取时间**：在模板函数的开始和结束时，使用 `datetime` 模块记录时间戳。
2.  **格式化时间**：将时间戳格式化为易于阅读的字符串。
3.  **写入HTML**：将包含起止时间、总耗时等信息的字符串整合到返回的 `html` 内容中。

```python
import datetime

start_time = datetime.datetime.now()
# ... 执行脚本的核心逻辑 ...
end_time = datetime.datetime.now()
duration = (end_time - start_time).total_seconds()

html_content = f"""
<h4>执行详情</h4>
<ul>
    <li>开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}</li>
    <li>结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}</li>
    <li>总耗时: {duration:.2f} 秒</li>
</ul>
"""
```

### 功能三：区分内嵌图片与文件附件

这是一个核心概念，请务必遵循：

-   **要直接在邮件里显示图片** (如图表、截图)，请使用 `embedded_images` 字段。
-   **要发送可供用户下载的文件** (如 `.log`, `.txt`, `.pdf`, `.zip`)，请使用 `attachments` 字段。

这两种方式可以同时使用。

## 4. 完整示例

请参考 `customize_templates.py` 文件中的 `script_runner` (“自动运行脚本并获取日志结果”) 模板，它已根据本规范进行了全面升级，是实现所有功能的最佳实践范例。

---
```

### **文件修改**

以下是对现有项目文件的修改，以完全支持上述规范。所有修改之处都已用注释标出。

#### **1. `backend/app/services/email_service.py` (核心修改)**

为了处理内嵌图片，我们需要修改邮件服务，使其能够识别 `embedded_images` 参数，并正确构建邮件结构。

```python
# backend/app/services/email_service.py (已修改)
import aiosmtplib # 导入异步 SMTP 库
import ssl
import random
import os # <-- 修改点：新增导入 os 模块
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication # <-- 修改点：新增导入 MIMEApplication
# ========================== START: MODIFICATION ==========================
# DESIGNER'S NOTE: 导入 MIMEImage 以支持内嵌图片功能。
from email.mime.image import MIMEImage
# ========================== END: MODIFICATION ============================
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

    # ========================== START: MODIFICATION ==========================
    # DESIGNER'S NOTE:
    # 对 `send_email` 方法进行了彻底的重构以支持新规范。
    # 1. 新增 `embedded_images` 参数，用于接收内嵌图片的信息。
    # 2. 将邮件主容器 `MIMEMultipart` 的类型设置为 "related"，这是在 HTML 中内嵌图片的标准做法。
    # 3. 新增了处理 `embedded_images` 列表的逻辑，为每张图片创建 MIMEImage 部分并附加 Content-ID。
    # 4. 原有的附件处理逻辑保持不变，但现在它会在处理完内嵌图片和HTML正文之后执行。
    async def send_email(self, receiver_email: str, subject: str, html_content: str, attachments: list[str] = None, embedded_images: list[dict] = None) -> bool:
        """
        【异步改造 & 功能增强】发送邮件的核心方法。
        使用 aiosmtplib 实现非阻塞的邮件发送。
        新增对文件附件和内嵌图片的支持。

        :param receiver_email: 收件人邮箱。
        :param subject: 邮件主题。
        :param html_content: 邮件的 HTML 内容。
        :param attachments: 一个包含服务器上文件绝对路径的列表 (可选)。
        :param embedded_images: 一个字典列表，每个字典包含 "path" 和 "cid"，用于内嵌图片 (可选)。
        """
        sender_account = self._get_random_account()
        sender_email = sender_account["email"]
        sender_password = sender_account["password"]
        
        # 使用 MIMEMultipart("related") 来支持在 HTML 中内嵌图片
        message = MIMEMultipart("related")
        message["Subject"] = subject
        message["From"] = f"EMinder <{sender_email}>"
        message["To"] = receiver_email
        
        # 附加 HTML 邮件正文，它必须是 "related" 结构中的第一个部分
        message.attach(MIMEText(html_content, "html"))

        # --- 处理内嵌图片 ---
        if embedded_images:
            for img_data in embedded_images:
                img_path = img_data.get("path")
                cid = img_data.get("cid")
                
                if not all([img_path, cid]):
                    print(f"警告: 无效的内嵌图片数据，已跳过: {img_data}")
                    continue
                
                if not os.path.exists(img_path) or not os.path.isfile(img_path):
                    print(f"警告: 内嵌图片文件未找到，已跳过: {img_path}")
                    continue
                
                try:
                    with open(img_path, "rb") as f:
                        img = MIMEImage(f.read())
                    
                    # 添加 Content-ID 头，这是 HTML 中通过 src="cid:..." 引用图片的关键
                    img.add_header('Content-ID', f'<{cid}>')
                    message.attach(img)
                    print(f"成功内嵌图片: {img_path} with CID: {cid}")
                except Exception as e:
                    print(f"错误: 内嵌图片 {img_path} 时失败: {e}")
        
        # --- 处理文件附件 ---
        if attachments:
            for file_path in attachments:
                if not os.path.exists(file_path) or not os.path.isfile(file_path):
                    print(f"警告: 附件文件未找到或不是一个文件，已跳过: {file_path}")
                    continue
                
                try:
                    with open(file_path, "rb") as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                    
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    message.attach(part)
                    print(f"成功附加文件: {file_path}")
                except Exception as e:
                    print(f"错误: 附加文件 {file_path} 时失败: {e}")

        try:
            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
                port=self.smtp_port,
                username=sender_email,
                password=sender_password,
                use_tls=True,
            )
            print(f"邮件已通过 [{sender_email}] 成功发送至 [{receiver_email}]")
            return True
            
        except aiosmtplib.SMTPAuthenticationError:
            print(f"邮件发送失败：发信源 [{sender_email}] 认证失败！请检查邮箱和授权码。")
            return False
        except aiosmtplib.SMTPServerDisconnected:
            print(f"邮件已通过 [{sender_email}] 成功发送至 [{receiver_email}]。(服务器提前关闭连接，可安全忽略)")
            return True
        except Exception as e:
            print(f"邮件发送失败，发信源 [{sender_email}] -> [{receiver_email}]。错误: {e}")
            return False
    # ========================== END: MODIFICATION ============================

# 创建一个全局邮件服务实例
email_service = EmailService()
```

#### **2. `backend/app/templates/email_templates.py`**

模板管理器需要能够理解并传递新的 `embedded_images` 字段。

```python
# backend/app/templates/email_templates.py (已修改)
import functools
import datetime
import asyncio # 导入 asyncio 模块

try:
    from .customize_templates import custom_templates
except ImportError:
    custom_templates = {}
    print("提示：未找到 `customize_templates.py`，跳过加载自定义模板。")

class TemplateManager:
    """
    管理和生成所有邮件模板。
    新增了元数据(metadata)功能，以便API可以向前端提供模板信息。
    """
    
    # --- 模板元数据定义 ---
    # 这是实现前端动态化的核心。
    # 每个模板的key是其方法名去除 'get_' 和 '_template' 的部分。
    def __init__(self):
        self._templates_metadata = {
        "daily_summary": {
            "display_name": "每日游戏化总结",
            "description": "发送每日任务完成情况、等级和待办事项的总结。",
            "fields": [
                {"name": "player_name", "label": "玩家名称", "type": "text", "default": "勇士"},
                {"name": "tasks_completed", "label": "今日完成任务数", "type": "number", "default": 5},
                {"name": "level", "label": "当前等级", "type": "text", "default": "15"},
                {"name": "progress", "label": "今日进度（0-100）", "type": "number", "default": 75},
                {"name": "todo_list", "label": "明日待办 (用英文逗号,分隔)", "type": "textarea", "default": "完成报告,学习Gradio,锻炼30分钟"},
            ]
        },
        "project_update": {
            "display_name": "项目周报",
            "description": "用于发送项目进度、已完成任务和后续计划的周报。",
            "fields": [
                {"name": "project_name", "label": "项目名称", "type": "text", "default": "EMinder 开发"},
                {"name": "reporter_name", "label": "报告人", "type": "text", "default": "项目经理"},
                {"name": "completed_tasks", "label": "本周完成内容 (用英文逗号,分隔)", "type": "textarea", "default": "后端模板动态化,前端UI重构"},
                {"name": "next_week_plan", "label": "下周计划 (用英文逗号,分隔)", "type": "textarea", "default": "增加持久化存储,编写单元测试"},
            ]
        },
        "motivational_quote": {
            "display_name": "每日激励",
            "description": "每天发送一句激励人心的名言警句。",
            "fields": [
                {"name": "recipient_name", "label": "接收者昵称", "type": "text", "default": "朋友"},
                {"name": "quote_content", "label": "名言内容", "type": "textarea", "default": "The only way to do great work is to love what you do."},
                {"name": "quote_author", "label": "名言作者", "type": "text", "default": "Steve Jobs"},
            ]
        },
        "weekly_report": {
            "display_name": "通用周报（旧）",
            "description": "一个简单的通用周报模板。",
            "fields": [
                {"name": "player_name", "label": "玩家名称", "type": "text", "default": "勇士"},
                {"name": "report_content", "label": "周报内容", "type": "textarea", "default": "本周主要完成了项目A的冲刺，并规划了下周的学习计划。"},
            ]
        }
    }
        # --- 内置模板的生成函数映射 ---
        self._template_functions = {
            "daily_summary": self.get_daily_summary_template,
            "project_update": self.get_project_update_template,
            "motivational_quote": self.get_motivational_quote_template,
            "weekly_report": self.get_weekly_report_template
        }

        # =============================================================================
        # --- 合并自定义模板 ---
        # 如果 custom_templates 被成功导入，就将其内容合并到主模板列表中。
        try:
            if 'custom_templates' in locals() or 'custom_templates' in globals():
                for key, template_data in custom_templates.items():
                    self._templates_metadata[key] = template_data["meta"]
                    
                    original_func = template_data["func"]
                    
                    # 我们不再直接存储原始函数，而是创建一个新的、被包装过的函数。
                    # functools.partial 会创建一个新函数，该函数在被调用时，
                    # 会自动先调用 self._apply_base_template，并将原始函数作为第一个参数传入。
                    self._template_functions[key] = functools.partial(self._apply_base_template, original_func)
                    
                print(f"✅ 成功加载并自动包装 {len(custom_templates)} 个自定义模板！")
        except NameError:
            pass
        # =============================================================================

    def get_template_function(self, template_type: str):
        """根据模板类型获取对应的生成函数"""
        return self._template_functions.get(template_type)

    def get_all_templates_metadata(self) -> dict:
        """返回所有模板的元数据"""
        return self._templates_metadata

    # ========================== START: MODIFICATION ==========================
    # DESIGNER'S NOTE:
    # 对 `_apply_base_template` 包装器进行了关键修改，使其能够识别并传递内嵌图片信息。
    # - 原始模板函数现在可以返回一个包含 `subject`, `html`, `attachments` 和可选 `embedded_images` 键的字典。
    # - 这个包装器会将 `embedded_images` 键原样传递到最终的返回结果中，
    #   这样调度器服务就能获取到此信息并传递给邮件服务。
    async def _apply_base_template(self, original_function, data: dict) -> dict:
        """
        【异步改造 & 功能增强】执行一个原始模板函数，并将其输出用基础HTML样式进行包装。
        此函数现在是异步的，可以处理同步和异步的原始模板函数，并能传递附件和内嵌图片信息。
        """
        # 1. 检查原始函数是否为协程函数，并相应地调用它
        if asyncio.iscoroutinefunction(original_function):
            email_parts = await original_function(data)
        else:
            email_parts = original_function(data)
        
        subject = email_parts.get("subject", "无主题")
        raw_html = email_parts.get("html", "")
        attachments = email_parts.get("attachments", [])
        # 新增：获取内嵌图片列表，如果不存在则默认为空列表
        embedded_images = email_parts.get("embedded_images", [])
        
        # 2. 使用 get_base_html 进行包装，主题将作为邮件内容的标题
        final_html = self.get_base_html(raw_html, subject)
        
        # 3. 返回包含所有邮件部分的最终结果
        return {"subject": subject, "html": final_html, "attachments": attachments, "embedded_images": embedded_images}
    # ========================== END: MODIFICATION ============================
    
    @staticmethod
    def get_base_html(content: str, title: str) -> str:
        """提供一个更美观、响应式的邮件样式容器"""
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0; }}
                .wrapper {{ width: 100%; table-layout: fixed; background-color: #f4f4f4; padding: 40px 0; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); overflow: hidden; }}
                .header {{ background-color: #4CAF50; color: #ffffff; padding: 30px 25px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; font-weight: 600; }}
                .content {{ padding: 30px 25px; color: #555; }}
                .content p {{ margin: 0 0 15px; }}
                .content h4 {{ color: #333; margin-top: 25px; margin-bottom: 10px; border-left: 4px solid #4CAF50; padding-left: 10px; font-size: 18px; }}
                .button {{ background-color: #4CAF50; color: #ffffff !important; padding: 14px 25px; text-align: center; text-decoration: none; display: inline-block; border-radius: 8px; font-weight: bold; font-size: 16px; }}
                .footer {{ font-size: 12px; color: #888; text-align: center; padding: 20px 25px; background-color: #f9f9f9; }}
                .footer p {{ margin: 0; }}
                ul {{ padding-left: 20px; }}
                li {{ margin-bottom: 8px; }}
                .progress-bar {{ width: 100%; background-color: #e0e0e0; border-radius: 5px; height: 20px; overflow: hidden; }}
                .progress {{ background-color: #4CAF50; height: 100%; text-align: center; color: white; line-height: 20px; font-weight: bold; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="wrapper">
                <div class="container">
                    <div class="header">
                        <h1>{title}</h1>
                    </div>
                    <div class="content">
                        {content}
                    </div>
                    <div class="footer">
                        <p>此邮件由 <strong>EMinder</strong> 服务自动发送，请勿直接回复，因为回了我也看不到~</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    def get_confirmation_template(self, confirmation_link: str) -> dict:
        """生成订阅确认邮件"""
        subject = "【EMinder】请确认您的订阅"
        title = "欢迎订阅 EMinder！"
        content = f"""
            <p>您好！</p>
            <p>感谢您选择 EMinder 服务。请点击下方的按钮以完成订阅确认，之后您将能定期收到我们为您定制的邮件。</p>
            <br>
            <div style="text-align: center;">
                <a href="{confirmation_link}" class="button">确认订阅</a>
            </div>
            <br>
            <p>如果您没有请求此订阅，请直接忽略并删除本邮件。</p>
            <p>此致,<br>EMinder 团队</p>
        """
        return {"subject": subject, "html": self.get_base_html(content, title)}

    def get_daily_summary_template(self, data: dict) -> dict:
        """生成每日总结邮件 (新版，带进度条)"""
        today = datetime.date.today().strftime('%Y-%m-%d')
        subject = f"EMinder 每日总结 - {today}"
        title = f"🎮 {today} 游戏化总结"

        # --- 健壮性修复 2.0 ---
        # 对所有从 data 字典中获取的值进行强制类型转换和安全处理

        # 1. 安全处理 'progress' 字段 (应为整数)
        try:
            # 先转为 float 再转为 int，可以处理 "10.0" 这样的字符串
            progress = int(float(data.get("progress")))
        except (ValueError, TypeError, AttributeError):
            # 如果值是 None, '', 或其他无效格式，安全地默认为 0
            progress = 0

        # 2. 安全处理 'todo_list' 字段 (应为字符串)，这是本次修复的核心
        # 无论传入的是数字、None还是字符串，都先强制转换为字符串
        todo_list_str = str(data.get("todo_list", ""))
        todo_list_str = todo_list_str.replace(", ",",")
        todo_items = todo_list_str.split(',')
        
        # 3. 对其他所有字段也进行安全的字符串转换
        player_name = str(data.get("player_name", "玩家"))
        tasks_completed = data.get("tasks_completed", 0) # 这个字段是数字，但通常不会为空，暂时保持原样
        level = str(data.get("level", "N/A"))
        # --- 修复结束 ---

        progress_bar_html = f"""
            <div class="progress-bar">
                <div class="progress" style="width: {progress}%;">{progress}%</div>
            </div>
        """
        
        # 改进了这里的逻辑，确保只有在真正有内容时才生成列表
        todo_list_html = "<ul>" + "".join([f"<li>{item.strip()}</li>" for item in todo_items if item.strip()]) + "</ul>"
        
        content = f"""
            <p>您好, <strong>{player_name}</strong>！</p>
            <p>以下是您今天的“人生游戏”统计：</p>
            <ul>
                <li><strong>今日完成任务数:</strong> <span style="font-size: 18px; color: #4CAF50; font-weight: bold;">{tasks_completed}</span></li>
                <li><strong>当前等级:</strong> {level}</li>
            </ul>
            <h4>今日进度:</h4>
            {progress_bar_html}
            <h4>明日待办事项:</h4>
            {todo_list_html if any(item.strip() for item in todo_items) else "<p>暂无待办事项，请注意添加。</p>"}
            <p>继续努力，明天会更好！</p>
        """
        return {"subject": subject, "html": self.get_base_html(content, title)}

    def get_project_update_template(self, data: dict) -> dict:
        """【新模板】生成项目周报邮件"""
        subject = f"项目周报 - {data.get('project_name', '未命名项目')}"
        title = f"📑 {data.get('project_name', '项目')} 周报"

        completed_tasks_items = str(data.get("completed_tasks", "")).split(',')
        completed_tasks_html = "<ul>" + "".join([f"<li>{item.strip()}</li>" for item in completed_tasks_items if item.strip()]) + "</ul>"

        next_week_plan_items = str(data.get("next_week_plan", "")).split(',')
        next_week_plan_html = "<ul>" + "".join([f"<li>{item.strip()}</li>" for item in next_week_plan_items if item.strip()]) + "</ul>"

        content = f"""
            <p>您好！</p>
            <p>这是 <strong>{data.get('project_name', '项目')}</strong> 的本周进展报告。</p>
            <h4>本周完成内容:</h4>
            {completed_tasks_html if completed_tasks_items else "<p>本周无已完成任务记录。</p>"}
            <h4>下周计划:</h4>
            {next_week_plan_html if next_week_plan_items else "<p>下周计划待定。</p>"}
            <br>
            <p>报告人: {data.get('reporter_name', 'N/A')}</p>
        """
        return {"subject": subject, "html": self.get_base_html(content, title)}

    def get_motivational_quote_template(self, data: dict) -> dict:
        """【新模板】生成每日激励邮件"""
        subject = "EMinder 温馨提醒：新的一天，加油！"
        title = "✨ 每日激励"
        content = f"""
            <p>您好, {data.get("recipient_name", "朋友")}！</p>
            <p>希望这句话能给你带来力量：</p>
            <div style="padding: 20px; margin: 20px 0; border-left: 5px solid #4CAF50; background-color: #f9f9f9; font-style: italic;">
                <p style="margin: 0;">“{data.get("quote_content", "")}”</p>
                <p style="margin: 10px 0 0; text-align: right; font-weight: bold;">— {data.get("quote_author", "佚名")}</p>
            </div>
            <p>祝您拥有美好的一天！</p>
        """
        return {"subject": subject, "html": self.get_base_html(content, title)}
        
    def get_weekly_report_template(self, data: dict) -> dict:
        """【示例】生成周报邮件（旧版，保留作为示例）"""
        subject = "EMinder 周报"
        title = "本周回顾"
        content = f"""
            <p>您好, {data.get("player_name", "玩家")}！</p>
            <p>这是您的本周报告...</p>
            <p>{data.get("report_content", "")}</p>
        """
        return {"subject": subject, "html": self.get_base_html(content, title)}

# 创建一个全局模板管理器实例
template_manager = TemplateManager()

# --- 为了让 scheduler_service.py 中的旧调用方式继续工作 ---
# 我们需要动态地将注册的模板函数绑定到 template_manager 实例上
# 这样 `getattr(template_manager, f"get_{template_type}_template")` 就能找到它们
for key, func in template_manager._template_functions.items():
    # 注意：这里我们不再为函数名添加 get_ 和 _template 前缀
    # 需要同步修改 `subscribers.py` 和 `scheduler_service.py` 的调用逻辑
    setattr(template_manager, key, func)
```

#### **3. `backend/app/services/scheduler_service.py`**

调度服务中的任务执行函数需要将 `embedded_images` 数据从模板结果中提取出来，并传递给邮件服务。

```python
# backend/app/services/scheduler_service.py (已修正序列化错误)
import datetime
import asyncio
import os # <-- 新增导入
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from croniter import croniter
from ..core.config import settings
from .email_service import email_service
from ..templates.email_templates import template_manager
from ..storage.sqlite_store import store

# --- 【核心修正点】 ---
# 将执行周期性任务的逻辑移到一个独立的、顶级的函数中。
# 这样做是为了解决 APScheduler 的序列化问题。当任务被持久化到数据库时，
# APScheduler 无法序列化一个包含调度器实例的对象 (self)。
# 将其作为普通函数，就不再有关联的 self 对象，问题迎刃而解。
async def _send_recurring_emails_task():
    """【异步改造】扫描订阅者并发送相应模板的邮件。这是一个独立的函数，用于周期性任务。"""
    print(f"\n[{datetime.datetime.now()}] --- 开始执行定时邮件发送任务 ---")
    active_subscribers = store.get_active_subscribers()

    if not active_subscribers:
        print("没有活跃的订阅者，本次任务结束。")
        return

    tasks = []
    for sub in active_subscribers:
        email = sub["email"]
        template_type = sub.get("template_type", "daily_summary")

        # --- 模拟为每个用户生成动态数据 ---
        mock_data = {
            "player_name": email.split('@')[0],
            "tasks_completed": 5,
            "level": 12,
            "progress": 80,
            "todo_list": ["完成项目报告", "学习 FastAPI", "锻炼30分钟"]
        }

        template_func = getattr(template_manager, template_type, None)
        
        if template_func:
            # 检查模板函数是否为异步
            if asyncio.iscoroutinefunction(template_func):
                email_content = await template_func(mock_data)
            else:
                email_content = template_func(mock_data)

            # 创建异步发送任务
            task = email_service.send_email(
                receiver_email=email,
                subject=email_content["subject"],
                html_content=email_content["html"]
            )
            tasks.append(task)
        else:
            print(f"警告：未找到名为 '{template_type}' 的邮件模板，无法为 {email} 发送。")
    
    # 并发执行所有邮件发送任务
    if tasks:
        await asyncio.gather(*tasks)
    
    print("--- 定时邮件发送任务执行完毕 ---\n")

async def _send_custom_cron_email_task(receiver_emails: list[str], template_type: str, data: dict, custom_subject: str = None):
    """
    【异步改造 & 功能增强】根据指定的参数，向一个邮件列表发送模板邮件。
    这是一个独立的函数，用于用户自定义的周期性任务。
    增加了 custom_subject 参数和附件处理能力。
    """
    print(f"\n[{datetime.datetime.now()}] --- 开始执行自定义周期任务: 发送 '{template_type}' ---")
    
    if not receiver_emails:
        print("邮件接收者列表为空，本次任务结束。")
        return
        
    template_func = getattr(template_manager, template_type, None)
    if not template_func:
        print(f"警告：在执行自定义周期任务时，未找到模板 '{template_type}'。")
        return

    # 检查模板函数是否为异步
    if asyncio.iscoroutinefunction(template_func):
        email_content = await template_func(data)
    else:
        email_content = template_func(data)
    
    # 【修改】如果提供了自定义标题，则使用它；否则，使用模板的默认标题。
    final_subject = custom_subject if custom_subject else email_content["subject"]
    
    # ========================== START: MODIFICATION ==========================
    # DESIGNER'S NOTE: 从模板函数的返回结果中提取附件和内嵌图片。
    attachments_to_send = email_content.get("attachments", [])
    embedded_images_to_send = email_content.get("embedded_images", [])
    # ========================== END: MODIFICATION ============================
    
    print(f"准备向 {len(receiver_emails)} 位接收者发送邮件 (标题: '{final_subject}'): {', '.join(receiver_emails)}")
    
    tasks = []
    for email in receiver_emails:
        # ========================== START: MODIFICATION ==========================
        # DESIGNER'S NOTE: 将提取出的 `attachments` 和 `embedded_images` 传递给邮件服务。
        task = email_service.send_email(
            receiver_email=email,
            subject=final_subject,
            html_content=email_content["html"],
            attachments=attachments_to_send,
            embedded_images=embedded_images_to_send
        )
        # ========================== END: MODIFICATION ============================
        tasks.append(task)
        
    # 并发执行所有邮件发送任务
    if tasks:
        await asyncio.gather(*tasks)
    
    print("--- 自定义周期任务执行完毕 ---\n")


class SchedulerService:
    """管理所有后台定时任务"""
    def __init__(self):
        jobstores = {
            'default': SQLAlchemyJobStore(url=settings.DATABASE_URL)
        }
        # BackgroundScheduler 同样支持调度异步任务
        self.scheduler = BackgroundScheduler(jobstores=jobstores, timezone="Asia/Taipei")

    # 【修改点】原有的 _send_scheduled_emails 实例方法已被上面的顶级函数替代，故删除。

    # ========================== START: MODIFICATION ==========================
    # DESIGNER'S NOTE:
    # 静态方法 `send_single_email_task` 也需要升级，以处理来自模板的内嵌图片数据。
    @staticmethod
    async def send_single_email_task(receiver_email: str, template_type: str, data: dict, custom_subject: str = None, temp_file_path: str = None):
        """
        【异步改造 & 功能增强】这是一个静态方法，专门被 APScheduler 调用来执行一次性任务。
        它不依赖 SchedulerService 实例的状态，因此可以被安全地序列化。
        增加了 custom_subject 参数和对临时上传文件、内嵌图片的处理能力。
        """
        try:
            print(f"执行一次性任务：向 {receiver_email} 发送 '{template_type}' 模板邮件。")
            template_func = getattr(template_manager, template_type, None)
            if template_func:
                if asyncio.iscoroutinefunction(template_func):
                    email_content = await template_func(data)
                else:
                    email_content = template_func(data)
                
                final_subject = custom_subject if custom_subject else email_content["subject"]
                
                # 合并模板生成的附件和用户上传的临时附件
                final_attachments = email_content.get("attachments", [])
                if temp_file_path and os.path.exists(temp_file_path):
                    final_attachments.append(temp_file_path)

                # 从模板结果中提取内嵌图片
                final_embedded_images = email_content.get("embedded_images", [])
                
                await email_service.send_email(
                    receiver_email,
                    final_subject,
                    email_content["html"],
                    final_attachments,
                    embedded_images=final_embedded_images
                )
            else:
                print(f"错误：在执行一次性任务时，未找到模板 '{template_type}'。")
        finally:
            # 关键：确保任务执行完毕后，删除临时上传的文件
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    print(f"成功清理临时文件: {temp_file_path}")
                except Exception as e:
                    print(f"警告：清理临时文件 {temp_file_path} 失败: {e}")
    # ========================== END: MODIFICATION ============================
    
    def add_cron_job(self, job_id: str, name: str, cron_string: str, args: list):
        """
        【新增】添加一个由 Cron 表达式定义的周期性任务。
        """
        if not croniter.is_valid(cron_string):
            raise ValueError(f"无效的 Cron 表达式: '{cron_string}'")

        parts = cron_string.split()
        if len(parts) != 5:
            raise ValueError("Cron 表达式必须包含5个部分 (分 时 日 月 周)。")
        
        cron_kwargs = {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'day_of_week': parts[4]
        }
        
        # add_job 会自动检测到 _send_custom_cron_email_task 是协程并正确地执行它
        job = self.scheduler.add_job(
            _send_custom_cron_email_task,
            'cron',
            id=job_id,
            name=name,
            args=args,
            replace_existing=True,
            **cron_kwargs
        )
        print(f"已成功添加新的周期任务: [ID: {job.id}, Name: {name}, Cron: '{cron_string}']")
        return job
            
    def start(self):
        """添加任务并启动调度器"""
        # ========================== START: 修改区域 (需求 ②) ==========================
        # DESIGNER'S NOTE:
        # 根据用户需求，注释掉在后端启动时自动添加的“每日总结”周期性任务。
        # 用户现在可以通过前端UI来添加所有周期性任务，这样更加灵活。
        # 如果未来需要恢复此功能，只需取消下面的注释即可。
        
        # self.scheduler.add_job(
        #     _send_recurring_emails_task,
        #     'cron',
        #     id="recurring_daily_summary",
        #     name="每日总结 (周期性)",
        #     year=settings.DAILY_SUMMARY_CRON.split(' ')[4],
        #     month=settings.DAILY_SUMMARY_CRON.split(' ')[3],
        #     day=settings.DAILY_SUMMARY_CRON.split(' ')[2],
        #     hour=settings.DAILY_SUMMARY_CRON.split(' ')[1],
        #     minute=settings.DAILY_SUMMARY_CRON.split(' ')[0],
        #     replace_existing=True
        # )
        # ========================== END: 修改区域 (需求 ②) ============================
        
        self.scheduler.start()
        print(f"后台调度器已启动。所有任务将持久化到数据库: {settings.DATABASE_URL}")
        
        # 由于默认任务已移除，此打印信息也不再需要
        # print(f"每日邮件任务将按 CRON 表达式 '{settings.DAILY_SUMMARY_CRON}' 执行。")

    def shutdown(self):
        """安全关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("后台调度器已关闭。")

# 创建一个全局调度服务实例
scheduler_service = SchedulerService()
```

#### **4. `backend/app/templates/customize_templates.py` (重要示例)**

这是规范的最佳实践范例。我对 `script_runner` 模板进行了全面升级，使其完美符合新规范。

```python
"""
===================================================================================
 EMinder - 自定义邮件模板
===================================================================================

 欢迎来到 EMinder 的模板定制中心！
 在这里，你可以根据自己的需求，创建个性化的邮件模板。按照以下步骤操作，即可轻松扩展 EMinder 的功能。

 --- 如何操作 ---

 1. 定义模板元数据 (Metadata):
    - 每个模板都需要一个“元数据”字典，它告诉前端界面如何展示这个模板的输入字段。
    - 结构:
      {
          "display_name": "模板在UI上显示的名称",
          "description": "一段描述，解释这个模板的用途",
          "fields": [
              {
                  "name": "字段的内部变量名 (英文)",
                  "label": "在UI上显示的标签 (中文/英文)",
                  "type": "字段类型，支持 'text', 'textarea', 'number'",
                  "default": "该字段的默认值"
              },
              // ... 可以添加更多字段
          ]
      }

 2. 编写模板生成函数 (Template Function):
    - 每个模板都需要一个函数，用来接收用户在前端填写的数据，并生成最终的邮件内容。
    - 函数必须接收一个名为 `data` 的字典作为参数。
    - ========================== START: MODIFICATION ==========================
    - 【核心】函数必须返回一个符合新规范的字典，详见 `SCRIPT_TEMPLATE_SPECIFICATION.md`。
    - 返回结构: {
          "subject": "邮件主题",
          "html": "邮件正文HTML",
          "attachments": ["/path/to/file1.log"], // (可选) 文件附件
          "embedded_images": [{"path": "/path/to/img.png", "cid": "my_img"}] // (可选) 内嵌图片
      }
    - 【异步注意】: 如果你的模板函数需要执行 I/O 操作 (如 API 请求、运行脚本)，请将其定义为 `async def`。
    - ========================== END: MODIFICATION ============================

 3. 注册你的模板:
    - 将你创建的元数据字典和模板生成函数组合在一起，形成一个完整的模板信息。
    - 将这个模板信息添加到一个名为 `custom_templates` 的字典中，key 为模板的唯一标识符 (通常是元数据中 `name` 的蛇形命名法)。

 4. 启用模板:
    - **最重要的一步**: 前往 `email_templates.py` 文件。
    - 取消对 `from .customize_templates import custom_templates` 的注释。
    - 程序会自动将你在这里定义的所有模板合并到主模板管理器中。

 --- 规范文档 ---

 **强烈建议**在开始编写新模板前，仔细阅读 `SCRIPT_TEMPLATE_SPECIFICATION.md` 文件，
 它详细说明了所有高级功能的实现方法。
"""

# ===================================================================================
# 新增功能所需模块导入
# ===================================================================================
import os
import datetime

# 设计师注：为了实现 Markdown 到 HTML 的转换，我们推荐使用 'Markdown' 库。
# 请在您的环境中执行 `pip install Markdown` 来安装它。
# 为了保证即使在未安装此库的情况下程序也能运行，我们提供了一个简单的降级方案。
try:
    import markdown
    def convert_markdown_to_html(md_text):
        # 使用 fenced_code 和 tables 扩展来更好地支持代码块和表格
        return markdown.markdown(md_text, extensions=['fenced_code', 'tables'])
except ImportError:
    print("警告: 'Markdown' 库未安装。报告文件将以纯文本格式显示。请运行 'pip install Markdown' 以获得完整功能。")
    def convert_markdown_to_html(md_text):
        # 简单的纯文本到HTML的转换，作为降级方案
        escaped_text = md_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f"<pre style='white-space: pre-wrap; word-wrap: break-word;'>{escaped_text}</pre>"

# ===================================================================================
# 【新增】导入大模型服务
# ===================================================================================
from ..services.llm_service import llm_service


# ========================== START: MODIFICATION ==========================
# DESIGNER'S NOTE:
# 导入新创建的 ScriptRunnerService，用于执行后台脚本。
# 这是实现“自动运行脚本并获取日志结果”模板的核心依赖。
from ..services.script_runner_service import script_runner_service
# ========================== END: MODIFICATION ============================


# ===================================================================================
# 新增功能：报告文件读取 - 辅助函数
# 设计师注：创建一个共享的辅助函数来处理文件读取和错误，可以避免代码重复，提高健壮性。
# ===================================================================================
def _read_and_process_report_file(report_folder: str, report_filename: str) -> dict:
    """
    一个通用的辅助函数，用于安全地读取和处理报告文件。
    :param report_folder: 报告所在的文件夹路径 (相对于 backend 目录)。
    :param report_filename: 报告的文件名。
    :return: 一个包含处理结果的字典。
    """
    try:
        # ========================== START: 修改区域 (支持绝对路径) ==========================
        # DESIGNER'S NOTE:
        # 这里的路径解析逻辑已增强，以稳健地处理绝对路径和相对路径。
        # 1. 如果 `report_folder` 是一个绝对路径 (例如 "C:/reports" 或 "/var/logs")，它将被直接使用。
        # 2. 如果它是一个相对路径 (例如 "reports/"), 它将被解析为相对于 `backend` 项目目录的路径。
        # 这完全符合您的需求，既支持了绝对路径，又为相对路径提供了可预测的行为。
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        abs_report_folder = report_folder if os.path.isabs(report_folder) else os.path.abspath(os.path.join(backend_dir, report_folder))
        file_path = os.path.join(abs_report_folder, report_filename)
        # ========================== END: 修改区域 (支持绝对路径) ============================

        if not os.path.exists(file_path):
            error_message = f"""
                <h4>错误：报告文件未找到</h4>
                <p>系统尝试读取以下路径的文件，但文件不存在：</p>
                <p><code>{file_path}</code></p>
                <p>请检查：</p>
                <ul>
                    <li>报告文件夹名称是否正确 (支持绝对路径或相对`backend`的路径)。</li>
                    <li>报告文件名是否正确，包括后缀名。</li>
                    <li>文件是否已放置在指定文件夹中。</li>



                </ul>
            """
            return {"error": True, "subject": f"错误：报告文件 {report_filename} 未找到", "html": error_message}

        with open(file_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # 转换 Markdown 为 HTML
        html_content = convert_markdown_to_html(markdown_content)
        
        # 从文件内容中提取第一行作为邮件标题 (如果存在)
        first_line = markdown_content.split('\n', 1)[0].strip()
        # 移除 Markdown 标题标记，如 '#'
        subject_title = first_line.lstrip('#').strip() if first_line else report_filename
        
        return {
            "error": False,
            "subject": f"定时报告 - {subject_title}",
            "html": html_content
        }

    except Exception as e:
        error_message = f"""
            <h4>错误：读取报告文件时发生意外</h4>
            <p>在处理文件 <code>{report_filename}</code> 时出现了一个错误。</p>
            <p><strong>错误详情:</strong></p>
            <pre>{str(e)}</pre>
        """
        return {"error": True, "subject": f"错误：处理报告 {report_filename} 失败", "html": error_message}

# ========================== START: MODIFICATION ==========================
# ===================================================================================
# 【模板升级】: 自动运行脚本并获取日志结果 (完全符合新规范)
# DESIGNER'S NOTE:
# 此模板已根据 `SCRIPT_TEMPLATE_SPECIFICATION.md` 进行了全面升级。
# 它现在是展示所有新功能的最佳实践范例：
# - 包含完整的执行时间戳。
# - 根据脚本成功或失败，内嵌不同的状态图片。
# - 支持文件附件。
# - 保持了原有的 LLM 总结功能。
# ===================================================================================

# --- 步骤 1: 定义元数据 ---
script_runner_meta = {
    "display_name": "自动运行脚本并获取日志结果",
    "description": "在后台非阻塞地运行指定命令，捕获其输出（日志），可选地总结日志并附加结果文件，最后将包含状态图片和时间戳的报告发送到邮箱。",
    "fields": [
        {
            "name": "script_command",
            "label": "脚本启动命令",
            "type": "textarea",
            "default": "python -u /path/to/your/script.py --verbose"
        },
        {
            "name": "working_directory",
            "label": "工作目录 (绝对路径, 或相对 backend 的路径)",
            "type": "text",
            "default": "."
        },
        {
            "name": "attach_file_path",
            "label": "附加文件路径 (可选, 服务器路径)",
            "type": "text",
            "default": "/path/to/your/output.log"
        },
        {
            "name": "log_summary_prompt",
            "label": "日志总结提示词 (可选, 留空不总结)",
            "type": "textarea",
            "default": "请帮我总结以下脚本的运行日志，关注其中的关键错误信息和最终结果。"
        }
    ]
}

# --- 步骤 2: 编写模板生成函数 (异步) ---
async def get_script_runner_template(data: dict) -> dict:
    """
    执行脚本，处理日志，并生成符合新规范的、包含时间戳、状态图片和附件的邮件内容。
    """
    command = data.get('script_command', '').strip()
    work_dir = data.get('working_directory', '.').strip()
    attach_path = data.get('attach_file_path', '').strip()
    summary_prompt = data.get('log_summary_prompt', '').strip()

    if not command:
        return {
            "subject": "脚本执行失败：未提供命令",
            "html": "<h4>配置错误</h4><p>您必须在'脚本启动命令'字段中提供一个有效的命令。</p>"
        }
    
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    # 解析工作目录，支持绝对和相对路径
    abs_work_dir = work_dir if os.path.isabs(work_dir) else os.path.abspath(os.path.join(backend_dir, work_dir))

    # --- 执行脚本 ---
    exec_result = await script_runner_service.run_script(command, abs_work_dir)

    # --- 准备内嵌图片和附件 ---
    attachments_list = []
    embedded_images_list = []
    
    # 状态图片逻辑 (假设图片存在于 backend/assets/ 目录下)
    # **注意**: 请确保在您的项目中创建 `backend/assets` 目录并放入 `success.png` 和 `failure.png` 图片。
    assets_dir = os.path.join(backend_dir, 'assets')
    status_img_path = os.path.join(assets_dir, 'success.png' if exec_result['success'] else 'failure.png')
    
    if os.path.exists(status_img_path):
        embedded_images_list.append({"path": status_img_path, "cid": "status_image"})
        status_img_html = '<img src="cid:status_image" alt="status" style="height: 50px; vertical-align: middle;"/>'
    else:
        status_img_html = "" # 如果图片不存在，则不显示
        print(f"警告: 状态图片未找到: {status_img_path}")


    subject_status = "成功" if exec_result['success'] else "失败"
    subject = f"脚本执行报告: {command.split()[0]} {subject_status}"
    
    status_color = "#4CAF50" if exec_result['success'] else "#F44336"
    
    # --- 构建 HTML 报告 (包含时间戳) ---
    def escape_html(text):
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')

    stdout_html = escape_html(exec_result.get('stdout', ''))
    stderr_html = escape_html(exec_result.get('stderr', ''))
    
    html_parts = [
        f"""
        <h2>{status_img_html} <span style="color: {status_color}; vertical-align: middle;">执行{subject_status}</span></h2>
        <h4>执行详情 📊</h4>
        <ul>
            <li><strong>命令:</strong> <code>{command}</code></li>
            <li><strong>工作目录:</strong> <code>{abs_work_dir}</code></li>
            <li><strong>返回码:</strong> {exec_result.get('return_code')}</li>
            <li><strong>开始时间:</strong> {exec_result.get('start_time', 'N/A')}</li>
            <li><strong>结束时间:</strong> {exec_result.get('end_time', 'N/A')}</li>
            <li><strong>总耗时:</strong> {exec_result.get('duration_seconds', 'N/A')} 秒</li>
        </ul>
        """
    ]

    # --- (可选) LLM 总结 ---
    log_for_summary = exec_result.get('stdout') or exec_result.get('stderr')
    if summary_prompt and log_for_summary:
        full_prompt = f"{summary_prompt}\n\n--- 日志开始 ---\n{log_for_summary}\n--- 日志结束 ---"
        summary_result = await llm_service.process_text_with_deepseek(full_prompt)
        
        summary_html = ""
        if summary_result["success"]:
            summary_html = f"<p>{escape_html(summary_result['content'])}</p>"
        else:
            summary_html = f"<p style='color: red;'>总结生成失败: {escape_html(summary_result['content'])}</p>"
            
        html_parts.append(f"<h4>智能日志摘要 📝</h4>{summary_html}")

    # --- 添加日志输出 ---
    if stdout_html:
        html_parts.append(f"""
        <h4>标准输出 (stdout) 📋</h4>
        <pre style="white-space: pre-wrap; word-wrap: break-word; background-color: #f5f5f5; padding: 15px; border-radius: 8px;">{stdout_html}</pre>
        """)
    if stderr_html:
        html_parts.append(f"""
        <h4>标准错误 (stderr) ❗</h4>
        <pre style="white-space: pre-wrap; word-wrap: break-word; background-color: #fbe9e7; color: #b71c1c; padding: 15px; border-radius: 8px;">{stderr_html}</pre>
        """)

    # --- 处理文件附件 ---
    if attach_path:
        abs_attach_path = attach_path if os.path.isabs(attach_path) else os.path.join(abs_work_dir, attach_path)
        
        if os.path.exists(abs_attach_path) and os.path.isfile(abs_attach_path):
            attachments_list.append(abs_attach_path)
            html_parts.append(f"<p><i>✓ 已附加文件: {os.path.basename(attach_path)}</i></p>")
        else:
            html_parts.append(f"<p style='color: red;'><i>✗ 警告: 尝试附加的文件未找到: {abs_attach_path}</i></p>")
            
    # --- 组装并返回最终结果 ---
    return {
        "subject": subject,
        "html": "".join(html_parts),
        "attachments": attachments_list,
        "embedded_images": embedded_images_list
    }
# ===================================================================================
# ========================== END: MODIFICATION ============================

# ===================================================================================
# 【模板】: 发送本地文件报告 (保持不变)
# ===================================================================================
local_file_report_meta = {
    "display_name": "发送本地文件报告",
    "description": "直接将您从本地电脑上传的文件作为附件发送。邮件内容会自动生成一段简短的说明。",
    "fields": [
        {
            "name": "email_body_message",
            "label": "邮件正文说明 (可选)",
            "type": "textarea",
            "default": "您好，\n\n请查收附件中的文件。\n\n此致"
        }
    ]
}

def get_local_file_report_template(data: dict) -> dict:
    message = data.get("email_body_message", "请查收附件。")
    html_content = f"<p>{message.replace(os.linesep, '<br>')}</p>"
    return {
        "subject": "来自EMinder的文件分享",
        "html": html_content
    }

# ===================================================================================
# 【新增模板】: DeepSeek 大模型工作流 (保持不变)
# ===================================================================================
deepseek_workflow_meta = {
    "display_name": "DeepSeek 大模型工作流",
    "description": "将下方输入的文本发送给 DeepSeek 大模型进行处理，并将返回的结果作为邮件内容。",
    "fields": [
        {
            "name": "text_ori", # 对应您需求中留出的变量名
            "label": "原始文本 (text_ori)",
            "type": "textarea",
            "default": "请帮我将以下内容翻译成英文：\n\nEMinder 是一个灵活的、模板驱动的邮件定时发送工具包。"
        }
    ]
}

async def get_deepseek_workflow_template(data: dict) -> dict:
    """【异步改造】调用 LLM 服务处理文本，并生成邮件内容"""
    
    text_to_process = data.get('text_ori', '').strip()
    
    if not text_to_process:
        return {
            "subject": "处理失败：输入文本为空",
            "html": "<h4>错误</h4><p>您没有提供任何需要处理的文本内容。</p>"
        }
    
    # 【异步改造】调用异步的 LLM 服务
    result = await llm_service.process_text_with_deepseek(text_to_process)
    
    if result["success"]:
        subject = f"DeepSeek 模型处理结果 - {text_to_process[:20]}..."
        html_content = f"""
            <h4>原始输入文本 (Input):</h4>
            <pre style="white-space: pre-wrap; word-wrap: break-word; background-color: #f5f5f5; padding: 15px; border-radius: 8px;">{text_to_process}</pre>
            
            <h4>大模型处理结果 (Output):</h4>
            <pre style="white-space: pre-wrap; word-wrap: break-word; background-color: #e8f5e9; padding: 15px; border-radius: 8px;">{result['content']}</pre>
        """
        return {"subject": subject, "html": html_content}
    else:
        subject = "DeepSeek 大模型工作流执行失败"
        html_content = f"""
            <h4>错误：大模型处理失败</h4>
            <p>在将您的文本发送给 DeepSeek API 时发生了错误。</p>
            
            <h4>错误详情:</h4>
            <pre style="white-space: pre-wrap; word-wrap: break-word; background-color: #fbe9e7; color: #b71c1c; padding: 15px; border-radius: 8px;">{result['content']}</pre>
            
            <h4>您的原始输入:</h4>
            <pre style="white-space: pre-wrap; word-wrap: break-word; background-color: #f5f5f5; padding: 15px; border-radius: 8px;">{text_to_process}</pre>
        """
        return {"subject": subject, "html": html_content}


# ===================================================================================
# 新增模板 1: 定时报告 (指定文件) (保持不变)
# ===================================================================================
fixed_file_report_meta = {
    "display_name": "定时报告 (指定文件)",
    "description": "定时读取一个固定的、文件名不变的 Markdown 文件，并将其内容作为邮件发送。",
    "fields": [
        {
            "name": "report_folder",
            "label": "报告存放文件夹 (绝对路径, 或相对 backend 的路径)",
            "type": "text",
            "default": "reports/"
        },
        {
            "name": "report_filename",
            "label": "报告文件名 (包含后缀)",
            "type": "text",
            "default": "weekly_report.md"
        }
    ]
}

def get_fixed_file_report_template(data: dict) -> dict:
    report_folder = data.get('report_folder', 'reports/').strip()
    report_filename = data.get('report_filename', '').strip()
    if not report_filename:
        return { "subject": "配置错误：未指定报告文件名", "html": "..." }
    return _read_and_process_report_file(report_folder, report_filename)


# ===================================================================================
# 新增模板 2: 定时报告 (每日文件) (保持不变)
# ===================================================================================
daily_file_report_meta = {
    "display_name": "定时报告 (每日文件)",
    "description": "根据任务执行当天的日期，动态生成文件名并读取对应的 Markdown 报告。这对于发送每日日志非常有用。",
    "fields": [
        { "name": "report_folder", "label": "报告存放文件夹 (绝对路径, 或相对 backend 的路径)", "type": "text", "default": "reports/" },
        { "name": "filename_format", "label": "文件名日期格式 (例如 %Y%m%d.md)", "type": "text", "default": "%Y-%m-%d-log.md" }
    ]
}

def get_daily_file_report_template(data: dict) -> dict:
    report_folder = data.get('report_folder', 'reports/').strip()
    filename_format = data.get('filename_format', '%Y-%m-%d.md').strip()
    if not filename_format:
        return { "subject": "配置错误：未指定文件名格式", "html": "..." }
    try:
        today_filename = datetime.datetime.now().strftime(filename_format)
    except Exception as e:
        return { "subject": "配置错误：无效的日期格式", "html": f"..." }
    return _read_and_process_report_file(report_folder, today_filename)


# ===================================================================================
# 示例模板 1: 月度学习报告 (保持不变)
# ===================================================================================
monthly_learning_report_meta = {
    "display_name": "月度学习报告",
    "description": "为学生或团队成员生成月度学习进展报告。",
    "fields": [
        { "name": "student_name", "label": "学生姓名", "type": "text", "default": "小明" },
        { "name": "courses_completed", "label": "本月完成课程 (用英文逗号,分隔)", "type": "textarea", "default": "Python 进阶, 数据库原理" },
        { "name": "total_hours", "label": "本月总学习时长 (小时)", "type": "number", "default": 40 },
        { "name": "next_month_goals", "label": "下月学习目标 (用英文逗号,分隔)", "type": "textarea", "default": "完成机器学习项目, 学习 Docker" }
    ]
}

def get_monthly_learning_report_template(data: dict) -> dict:
    subject = f"【学习报告】{data.get('student_name', '同学')} 的月度学习报告"
    completed_courses_str = str(data.get("courses_completed", ""))
    next_month_goals_str = str(data.get("next_month_goals", ""))
    completed_courses_html = "<ul>" + "".join(
        [f"<li>{course.strip()}</li>" for course in completed_courses_str.split(',') if course.strip()]
    ) + "</ul>"
    
    next_month_goals_html = "<ul>" + "".join(
        [f"<li>{goal.strip()}</li>" for goal in next_month_goals_str.split(',') if goal.strip()]
    ) + "</ul>"

    content = f"""
        <p>你好, <strong>{data.get('student_name', '同学')}</strong>！</p>
        <p>这是你本月的学习进展总结，请查收：</p>
        <h4>本月成就 🏆</h4>
        <p>你本月共投入了 <strong>{data.get('total_hours', 0)}</strong> 小时用于学习，取得了很棒的成果！</p>
        <h4>完成的课程:</h4>
        {completed_courses_html if completed_courses_str.strip() else "<p>本月暂无完成课程记录。</p>"}
        <h4>下月目标 🚀</h4>
        <p>请继续保持势头，向着以下目标前进：</p>
        {next_month_goals_html if next_month_goals_str.strip() else "<p>下月目标待定。</p>"}
    """
    return {"subject": subject, "html": content}


# ===================================================================================
# 步骤 3: 在这里注册所有你自定义的模板
# ===================================================================================
custom_templates = {
    "local_file_report": {
        "meta": local_file_report_meta,
        "func": get_local_file_report_template
    },
    "script_runner": { # 升级后的脚本运行器
        "meta": script_runner_meta,
        "func": get_script_runner_template
    },
    "deepseek_workflow": {
        "meta": deepseek_workflow_meta,
        "func": get_deepseek_workflow_template
    },
    "fixed_file_report": {
        "meta": fixed_file_report_meta,
        "func": get_fixed_file_report_template
    },
    "daily_file_report": {
        "meta": daily_file_report_meta,
        "func": get_daily_file_report_template
    },
    "monthly_learning_report": {
        "meta": monthly_learning_report_meta,
        "func": get_monthly_learning_report_template
    },
}

```

以上就是完整的解决方案。我们创建了一份详细的开发规范 MD 文档，并对系统的核心服务和模板示例进行了必要的、健壮的升级，以完全支持您提出的所有功能需求。现在，任何开发者都可以根据这份规范轻松创建功能强大的脚本执行类模板。