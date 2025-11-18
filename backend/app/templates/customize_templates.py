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
    - 【重要】函数必须返回一个符合开发规范的字典。详情请参阅 `CUSTOM_TEMPLATE_GUIDE.md`。
      - 必须包含 `subject` (邮件主题) 和 `html` (邮件内容)。
      - 可选包含 `attachments` (文件附件路径列表) 和 `embedded_images` (内嵌图片信息列表)。
    - 【异步注意】: 如果你的模板函数需要执行 I/O 操作 (如 API 请求、运行脚本)，请将其定义为 `async def`。

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
import re
import glob
import shutil
from ..core.config import settings

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


# ========================== START: 修改区域 (需求 ①) ==========================
# DESIGNER'S NOTE:
# 导入新创建的 ScriptRunnerService，用于执行后台脚本。
# 这是实现“自动运行脚本并获取日志结果”模板的核心依赖。
from ..services.script_runner_service import script_runner_service
# ========================== END: 修改区域 (需求 ①) ============================


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

# ========================== START: 修改区域 (需求 ①) ==========================
# ===================================================================================

# --- 步骤 0: 内部辅助函数 ---

def _create_default_daily_template(filepath: str, plan_items_from_yesterday: list = None):
    """
    在一个指定的路径创建一个默认的每日总结Markdown模板文件。
    新增功能：可以接收昨天的计划并自动填充到今天的待办中，并加入了“随手记”板块。
    """
    # ========================== START: MODIFICATION (模板简化) ==========================
    template_header = f"# {datetime.date.today().strftime('%Y-%m-%d')} 每日总结与明日计划\n\n"
    
    # --- 动态构建 "今日事项" ---
    today_items_section = "## 📝 今日事项\n\n"
    if plan_items_from_yesterday:
        for item in plan_items_from_yesterday:
            # 确保迁移过来的事项是未完成状态
            today_items_section += f"- [ ] {item}\n"
    else:
        # 如果没有昨日计划，提供一个空项供用户填写
        today_items_section += "- [ ] \n"
    
    # --- 新增 "随手记" 板块 ---
    notes_section = "\n## ✍️ 随手记\n\n- \n"

    template_plan = "\n## 🚀 明日计划\n\n- \n"
    
    final_content = template_header + today_items_section + notes_section + template_plan
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
        print(f"成功创建了新的每日模板: {filepath}")
    except Exception as e:
        print(f"错误：创建默认模板文件失败: {e}")

def _parse_daily_summary(content: str) -> dict:
    """
    解析每日总结Markdown文件的内容。
    :param content: Markdown文件的字符串内容。
    :return: 包含已办、待办、完成度、明日计划和随手记的字典。
    """
    # 使用正则表达式安全地提取各个部分的内容
    today_items_content_match = re.search(r'##\s*📝\s*今日事项\s*([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)
    notes_content_match = re.search(r'##\s*✍️\s*随手记\s*([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)
    plan_content_match = re.search(r'##\s*🚀\s*明日计划\s*([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)

    today_items_content = today_items_content_match.group(1).strip() if today_items_content_match else ""
    notes_content = notes_content_match.group(1).strip() if notes_content_match else ""
    plan_content = plan_content_match.group(1).strip() if plan_content_match else ""

    # 提取 "今日事项" 中的已完成和未完成项
    done_items = [item.strip() for item in re.findall(r'-\s*\[x\]\s*(.+)', today_items_content, re.IGNORECASE)]
    todo_items = [item.strip() for item in re.findall(r'-\s*\[ \]\s*(.+)', today_items_content)]

    # 提取 "随手记" 和 "明日计划" 的列表项
    notes_items = [line.strip('- ').strip() for line in notes_content.split('\n') if line.strip() and line.strip().startswith('- ')]
    plan_items = [line.strip('- ').strip() for line in plan_content.split('\n') if line.strip() and line.strip().startswith('- ')]

    total_tasks = len(done_items) + len(todo_items)
    progress = (len(done_items) / total_tasks * 100) if total_tasks > 0 else 0

    return {
        "done": done_items,
        "todo": todo_items,
        "notes": notes_items,
        "plan": plan_items,
        "total": total_tasks,
        "progress": round(progress)
    }

async def _generate_period_summary(period_days: int, period_name: str) -> dict:
    """
    一个通用的函数，用于生成周度或月度总结报告。
    :param period_days: 7 for weekly, 30 for monthly.
    :param period_name: "周度" or "月度".
    :return: A dictionary for the email template.
    """
    # 1. 检查并获取路径
    if not settings.DAILY_SUMMARY_PATH:
        return {
            "subject": f"配置错误：无法生成{period_name}总结",
            "html": "<h4>配置错误</h4><p>管理员尚未在 <code>.env</code> 文件中配置 <code>DAILY_SUMMARY_PATH</code> 变量。</p>"
        }
    
    history_path = os.path.join(settings.DAILY_SUMMARY_PATH, "history")
    if not os.path.isdir(history_path):
        return {
            "subject": f"{period_name}总结：无历史数据",
            "html": f"<h4>无数据</h4><p>在路径 <code>{history_path}</code> 中未找到历史总结文件夹。请先使用“每日总结”模板生成一些数据。</p>"
        }

    # 2. 筛选时间范围内的历史文件
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=period_days)
    relevant_files = []
    # 修改glob以匹配新的归档文件名 (YYYY-MM-DD.md)
    for filepath in glob.glob(os.path.join(history_path, "*.md")):
        filename = os.path.basename(filepath)
        try:
            # 文件名现在就是日期
            file_date_str = os.path.splitext(filename)[0]
            file_date = datetime.datetime.strptime(file_date_str, "%Y-%m-%d").date()
            if start_date <= file_date < today: # Exclude today
                relevant_files.append((file_date, filepath))
        except (ValueError, IndexError):
            continue
    
    if not relevant_files:
        return {
            "subject": f"{period_name}总结：范围内无历史数据",
            "html": f"<h4>无数据</h4><p>在过去 {period_days} 天内没有找到任何有效的每日总结历史记录。</p>"
        }

    # 3. 读取并聚合数据
    relevant_files.sort() # 按日期排序
    total_done_tasks = 0
    total_tasks_count = 0
    progress_per_day = []
    
    for file_date, filepath in relevant_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            parsed_data = _parse_daily_summary(content)
            total_done_tasks += len(parsed_data["done"])
            total_tasks_count += parsed_data["total"]
            progress_per_day.append({
                "date": file_date.strftime("%m-%d"),
                "progress": parsed_data["progress"]
            })
    
    overall_progress = (total_done_tasks / total_tasks_count * 100) if total_tasks_count > 0 else 0

    # 4. 构建AI Prompt
    progress_str = ", ".join([f"{p['date']}: {p['progress']}%" for p in progress_per_day])
    prompt = f"""
请你扮演一位专业的个人成长教练和数据分析师。我将为你提供过去{period_days}天内我的每日任务完成情况数据。请你基于这些数据，为我生成一份详细的{period_name}总结报告。

报告需要包含以下几个部分：
1.  **数据概览**: 清晰地总结核心数据指标。
2.  **多维度分析**:
    *   **一致性分析**: 我是否每天都在坚持？是否有中断？
    *   **效率趋势**: 我的完成率是上升、下降还是保持平稳？
    *   **优点识别**: 根据数据，我做得好的地方是什么？
    *   **潜在问题**: 是否有迹象表明我可能在某些方面遇到了困难？
3.  **鼓励与建议**: 给出具体、可执行的建议，并用积极、激励人心的语气鼓励我继续前进。

**输入数据:**
- **时间范围**: 过去 {period_days} 天
- **总计划任务数**: {total_tasks_count}
- **总完成任务数**: {total_done_tasks}
- **总体完成率**: {overall_progress:.1f}%
- **每日进度列表 (日期: 完成率)**: {progress_str}
- **有效总结天数**: {len(relevant_files)} / {period_days}

请直接生成Markdown格式的报告正文，无需客套话。
"""
    
    # 5. 调用AI并构建邮件
    ai_result = await llm_service.generate_text(prompt)
    # ========================== END: MODIFICATION ============================
    ai_analysis_html = convert_markdown_to_html(ai_result['content']) if ai_result['success'] else f"<p>AI分析失败: {ai_result['content']}</p>"

    subject = f"您的专属{period_name}总结报告 ({start_date.strftime('%Y-%m-%d')} - {(today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')})"
    html_content = f"""
        <h4>数据概览</h4>
        <ul>
            <li><strong>时间范围:</strong> {start_date.strftime('%Y-%m-%d')} 至 {(today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')}</li>
            <li><strong>有效天数:</strong> {len(relevant_files)} / {period_days} 天</li>
            <li><strong>总计划任务:</strong> {total_tasks_count} 项</li>
            <li><strong>总完成任务:</strong> {total_done_tasks} 项</li>
            <li><strong>总体完成率:</strong> <span style="font-size: 18px; color: #4CAF50; font-weight: bold;">{overall_progress:.1f}%</span></li>
        </ul>
        <h4>AI智能分析与建议</h4>
        {ai_analysis_html}
    """
    
    return {"subject": subject, "html": html_content}
# ========================== END: MODIFICATION (需求 ②) ============================


# --- 步骤 1: 【新模板】每日总结与明日计划 ---
daily_summary_plan_meta = {
    "display_name": "每日总结与明日计划 (自动)",
    "description": "自动读取指定本地文件夹中的当日Markdown文件，进行总结和AI分析，然后发送报告邮件，并存档。",
    "fields": [] # 这是一个全自动模板，不需要用户在UI上填写任何字段。
}

# ========================== START: MODIFICATION (需求 ②) ==========================
async def generate_daily_summary_plan_template(data: dict) -> dict:
    """
    (已重构) 实现每日总结与明日计划的核心逻辑。
    - 首次运行: 初始化今日文件，并迁移昨日计划。
    - 后续运行: 总结今日进度，并备份，但不删除源文件。
    """
    # 1. 检查路径配置
    if not settings.DAILY_SUMMARY_PATH:
        return {
            "subject": "配置错误：无法执行每日总结",
            "html": "<h4>配置错误</h4><p>管理员尚未在 <code>.env</code> 文件中配置 <code>DAILY_SUMMARY_PATH</code> 变量。请配置该变量指向您的总结文件夹。</p>"
        }
    
    base_path = settings.DAILY_SUMMARY_PATH
    history_path = os.path.join(base_path, "history")
    os.makedirs(history_path, exist_ok=True)

    # 2. 准备路径并查找昨天的计划 (核心新增逻辑)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    today_filename = f"{today.strftime('%Y-%m-%d')}.md"
    yesterday_filename = f"{yesterday.strftime('%Y-%m-%d')}.md"
    
    today_filepath = os.path.join(base_path, today_filename)
    yesterday_filepath = os.path.join(base_path, yesterday_filename)

    # 2. 判断是首次运行还是后续运行
    if not os.path.exists(today_filepath):
        # --- 场景A: 当天首次运行 ---
        yesterdays_plan = []
        
        # 2a. 查找并处理昨日文件
        if os.path.exists(yesterday_filepath):
            try:
                with open(yesterday_filepath, 'r', encoding='utf-8') as f:
                    y_content = f.read()
                
                # 从昨日文件中提取“明日计划”
                yesterdays_plan = _parse_daily_summary(y_content).get("plan", [])
                
                # 归档昨日文件
                archive_path = os.path.join(history_path, yesterday_filename)
                shutil.move(yesterday_filepath, archive_path) # 使用 move 实现归档并删除
                print(f"成功归档昨日文件到: {archive_path}")

            except Exception as e:
                print(f"处理昨日文件 {yesterday_filepath} 时出错: {e}")
        
        # 2b. 创建今日文件，并迁移计划
        _create_default_daily_template(today_filepath, plan_items_from_yesterday=yesterdays_plan)
        
        # 2c. 发送初始化邮件
        email_html = f"<h4>今日总结已初始化！</h4><p>系统已为您创建了今天的模板文件：</p><p><code>{today_filepath}</code></p>"
        if yesterdays_plan:
            email_html += "<p>并已将您昨天的“明日计划”自动迁移为今天的待办事项。请开始新的一天吧！</p>"
        else:
            email_html += "<p>请立即填写今日的计划与总结吧！</p>"
            
        return { "subject": f"✅ {today.strftime('%Y-%m-%d')} 新的一天，计划已就绪！", "html": email_html }
            
    else:
        # --- 场景B: 当天后续运行 ---
        
        # 3a. 读取并解析今天的现有文件
        with open(today_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        parsed_data = _parse_daily_summary(content)
        
        # 3b. 将当前内容归档到history，但不删除源文件
        history_summary_filepath = os.path.join(history_path, f"{today.strftime('%Y-%m-%d')}_summary_{datetime.datetime.now().strftime('%H%M%S')}.md")
        try:
            shutil.copy(today_filepath, history_summary_filepath)
            print(f"成功将当前总结备份到: {history_summary_filepath}")
        except Exception as e:
             print(f"备份文件到history时出错: {e}")
            
        # 3c. 构建AI Prompt
        prompt = f"""
请你扮演我的私人助理，以积极、鼓励的语气，为我生成一份今日的总结报告。

**我的今日数据:**
- **已完成事项**: {', '.join(parsed_data['done']) if parsed_data['done'] else '无'}
- **未完成事项**: {', '.join(parsed_data['todo']) if parsed_data['todo'] else '无'}
- **今日任务完成率**: {parsed_data['progress']}%
- **我的随手记**: {', '.join(parsed_data['notes']) if parsed_data['notes'] else '无'}
- **我的明日计划**: {', '.join(parsed_data['plan']) if parsed_data['plan'] else '未计划'}

**你的任务:**
1.  **总结表现**: 简要总结我今天的表现。
2.  **给予鼓励**: 针对我的完成情况（无论好坏）给予具体、真诚的鼓励。
3.  **提出建议**: 如果有未完成的事项，可以温和地提醒。如果对明日计划有建议，也可以提出来。
4.  **结尾祝福**: 最后用一句激励人心的话结尾。

请直接生成报告正文，使用Markdown格式，语言亲切自然。
"""
        
        # 3d. 调用AI并构建邮件
        ai_result = await llm_service.generate_text(prompt)
        ai_analysis_html = convert_markdown_to_html(ai_result['content']) if ai_result['success'] else f"<p>AI分析失败: {ai_result['content']}</p>"

        subject = f"你的专属每日总结报告 - {today.strftime('%Y-%m-%d')}"
        html_content = f"""
            <h4>今日任务完成度: {parsed_data['progress']}%</h4>
            <div style="width: 100%; background-color: #e0e0e0; border-radius: 5px; height: 20px; overflow: hidden;">
                <div style="background-color: #4CAF50; width: {parsed_data['progress']}%; height: 100%; text-align: center; color: white; line-height: 20px; font-weight: bold; border-radius: 5px;">{parsed_data['progress']}%</div>
            </div>

            <h4>✅ 已办清单</h4>
            <ul>{''.join(f'<li>{item}</li>' for item in parsed_data['done']) if parsed_data['done'] else '<li>今日暂无完成事项</li>'}</ul>

            <h4>📝 待办清单</h4>
            <ul>{''.join(f'<li>{item}</li>' for item in parsed_data['todo']) if parsed_data['todo'] else '<li>太棒了！没有待办遗留！</li>'}</ul>
            
            <h4>✍️ 随手记</h4>
            <ul>{''.join(f'<li>{item}</li>' for item in parsed_data['notes']) if parsed_data['notes'] else '<li>暂无随手记录。</li>'}</ul>

            <h4>🚀 明日计划</h4>
            <ul>{''.join(f'<li>{item}</li>' for item in parsed_data['plan']) if parsed_data['plan'] else '<li>暂未规划明日事项。</li>'}</ul>

            <h4>💡 AI 智能助理分析</h4>
            {ai_analysis_html}
        """
        
        return {"subject": subject, "html": html_content}
# ========================== END: MODIFICATION (需求 ②) ============================


# --- 步骤 2: 【新模板】周度总结与计划 ---
weekly_summary_plan_meta = {
    "display_name": "周度总结报告 (自动)",
    "description": "自动读取过去7天的每日总结历史，进行聚合分析，并通过AI生成周报。",
    "fields": []
}

async def generate_weekly_summary_plan_template(data: dict) -> dict:
    """生成周度总结报告。"""
    return await _generate_period_summary(period_days=7, period_name="周度")


# --- 步骤 3: 【新模板】月度总结与计划 ---
monthly_summary_plan_meta = {
    "display_name": "月度总结报告 (自动)",
    "description": "自动读取过去30天的每日总结历史，进行聚合分析，并通过AI生成月报。",
    "fields": []
}

async def generate_monthly_summary_plan_template(data: dict) -> dict:
    """生成月度总结报告。"""
    return await _generate_period_summary(period_days=30, period_name="月度")

# ===================================================================================
# END OF MODIFICATION
# ===================================================================================

# ===================================================================================
# 【模板】: 发送本地文件报告
# ===================================================================================
local_file_report_meta = {
    "display_name": "发送本地文件报告",
    "description": "直接将您从本地电脑上传的文件作为附件发送。邮件内容会自动生成一段简短的说明。",
    "fields": [
        # 这个模板故意将字段留空，因为核心交互是文件上传组件，它在前端UI中是独立于模板字段的。
        # 我们可以在这里加一个说明字段，让用户体验更好。
        {
            "name": "email_body_message",
            "label": "邮件正文说明 (可选)",
            "type": "textarea",
            "default": "您好，\n\n请查收附件中的文件。\n\n此致"
        }
    ]
}

# --- 步骤 2: 编写模板生成函数 ---
def get_local_file_report_template(data: dict) -> dict:
    """
    为本地上传的文件生成一个简单的邮件包装。
    实际的附件处理由API层负责。
    """
    message = data.get("email_body_message", "请查收附件。")
    # 将纯文本转换为带换行的HTML
    html_content = f"<p>{message.replace(os.linesep, '<br>')}</p>"

    return {
        "subject": "来自EMinder的文件分享",
        "html": html_content
        # 注意：这里不返回 "attachments" 键，因为附件是从API直接处理的
    }
# ========================== END: 修改区域 (需求 ①) ============================


# ===================================================================================
# 【模板】: 自动运行脚本并获取日志结果 (保持不变)
# ===================================================================================
script_runner_meta = {
    "display_name": "自动运行脚本并获取日志结果",
    "description": "在后台运行命令，捕获其输出，并将脚本生成的所有指定文件作为附件发送。",
    "fields": [
        {
            "name": "email_body_message",
            "label": "邮件说明与附言 (可选)",
            "type": "textarea",
            "default": "您好，这是脚本的运行报告，请查收附件中的文件（如有）。"
        },
# ========================== START: MODIFICATION (Requirement ①) ==========================
# DESIGNER'S NOTE: 新增邮件标题模板字段，允许用户自定义并使用特殊标记。
        {
            "name": "custom_subject",
            "label": "邮件标题模板",
            "type": "text",
            "default": "脚本 <ifsuccess> 报告 - <time>",
            "info": "使用 <time> 插入时间戳, <ifsuccess> 插入成功/失败状态"
        },
# ========================== END: MODIFICATION (Requirement ①) ============================
        {
            "name": "script_command",
            "label": "脚本启动命令",
            "type": "textarea",
            "default": "python D:\\Desktop\\Develop\\Automatics\\GymGenAuto\\GymGenAuto.py"
        },
        {
            "name": "working_directory",
            "label": "工作目录 (脚本执行的上下文目录)",
            "type": "text",
            "default": "D:\\Desktop\\Develop\\Automatics\\GymGenAuto"
        },
        # ========================== START: MODIFICATION (Requirement ①) ==========================
        # DESIGNER'S NOTE:
        # 新增一个字段，用于让用户指定任务完成后需要嵌入到邮件正文的图片路径。
        {
            "name": "generated_attachment_paths",
            "label": "脚本生成的附件路径 (每行一个)",
            "type": "textarea",
            "default": (
                "D:\\Desktop\\Develop\\Automatics\\GymGenAuto\\generated_images\\output_1700.png\n"
                "D:\\Desktop\\Develop\\Automatics\\GymGenAuto\\generated_images\\output_1830.png\n"
                "D:\\Desktop\\Develop\\Automatics\\GymGenAuto\\generated_images\\output_2000.png"
            )
        },
        # ========================== END: MODIFICATION (Requirement ①) ============================
        {
            "name": "log_summary_prompt",
            "label": "日志总结提示词 (可选, 留空不总结)",
            "type": "textarea",
            "default": ""
        }
    ]
}

# --- 步骤 2: 编写模板生成函数 (异步) ---
async def get_script_runner_template(data: dict) -> dict:
    """
    执行脚本，处理日志，并生成附带附件的邮件内容。
    这是一个异步函数，因为它需要等待脚本执行和可能的 LLM API 调用。
    """
    message = data.get("email_body_message", '').strip()
    command = data.get('script_command', '').strip()
    work_dir = data.get('working_directory', '.').strip()
    attach_path = data.get('attach_file_path', '').strip()
    summary_prompt = data.get('log_summary_prompt', '').strip()
    # ========================== START: MODIFICATION (Unified Attachment System) ==========================
    generated_paths_str = data.get('generated_attachment_paths', '').strip()
    # ========================== END: MODIFICATION (Unified Attachment System) ============================

# ========================== START: MODIFICATION (Requirement ①) ==========================
# DESIGNER'S NOTE: 从 data 字典中获取用户定义的标题模板。
    custom_subject_template = data.get('custom_subject', '脚本执行报告').strip()
# ========================== END: MODIFICATION (Requirement ①) ============================

    if not command:
        return {
            "subject": "脚本执行失败：未提供命令",
            "html": "<h4>配置错误</h4><p>您必须在'脚本启动命令'字段中提供一个有效的命令。</p>",
            "attachments": []
        }
    
    # 脚本执行器现在内部处理绝对路径，这里无需转换
    exec_result = await script_runner_service.run_script(command, work_dir)

# ========================== START: MODIFICATION (Requirement ①) ==========================
# DESIGNER'S NOTE:
# 这是实现标题模板功能的核心逻辑。我们准备好替换的文本，然后对用户提供的模板字符串执行替换。
    # 准备替换用的文本
    timestamp = exec_result.get('start_time', 'N/A')
    success_str = "成功" if exec_result['success'] else "失败"

    # 执行替换，生成最终的邮件标题
    subject = custom_subject_template.replace("<time>", timestamp)
    subject = subject.replace("<ifsuccess>", success_str)
# ========================== END: MODIFICATION (Requirement ①) ============================
    
    # --- 构建 HTML 报告 ---
    status_color = "#4CAF50" if exec_result['success'] else "#F44336"
    status_text = "成功" if exec_result['success'] else "失败"
    
    # 将文本中的特殊 HTML 字符转义，并保留换行
    def escape_html(text):
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')

    stdout_html = escape_html(exec_result.get('stdout', ''))
    stderr_html = escape_html(exec_result.get('stderr', ''))
    # ========================== START: MODIFICATION (Requirements ①, ③) ==========================
    # DESIGNER'S NOTE:
    # 核心逻辑变更：处理由脚本生成的所有附件。
    # 我们不再区分图片或文件，所有路径都被统一处理并添加到 `attachments` 列表中。
    # HTML 正文现在只显示一个确认列表，而不是尝试嵌入图片。
    html_parts = []
    html_parts.append(f"<h4>{message}</h4>")

    html_parts.append(f"""
        <h4>执行详情 📊</h4>
        <ul>
            <li><strong>命令:</strong> <code>{command}</code></li>
            <li><strong>工作目录:</strong> <code>{os.path.abspath(work_dir)}</code></li>
            <li><strong>状态:</strong> <span style="color: {status_color}; font-weight: bold;">{status_text} (返回码: {exec_result.get('return_code')})</span></li>
            <li><strong>开始时间:</strong> {exec_result.get('start_time', 'N/A')}</li>
            <li><strong>结束时间:</strong> {exec_result.get('end_time', 'N/A')}</li>
            <li><strong>总耗时:</strong> {exec_result.get('duration_seconds', 'N/A')} 秒</li>
        </ul>""")

    script_generated_attachments = []
    
    if generated_paths_str:
        paths = [p.strip() for p in generated_paths_str.split('\n') if p.strip()]
        
        if paths:
            attachment_html_list = "<ul>"
            for path in paths:
                # 注意：这里我们只检查路径是否为绝对路径，实际存在性由 email_service 在发送时最终确认。
                # 这样即使脚本失败，我们仍然会尝试附加文件，这可能有助于调试。
                if os.path.isabs(path):
                    script_generated_attachments.append(path)
                    attachment_html_list += f"<li>✓ {os.path.basename(path)}</li>"
                else:
                    attachment_html_list += f"<li style='color: red;'>✗ {os.path.basename(path)} (路径非绝对路径，已跳过)</li>"
            attachment_html_list += "</ul>"
            
            html_parts.append(f"<h4>由脚本生成的附件 📎</h4>{attachment_html_list}")
    # ========================== END: MODIFICATION (Unified Attachment System) ============================

    

    # --- (可选) LLM 总结 ---
    log_for_summary = exec_result.get('stdout') or exec_result.get('stderr')
    if summary_prompt and log_for_summary:
        full_prompt = f"{summary_prompt}\n\n--- 日志开始 ---\n{log_for_summary}\n--- 日志结束 ---"
        # ========================== START: MODIFICATION ==========================
        summary_result = await llm_service.generate_text(full_prompt)
        # ========================== END: MODIFICATION ============================
        
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


    # --- 返回符合新规范的完整字典 ---
    return {
        "subject": subject,
        "html": "".join(html_parts),
        # 关键：返回一个包含所有待附加文件路径的列表
        "attachments": script_generated_attachments
    }
# ===================================================================================
# ========================== END: 修改区域 (需求 ①) ============================

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
async def get_deepseek_workflow_template(data: dict) -> dict:
    """【异步改造】调用 LLM 服务处理文本，并生成邮件内容"""
    
    text_to_process = data.get('text_ori', '').strip()
    
    if not text_to_process:
        return {
            "subject": "处理失败：输入文本为空",
            "html": "<h4>错误</h4><p>您没有提供任何需要处理的文本内容。</p>"
        }
    
    # ========================== START: MODIFICATION ==========================
    # 调用通用的 generate_text 方法
    result = await llm_service.generate_text(text_to_process)
    # ========================== END: MODIFICATION ============================
    
    if result["success"]:
        # 处理成功
        subject = f"AI处理结果 - {text_to_process[:20]}..."
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
        subject = "大模型工作流执行失败"
        html_content = f"""
            <h4>错误：大模型处理失败</h4>
            <p>在将您的文本发送给 API 时发生了错误。</p>
            
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
            "label": "报告存放文件夹 (绝对路径, 或相对 backend 的路径)",
            "type": "text",
            "default": "reports/"
        },
        # ========================== END: 修改区域 (更新UI提示) ============================
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
            "label": "报告存放文件夹 (绝对路径, 或相对 backend 的路径)",
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
    # ========================== START: MODIFICATION (需求 ① & ②) ==========================
    "daily_summary_plan": {
        "meta": daily_summary_plan_meta,
        "func": generate_daily_summary_plan_template
    },
    "weekly_summary_plan": {
        "meta": weekly_summary_plan_meta,
        "func": generate_weekly_summary_plan_template
    },
    "monthly_summary_plan": {
        "meta": monthly_summary_plan_meta,
        "func": generate_monthly_summary_plan_template
    },
    # ========================== END: MODIFICATION (需求 ① & ②) ============================
    "script_runner": {
        "meta": script_runner_meta,
        "func": get_script_runner_template
    },
    "local_file_report": {
        "meta": local_file_report_meta,
        "func": get_local_file_report_template
    },
    "deepseek_workflow": { # key 保持不变以兼容旧任务
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