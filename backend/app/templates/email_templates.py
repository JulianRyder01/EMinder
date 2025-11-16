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

    # ========================== START: 修改区域 (需求 ①) ==========================
    # DESIGNER'S NOTE:
    # 对 `_apply_base_template` 包装器进行了关键修改，使其能够识别并传递附件信息。
    # - 原始模板函数现在可以返回一个包含 `subject`, `html`, 和可选 `attachments` 键的字典。
    # - 这个包装器会将 `attachments` 键原样传递到最终的返回结果中，
    #   这样调度器服务 (`scheduler_service`) 就能获取到附件列表并将其传递给邮件服务 (`email_service`)。
    async def _apply_base_template(self, original_function, data: dict) -> dict:
        """
        【异步改造 & 功能增强】执行一个原始模板函数，并将其输出用基础HTML样式进行包装。
        此函数现在是异步的，可以处理同步和异步的原始模板函数，并能传递附件信息。
        """
        # 1. 检查原始函数是否为协程函数，并相应地调用它
        if asyncio.iscoroutinefunction(original_function):
            # 如果是 async def 函数, 就 await 它
            email_parts = await original_function(data)
        else:
            # 如果是普通 def 函数, 就直接调用
            email_parts = original_function(data)
        
        subject = email_parts.get("subject", "无主题")
        raw_html = email_parts.get("html", "")
        # 新增：获取附件列表，如果不存在则默认为空列表
        attachments = email_parts.get("attachments", [])
        
        # 2. 使用 get_base_html 进行包装，主题将作为邮件内容的标题
        final_html = self.get_base_html(raw_html, subject)
        
        # 3. 返回包含主题、HTML 和附件的最终结果
        return {"subject": subject, "html": final_html, "attachments": attachments}
    # ========================== END: 修改区域 (需求 ①) ============================
    
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