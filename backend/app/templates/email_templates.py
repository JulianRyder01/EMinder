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
    
    def __init__(self):
        # ========================== START: MODIFICATION (Decisive Async Fix) ==========================
        # DESIGNER'S NOTE:
        # 这是解决 TypeError 的核心重构。我们不再分开处理内置模板和自定义模板，
        # 而是将它们全部统一到一个数据结构中，然后用一个循环来确保每一个模板
        # 都被我们的异步包装器 `_apply_base_template` 正确地包装。
        # 这消除了之前存在的逻辑不一致性，保证了任何对 template_func 的调用都返回一个可等待对象。

        # 步骤 1: 将所有模板的元数据和原始函数集中定义。
        all_templates_definitions = {
            "daily_summary": {
                "meta": {
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
                "func": self.get_daily_summary_template
            },
            "project_update": {
                "meta": {
                    "display_name": "项目周报",
                    "description": "用于发送项目进度、已完成任务和后续计划的周报。",
                    "fields": [
                        {"name": "project_name", "label": "项目名称", "type": "text", "default": "EMinder 开发"},
                        {"name": "reporter_name", "label": "报告人", "type": "text", "default": "项目经理"},
                        {"name": "completed_tasks", "label": "本周完成内容 (用英文逗号,分隔)", "type": "textarea", "default": "后端模板动态化,前端UI重构"},
                        {"name": "next_week_plan", "label": "下周计划 (用英文逗号,分隔)", "type": "textarea", "default": "增加持久化存储,编写单元测试"},
                    ]
                },
                "func": self.get_project_update_template
            },
            "motivational_quote": {
                "meta": {
                    "display_name": "每日激励",
                    "description": "每天发送一句激励人心的名言警句。",
                    "fields": [
                        {"name": "recipient_name", "label": "接收者昵称", "type": "text", "default": "朋友"},
                        {"name": "quote_content", "label": "名言内容", "type": "textarea", "default": "The only way to do great work is to love what you do."},
                        {"name": "quote_author", "label": "名言作者", "type": "text", "default": "Steve Jobs"},
                    ]
                },
                "func": self.get_motivational_quote_template
            },
            "weekly_report": {
                "meta": {
                    "display_name": "通用周报（旧）",
                    "description": "一个简单的通用周报模板。",
                    "fields": [
                        {"name": "player_name", "label": "玩家名称", "type": "text", "default": "勇士"},
                        {"name": "report_content", "label": "周报内容", "type": "textarea", "default": "本周主要完成了项目A的冲刺，并规划了下周的学习计划。"},
                    ]
                },
                "func": self.get_weekly_report_template
            }
        }

        # 步骤 2: 将自定义模板合并到主定义列表中。
        # 如果 `custom_templates` 中有与内置模板同名的 key，它将会覆盖内置模板。
        all_templates_definitions.update(custom_templates)
        
        # 步骤 3: 初始化用于存储最终结果的实例变量。
        self._templates_metadata = {}
        self._template_functions = {}

        # 步骤 4: 遍历所有模板定义，进行统一的异步包装。
        for key, definition in all_templates_definitions.items():
            meta = definition.get("meta")
            original_func = definition.get("func")

            if not (meta and original_func):
                print(f"警告：模板 '{key}' 的定义不完整，已跳过。")
                continue

            # 存储元数据
            self._templates_metadata[key] = meta
            
            # 创建一个被异步包装器包裹的新函数
            wrapped_func = functools.partial(self._apply_base_template, original_func)
            
            # 存储这个保证可 await 的函数
            self._template_functions[key] = wrapped_func
            
            # 同时将其设置为实例的一个属性，以便 `getattr` 可以直接调用
            setattr(self, key, wrapped_func)

        if custom_templates:
            print(f"✅ 成功加载并统一包装了 {len(custom_templates)} 个自定义模板！")
        # ========================== END: MODIFICATION (Decisive Async Fix) ============================


    def get_template_function(self, template_type: str):
        """根据模板类型获取对应的生成函数"""
        return self._template_functions.get(template_type)

    def get_all_templates_metadata(self) -> dict:
        """返回所有模板的元数据"""
        return self._templates_metadata

    async def _apply_base_template(self, original_function, data: dict) -> dict:
        """
        【异步改造 & 功能增强】执行一个原始模板函数，并将其输出用基础HTML样式进行包装。
        此函数现在是异步的，可以处理同步和异步的原始模板函数，并能传递附件和内嵌图片信息。
        """
        # 1. 检查原始函数是否为协程函数，并相应地调用它
        if asyncio.iscoroutinefunction(original_function):
            # 如果是 async def 函数, 就 await 它
            email_parts = await original_function(data)
        else:
            # 如果是普通 def 函数, 就直接调用
            email_parts = original_function(data)
        
        # ========================== START: MODIFICATION (Fix Skip Email) ==========================
        # DESIGNER'S NOTE: 
        # 关键修正：如果模板返回了 abort_sending 标志，直接透传该字典。
        # 不要继续往下执行 get_base_html，否则会生成一个“空壳”HTML并在没有内容的情况下发送。
        if email_parts.get("abort_sending"):
            return {"abort_sending": True}
        # ========================== END: MODIFICATION (Fix Skip Email) ============================

        subject = email_parts.get("subject", "无主题")
        raw_html = email_parts.get("html", "")
        # 新增：获取附件列表，如果不存在则默认为空列表
        attachments = email_parts.get("attachments", [])
        # 新增：获取内嵌图片列表，如果不存在则默认为空列表
        embedded_images = email_parts.get("embedded_images", [])
        
        # 2. 使用 get_base_html 进行包装，主题将作为邮件内容的标题
        final_html = self.get_base_html(raw_html, subject)
        
        # 3. 返回包含所有部分的最终结果
        return {
            "subject": subject, 
            "html": final_html, 
            "attachments": attachments, 
            "embedded_images": embedded_images
        }
    # ========================== END: MODIFICATION (Requirements ①, ③) ============================
    
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
                /* ========================== START: MODIFICATION ========================== */
                /* DESIGNER'S NOTE: 为内容区域添加强制换行样式，防止长文本溢出。 */
                .content {{ padding: 30px 25px; color: #555; word-wrap: break-word; word-break: break-word; }}
                /* ========================== END: MODIFICATION ============================ */
                .content p {{ margin: 0 0 15px; }}
                .content h4 {{ color: #333; margin-top: 25px; margin-bottom: 10px; border-left: 4px solid #4CAF50; padding-left: 10px; font-size: 18px; }}
                .button {{ background-color: #4CAF50; color: #ffffff !important; padding: 14px 25px; text-align: center; text-decoration: none; display: inline-block; border-radius: 8px; font-weight: bold; font-size: 16px; }}
                .footer {{ font-size: 12px; color: #888; text-align: center; padding: 20px 25px; background-color: #f9f9f9; }}
                .footer p {{ margin: 0; }}
                ul {{ padding-left: 20px; }}
                li {{ margin-bottom: 8px; }}
                .progress-bar {{ width: 100%; background-color: #e0e0e0; border-radius: 5px; height: 20px; overflow: hidden; }}
                .progress {{ background-color: #4CAF50; height: 100%; text-align: center; color: white; line-height: 20px; font-weight: bold; border-radius: 5px; }}
                /* ========================== START: MODIFICATION ========================== */
                /* DESIGNER'S NOTE: 
                   为 <pre> 标签添加全局样式，确保代码块和长文本能够自动换行，
                   这对于显示日志或AI生成的长字符串至关重要。*/
                pre {{
                    white-space: pre-wrap;   /* 保留空白符序列，但允许正常换行 */
                    word-wrap: break-word;   /* 在长单词或URL内部进行换行 */
                }}
                /* ========================== END: MODIFICATION ============================ */
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
        # 注意：这个模板是直接调用的，所以它自己要包装HTML
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
        # 只返回核心内容，包装器会处理外层样式
        return {"subject": subject, "html": content}

    def get_project_update_template(self, data: dict) -> dict:
        """【新模板】生成项目周报邮件"""
        subject = f"项目周报 - {data.get('project_name', '未命名项目')}"
        
        completed_tasks_items = str(data.get("completed_tasks", "")).split(',')
        completed_tasks_html = "<ul>" + "".join([f"<li>{item.strip()}</li>" for item in completed_tasks_items if item.strip()]) + "</ul>"

        next_week_plan_items = str(data.get("next_week_plan", "")).split(',')
        next_week_plan_html = "<ul>" + "".join([f"<li>{item.strip()}</li>" for item in next_week_plan_items if item.strip()]) + "</ul>"

        content = f"""
            <p>您好！</p>
            <p>这是 <strong>{data.get('project_name', '项目')}</strong> 的本周进展报告。</p>
            <h4>本周完成内容:</h4>
            {completed_tasks_html if any(s.strip() for s in completed_tasks_items) else "<p>本周无已完成任务记录。</p>"}
            <h4>下周计划:</h4>
            {next_week_plan_html if any(s.strip() for s in next_week_plan_items) else "<p>下周计划待定。</p>"}
            <br>
            <p>报告人: {data.get('reporter_name', 'N/A')}</p>
        """
        return {"subject": subject, "html": content}

    def get_motivational_quote_template(self, data: dict) -> dict:
        """【新模板】生成每日激励邮件"""
        subject = "EMinder 温馨提醒：新的一天，加油！"
        content = f"""
            <p>您好, {data.get("recipient_name", "朋友")}！</p>
            <p>希望这句话能给你带来力量：</p>
            <div style="padding: 20px; margin: 20px 0; border-left: 5px solid #4CAF50; background-color: #f9f9f9; font-style: italic;">
                <p style="margin: 0;">“{data.get("quote_content", "")}”</p>
                <p style="margin: 10px 0 0; text-align: right; font-weight: bold;">— {data.get("quote_author", "佚名")}</p>
            </div>
            <p>祝您拥有美好的一天！</p>
        """
        return {"subject": subject, "html": content}
        
    def get_weekly_report_template(self, data: dict) -> dict:
        """【示例】生成周报邮件（旧版，保留作为示例）"""
        subject = "EMinder 周报"
        content = f"""
            <p>您好, {data.get("player_name", "玩家")}！</p>
            <p>这是您的本周报告...</p>
            <p>{data.get("report_content", "")}</p>
        """
        return {"subject": subject, "html": content}

# 创建一个全局模板管理器实例
template_manager = TemplateManager()