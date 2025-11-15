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
    - 每个模板都需要一个函数，用来接收用户在前端填写的数据，并生成最终的邮件 HTML 内容。
    - 函数必须接收一个名为 `data` 的字典作为参数。
    - 函数必须返回一个字典，包含 `subject` (邮件主题) 和 `html` (邮件内容)。

 3. 注册你的模板:
    - 将你创建的元数据字典和模板生成函数组合在一起，形成一个完整的模板信息。
    - 将这个模板信息添加到一个名为 `custom_templates` 的字典中，key 为模板的唯一标识符 (通常是元数据中 `name` 的蛇形命名法)。

 4. 启用模板:
    - **最重要的一步**: 前往 `email_templates.py` 文件。
    - 取消对 `from .customize_templates import custom_templates` 的注释。
    - 程序会自动将你在这里定义的所有模板合并到主模板管理器中。

 --- 示例 ---

 下面提供了一个完整的“月度学习报告”模板作为参考。你可以复制、修改或基于它创建全新的模板。
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

        file_path = os.path.join(report_folder, report_filename)

        if not os.path.exists(file_path):
            error_message = f"""
                <h4>错误：报告文件未找到</h4>
                <p>系统尝试读取以下路径的文件，但文件不存在：</p>
                <p><code>{file_path}</code></p>
                <p>请检查：</p>
                <ul>
                    <li>报告文件夹名称是否正确 (相对于 backend 目录)。</li>
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

# ===================================================================================
# 【新增模板】: DeepSeek 大模型工作流
# ===================================================================================

# --- 步骤 1: 定义元数据 ---
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

# --- 步骤 2: 编写模板生成函数 ---
def get_deepseek_workflow_template(data: dict) -> dict:
    """调用 LLM 服务处理文本，并生成邮件内容"""
    
    text_to_process = data.get('text_ori', '').strip()
    
    if not text_to_process:
        return {
            "subject": "处理失败：输入文本为空",
            "html": "<h4>错误</h4><p>您没有提供任何需要处理的文本内容。</p>"
        }
    
    # 调用 LLM 服务
    result = llm_service.process_text_with_deepseek(text_to_process)
    
    if result["success"]:
        # 处理成功
        subject = f"DeepSeek 模型处理结果 - {text_to_process[:20]}..."
        # 将原始文本和处理结果都包含在邮件中，方便对照
        # 使用 pre 标签保留换行和空格，保证格式
        html_content = f"""
            <h4>原始输入文本 (Input):</h4>
            <pre style="white-space: pre-wrap; word-wrap: break-word; background-color: #f5f5f5; padding: 15px; border-radius: 8px;">{text_to_process}</pre>
            
            <h4>大模型处理结果 (Output):</h4>
            <pre style="white-space: pre-wrap; word-wrap: break-word; background-color: #e8f5e9; padding: 15px; border-radius: 8px;">{result['content']}</pre>
        """
        return {"subject": subject, "html": html_content}
    else:
        # 处理失败
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
# 新增模板 1: 定时报告 (指定文件)
# 设计师注：为固定文件创建一个专用模板，界面清晰，用户不易出错。
# ===================================================================================

# --- 步骤 1: 定义元数据 ---
fixed_file_report_meta = {
    "display_name": "定时报告 (指定文件)",
    "description": "定时读取一个固定的、文件名不变的 Markdown 文件，并将其内容作为邮件发送。",
    "fields": [
        {
            "name": "report_folder",
            "label": "报告存放文件夹",
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

# --- 步骤 2: 编写模板生成函数 ---
def get_fixed_file_report_template(data: dict) -> dict:
    """生成固定文件报告的邮件内容"""
    report_folder = data.get('report_folder', 'reports/').strip()
    report_filename = data.get('report_filename', '').strip()

    if not report_filename:
        return {
            "subject": "配置错误：未指定报告文件名",
            "html": "<h4>配置错误</h4><p>您必须在'报告文件名'字段中提供一个有效的文件名。</p>"
        }

    return _read_and_process_report_file(report_folder, report_filename)


# ===================================================================================
# 新增模板 2: 定时报告 (每日文件)
# 设计师注：为动态文件创建另一个模板，专门处理基于日期的文件名，并提供清晰的格式说明。
# ===================================================================================

# --- 步骤 1: 定义元数据 ---
daily_file_report_meta = {
    "display_name": "定时报告 (每日文件)",
    "description": "根据任务执行当天的日期，动态生成文件名并读取对应的 Markdown 报告。这对于发送每日日志非常有用。",
    "fields": [
        {
            "name": "report_folder",
            "label": "报告存放文件夹",
            "type": "text",
            "default": "reports/"
        },
        {
            "name": "filename_format",
            "label": "文件名日期格式 (例如 %Y%m%d.md)",
            "type": "text",
            "default": "%Y-%m-%d-log.md"
        }
    ]
}

# --- 步骤 2: 编写模板生成函数 ---
def get_daily_file_report_template(data: dict) -> dict:
    """根据当前日期生成动态文件报告的邮件内容"""
    report_folder = data.get('report_folder', 'reports/').strip()
    filename_format = data.get('filename_format', '%Y-%m-%d.md').strip()

    if not filename_format:
        return {
            "subject": "配置错误：未指定文件名格式",
            "html": "<h4>配置错误</h4><p>您必须在'文件名日期格式'字段中提供一个有效的格式，例如 '%Y%m%d.md'。</p>"
        }

    try:
        # 获取当前日期并格式化文件名
        today_filename = datetime.datetime.now().strftime(filename_format)
    except Exception as e:
        return {
            "subject": "配置错误：无效的日期格式",
            "html": f"<h4>配置错误</h4><p>提供的文件名日期格式 '{filename_format}' 无效。</p><p>错误详情: {e}</p>"
        }
        
    return _read_and_process_report_file(report_folder, today_filename)


# ===================================================================================
# 示例模板 1: 月度学习报告 (Monthly Learning Report) - 保留源代码中已有的示例
# ===================================================================================

# --- 步骤 1: 定义元数据 ---
monthly_learning_report_meta = {
    "display_name": "月度学习报告",
    "description": "为学生或团队成员生成月度学习进展报告。",
    "fields": [
        {
            "name": "student_name",
            "label": "学生姓名",
            "type": "text",
            "default": "小明"
        },
        {
            "name": "courses_completed",
            "label": "本月完成课程 (用英文逗号,分隔)",
            "type": "textarea",
            "default": "Python 进阶, 数据库原理"
        },
        {
            "name": "total_hours",
            "label": "本月总学习时长 (小时)",
            "type": "number",
            "default": 40
        },
        {
            "name": "next_month_goals",
            "label": "下月学习目标 (用英文逗号,分隔)",
            "type": "textarea",
            "default": "完成机器学习项目, 学习 Docker"
        }
    ]
}

# --- 步骤 2: 编写模板生成函数 ---
def get_monthly_learning_report_template(data: dict) -> dict:
    """生成月度学习报告的邮件内容"""
    subject = f"【学习报告】{data.get('student_name', '同学')} 的月度学习报告"
    completed_courses_str = str(data.get("courses_completed", ""))
    next_month_goals_str = str(data.get("next_month_goals", ""))
    # 将逗号分隔的字符串转换为 HTML 列表
    completed_courses_html = "<ul>" + "".join(
        [f"<li>{course.strip()}</li>" for course in completed_courses_str.split(',') if course.strip()]
    ) + "</ul>"
    
    next_month_goals_html = "<ul>" + "".join(
        [f"<li>{goal.strip()}</li>" for goal in next_month_goals_str.split(',') if goal.strip()]
    ) + "</ul>"

    # 使用 f-string 构建邮件主体内容
    # 注意：这里没有调用 get_base_html，因为我们希望这个文件是独立的。
    # 在实际合并时，TemplateManager 会自动为它包裹上漂亮的样式。
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
        
        <p>“书山有路勤为径，学海无涯苦作舟。” 与君共勉！</p>
    """
    
    return {"subject": subject, "html": content}


# ===================================================================================
# 步骤 3: 在这里注册所有你自定义的模板
# ===================================================================================
# 字典的 `key` 是模板的唯一标识符，建议使用蛇形命名法 (snake_case)。
# 这个 `key` 将被用于 API 调用。
# 字典的 `value` 是一个包含元数据和生成函数的字典。

custom_templates = {
    "deepseek_workflow": { # 【新增】注册 DeepSeek 工作流模板
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
    # 如果你创建了更多模板，可以像下面这样继续添加:
    # "my_another_template": {
    #     "meta": my_another_template_meta,
    #     "func": get_my_another_template_func
    # }
}