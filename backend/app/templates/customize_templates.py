# backend/app/templates/customize_templates.py
DEBUG = True
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
    - 【重要】函数必须返回一个符合开发规范的字典。
      - 必须包含 `subject` (邮件主题) 和 `html` (邮件内容)。
      - 可选包含 `attachments` (文件附件路径列表) 和 `embedded_images` (内嵌图片信息列表)。
    - 【异步注意】: 如果你的模板函数需要执行 I/O 操作 (如 API 请求、运行脚本)，请将其定义为 `async def`。

 3. 注册你的模板:
    - 将你创建的元数据字典和模板生成函数组合在一起，形成一个完整的模板信息。
    - 将这个模板信息添加到一个名为 `custom_templates` 的字典中，key 为模板的唯一标识符。

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
import json
from collections import defaultdict
from ..core.config import settings
from ..services.llm_service import llm_service
from ..services.script_runner_service import script_runner_service

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
        # DESIGNER'S NOTE:
        # 这里的路径解析逻辑已增强，以稳健地处理绝对路径和相对路径。
        # 1. 如果 `report_folder` 是一个绝对路径 (例如 "C:/reports" 或 "/var/logs")，它将被直接使用。
        # 2. 如果它是一个相对路径 (例如 "reports/"), 它将被解析为相对于 `backend` 项目目录的路径。
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        abs_report_folder = report_folder if os.path.isabs(report_folder) else os.path.abspath(os.path.join(backend_dir, report_folder))
        file_path = os.path.join(abs_report_folder, report_filename)

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

# ===================================================================================
# 模块: 每日总结与计划 (Daily Summary & Plan)
# ===================================================================================

# ========================== START: MODIFICATION (Timeline Logic) ==========================
# DESIGNER'S NOTE:
# 定义四大象限及其子项的映射关系，以及对应的颜色配置。
# 颜色选取逻辑：符合心理预期，同时在邮件白色背景上清晰可见。
LIFE_QUADRANTS = {
    '生产': {'items': ['工作', '学习', '创作', '规划'], 'color': '52, 152, 219'}, # 蓝色系
    '消耗': {'items': ['通勤', '家务', '琐事', '沉溺'], 'color': '149, 165, 166'}, # 灰色系 (沉溺可用深灰)
    '维护': {'items': ['睡眠', '饮食', '洗漱', '养身'], 'color': '241, 196, 15'}, # 黄色系
    '恢复': {'items': ['运动', '娱乐', '社交', '独思'], 'color': '46, 204, 113'}  # 绿色系
}

# 辅助映射：子项 -> 大象限
SUB_TO_MAIN_MAP = {}
for main, content in LIFE_QUADRANTS.items():
    for sub in content['items']:
        SUB_TO_MAIN_MAP[sub] = main

TIMELINE_ICONS = {
    '工作':'💼','学习':'📚','创作':'🎨','规划':'🧭',
    '运动':'🏃','娱乐':'🎮','社交':'💬','独思':'🧘',
    '睡眠':'🌙','饮食':'🍔','洗漱':'🚿','养身':'💊',
    '通勤':'🚌','家务':'🧹','琐事':'🧾','沉溺':'🧟'
}

TIMELINE_COLORS_HEX = {
    '工作': '#64B5F6', '学习': '#81C784', '创作': '#FFB74D', '规划': '#BA68C8',
    '运动': '#E57373', '娱乐': '#F06292', '社交': '#4DB6AC', '独思': '#9575CD',
    '睡眠': '#90A4AE', '饮食': '#AED581', '洗漱': '#4DD0E1', '养身': '#FF8A65',
    '通勤': '#FFD54F', '家务': '#A1887F', '琐事': '#E0E0E0', '沉溺': '#546E7A'
}

def _time_str_to_seconds(t_str):
    """辅助函数：将 HH:MM:SS 转换为秒"""
    try:
        parts = list(map(int, t_str.split(':')))
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except (ValueError, IndexError):
        return 0

def _seconds_to_hm(seconds):
    """辅助函数：秒转 Xh Ym"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

# ========================== START: ANALYTICS PARSER ==========================
def _parse_time_log_statistics(log_text: str) -> dict:
    """
    [核心新增] 解析时间日志，计算四大象限的统计数据。
    返回结构:
    {
        'total_tracked': int (seconds),
        'quadrants': {
            '生产': {'duration': 0, 'percent': 0.0, 'breakdown': {'工作': 100, ...}},
            ...
        }
    }
    """
    stats = {
        'total_tracked': 0,
        'quadrants': {k: {'duration': 0, 'percent': 0.0, 'breakdown': defaultdict(int)} for k in LIFE_QUADRANTS.keys()}
    }

    if not log_text or not log_text.strip():
        return stats

    lines = log_text.strip().split('\n')
    regex = re.compile(r'^\-\s*\[(\d{2}:\d{2}:\d{2})\s*-\s*(.*?)\]\s*\[(.*?)\]\s*\[(.*?)\/(.*?)\](?:\s*\|\s*(.*))?$')
    
    now = datetime.datetime.now()
    current_seconds_of_day = now.hour * 3600 + now.minute * 60 + now.second

    for line in lines:
        match = regex.match(line.strip())
        if match:
            start_str, end_str, cat, main_cat, sub_cat, remark = match.groups()
            
            if '...' in end_str:
                end_sec = current_seconds_of_day
            else:
                end_sec = _time_str_to_seconds(end_str)
            
            start_sec = _time_str_to_seconds(start_str)
            duration = end_sec - start_sec
            
            if duration > 0:
                stats['total_tracked'] += duration
                
                # 确定大象限：优先使用映射表，如果日志里写的Main/Sub不匹配，尝试映射Sub，最后回退到日志里的Main
                quadrant = SUB_TO_MAIN_MAP.get(sub_cat)
                if not quadrant and main_cat in LIFE_QUADRANTS:
                    quadrant = main_cat
                
                if quadrant and quadrant in stats['quadrants']:
                    stats['quadrants'][quadrant]['duration'] += duration
                    stats['quadrants'][quadrant]['breakdown'][sub_cat] += duration

    # 计算百分比
    total = stats['total_tracked']
    if total > 0:
        for q in stats['quadrants']:
            stats['quadrants'][q]['percent'] = (stats['quadrants'][q]['duration'] / total) * 100

    return stats
# ========================== END: ANALYTICS PARSER ==========================


# ========================== START: VISUALIZATION RENDERERS ==========================
def _render_quadrant_heatmap(stats: dict) -> str:
    """
    [核心新增] 生成四大象限的 2x2 热力矩阵图 (HTML)。
    颜色深浅基于投入时间比重。
    布局：
    消耗 | 生产
    维护 | 恢复
    """
    quadrants = stats['quadrants']
    total_time = stats['total_tracked']
    if total_time == 0:
        return "<p>暂无数据生成象限图。</p>"

    # 布局顺序：左上(消耗)，右上(生产)，左下(维护)，右下(恢复) —— 参考用户图片
    layout_order = ['消耗', '生产', '维护', '恢复']
    
    html = ['<div style="display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 4px; width: 100%; max-width: 500px; height: 300px; margin: 20px 0; font-family: sans-serif;">']

    for q_name in layout_order:
        data = quadrants.get(q_name, {'duration': 0, 'percent': 0})
        rgb = LIFE_QUADRANTS[q_name]['color']
        
        # 计算透明度：基于占比，最低 0.1，最高 0.9。
        # 算法：Base 0.1 + (Percent / 50 * 0.8) -> 假设单象限最大占比50%时颜色最深，超过也按最深算
        alpha = 0.1 + min(data['percent'] / 40.0, 1.0) * 0.8
        bg_color = f"rgba({rgb}, {alpha:.2f})"
        border_color = f"rgba({rgb}, 1)"
        
        duration_str = _seconds_to_hm(data['duration'])
        
        # 找出该象限下Top 2的子项
        breakdown = data.get('breakdown', {})
        sorted_subs = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)[:2]
        subs_str = " ".join([f"{k}" for k, v in sorted_subs])

        cell_html = f"""
        <div style="background-color: {bg_color}; border: 2px solid {border_color}; border-radius: 8px; padding: 10px; display: flex; flex-direction: column; justify-content: center; align-items: center; color: #333;">
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 5px;">{q_name}</div>
            <div style="font-size: 14px;">{data['percent']:.1f}%</div>
            <div style="font-size: 12px; color: #555;">{duration_str}</div>
            <div style="font-size: 10px; color: #777; margin-top: 4px;">{subs_str}</div>
        </div>
        """
        html.append(cell_html)

    html.append('</div>')
    return "".join(html)


def _render_trend_stack_chart(daily_stats_list: list) -> str:
    """
    [核心新增] 生成周期趋势堆叠图 (HTML)。
    横轴：日期
    纵轴：100% 堆叠柱状图 (四大象限)
    """
    if not daily_stats_list:
        return ""

    html = []
    html.append('<div style="margin-top: 20px; font-family: sans-serif;">')
    html.append('<h4>📈 生活重心趋势 (堆叠图)</h4>')
    html.append('<div style="display: flex; height: 200px; align-items: flex-end; width: 100%; overflow-x: auto; padding-bottom: 5px;">')

    # 图例
    legend_html = '<div style="display: flex; justify-content: center; margin-bottom: 10px; font-size: 12px;">'
    for q_name in ['生产', '消耗', '维护', '恢复']:
        rgb = LIFE_QUADRANTS[q_name]['color']
        color = f"rgba({rgb}, 0.7)"
        legend_html += f'<div style="display:flex; align-items:center; margin-right: 15px;"><span style="width:10px; height:10px; background:{color}; margin-right:5px; display:inline-block;"></span>{q_name}</div>'
    legend_html += '</div>'
    html.insert(1, legend_html)

    for day_data in daily_stats_list:
        date_label = day_data['date_str'] # e.g. "03-15"
        stats = day_data['stats']
        total = stats['total_tracked']
        
        html.append('<div style="flex: 1; min-width: 40px; margin: 0 2px; display: flex; flex-direction: column-reverse; height: 100%;">')
        
        # 渲染柱子
        bar_html = []
        if total > 0:
            for q_name in ['生产', '恢复', '维护', '消耗']: # 堆叠顺序
                q_data = stats['quadrants'].get(q_name)
                pct = q_data['percent']
                if pct > 0:
                    rgb = LIFE_QUADRANTS[q_name]['color']
                    # Tooltip title
                    title = f"{date_label} {q_name}: {pct:.1f}% ({_seconds_to_hm(q_data['duration'])})"
                    bar_html.append(f'<div style="height: {pct}%; background-color: rgba({rgb}, 0.8); width: 100%;" title="{title}"></div>')
        else:
             # 无数据占位
             bar_html.append('<div style="height: 100%; background-color: #eee;" title="无数据"></div>')
        
        html.append("".join(bar_html))
        
        # 日期标签
        html.append(f'<div style="text-align: center; font-size: 10px; color: #666; margin-top: 4px; writing-mode: horizontal-tb;">{date_label}</div>')
        html.append('</div>')

    html.append('</div></div>')
    return "".join(html)


def _render_timeline_html(log_text: str) -> str:
    """
    [核心修改] 将时间日志文本转换为横向时间轴 HTML。
    该函数包含完整的鲁棒性检查，如果日志为空或解析失败，安全返回空字符串。
    """
    if not log_text or not log_text.strip():
        return ""

    lines = log_text.strip().split('\n')
    tasks = []
    # 正则匹配: - [00:00:00 - 01:00:00] [Category] [Main/Sub] | Remark
    # 兼容 ... 结束时间
    regex = re.compile(r'^\-\s*\[(\d{2}:\d{2}:\d{2})\s*-\s*(.*?)\]\s*\[(.*?)\]\s*\[(.*?)\/(.*?)\](?:\s*\|\s*(.*))?$')
    
    now = datetime.datetime.now()
    # 计算当前是一天中的第几秒
    current_seconds_of_day = now.hour * 3600 + now.minute * 60 + now.second
    # 范围至少显示到当前时间，且至少显示1小时，避免除以0或范围过小
    total_scope = max(current_seconds_of_day, 3600)

    for line in lines:
        match = regex.match(line.strip())
        if match:
            start_str, end_str, cat, main_cat, sub_cat, remark = match.groups()
            remark = remark or ''
            
            # 处理 "..." 表示进行中，结束时间设为当前时间
            if '...' in end_str:
                end_sec = current_seconds_of_day
                display_end = now.strftime("%H:%M:%S")
            else:
                end_sec = _time_str_to_seconds(end_str)
                display_end = end_str
            
            start_sec = _time_str_to_seconds(start_str)
            duration = end_sec - start_sec
            
            if duration > 0:
                tasks.append({
                    'start': start_sec,
                    'duration': duration,
                    'sub': sub_cat,
                    'remark': remark,
                    'raw_start': start_str,
                    'raw_end': display_end,
                    'category': cat,
                    'main': main_cat
                })

    if not tasks:
        return ""

    # 按子类名称排序
    sorted_subs = sorted(list(set(t['sub'] for t in tasks)))
    
    # 开始构建 HTML
    # 使用内联样式以确保邮件兼容性 (Mail clients often strip external CSS)
    html_parts = []
    # 容器：添加横向滚动支持，防止在小屏幕上溢出
    html_parts.append('<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #fafafa; padding: 15px; border-radius: 8px; border: 1px solid #e0e0e0; margin-top: 15px; overflow-x: auto;">')
    html_parts.append('<h4 style="margin-top: 0; color: #333;">📊 今日时间轴</h4>')
    
    # 1. 时间刻度行
    html_parts.append('<div style="display: flex; height: 20px; border-bottom: 1px solid #ddd; margin-bottom: 8px; position: relative; min-width: 300px;">')
    html_parts.append('<div style="width: 30px; flex-shrink: 0;"></div>') # 左侧图标占位
    html_parts.append('<div style="flex-grow: 1; position: relative;">') # 刻度区
    
    # 每小时生成一个刻度
    hours_to_show = int(total_scope / 3600)
    for h in range(hours_to_show + 1):
        sec = h * 3600
        pct = (sec / total_scope) * 100
        if pct <= 100:
            # 时间标签: 偶数小时显示数字，防止拥挤
            if h % 2 == 0: 
                html_parts.append(f'<div style="position: absolute; left: {pct}%; top: 0; font-size: 10px; color: #999; transform: translateX(-50%);">{h:02d}</div>')
            # 刻度线
            html_parts.append(f'<div style="position: absolute; left: {pct}%; bottom: 0; width: 1px; height: 4px; background: #ccc;"></div>')
            
    html_parts.append('</div></div>') # 结束刻度行

    # 2. 轨道行 (Rows)
    for sub in sorted_subs:
        icon = TIMELINE_ICONS.get(sub, sub[0].upper() if sub else '?')
        color = TIMELINE_COLORS_HEX.get(sub, '#90A4AE') 
        
        html_parts.append('<div style="display: flex; align-items: center; margin-bottom: 6px; min-width: 300px;">')
        # 左侧图标
        html_parts.append(f'<div style="width: 30px; font-size: 16px; text-align: center; flex-shrink: 0; cursor: default;" title="{sub}">{icon}</div>')
        # 右侧轨道槽
        html_parts.append('<div style="flex-grow: 1; height: 20px; background: #f0f0f0; position: relative; border-radius: 4px;">')
        
        # 渲染该轨道上的所有任务块
        row_tasks = [t for t in tasks if t['sub'] == sub]
        for t in row_tasks:
            left_pct = (t['start'] / total_scope) * 100
            width_pct = (t['duration'] / total_scope) * 100
            
            # Tooltip content (使用 title 属性，这是最兼容的实现方式)
            title_text = f"[{t['raw_start']} - {t['raw_end']}] {t['sub']} | {t['remark']}"
            
            # 块样式
            html_parts.append(f'''
            <div style="position: absolute; left: {left_pct}%; width: {width_pct}%; 
                        height: 100%; background-color: {color}; border-radius: 3px; 
                        box-shadow: 0 1px 2px rgba(0,0,0,0.1);" 
                 title="{title_text}">
            </div>
            ''')
            
        html_parts.append('</div></div>') # 结束行

    html_parts.append('</div>') # 结束容器
    return "".join(html_parts)
# ========================== END: MODIFICATION (Timeline Logic) ============================


# --- 步骤 0: 内部辅助函数 ---

def _create_default_daily_template(filepath: str, plan_items_from_yesterday: list = None):
    """
    在一个指定的路径创建一个默认的每日总结Markdown模板文件。
    新增功能：可以接收昨天的计划并自动填充到今天的待办中，并加入了“随手记”板块。
    """
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
    
    

    # 2. 随手记 (LifeQuadrant Notes)
    notes_section = "\n## ✍️ 随手记\n\n- \n"

    template_plan = "\n## 🚀 明日计划\n\n- \n"

    # 3. 时间日志 (LifeQuadrant Time Log) - 新增
    # LifeQuadrant 将自动追加内容到这里
    time_log_section = "\n## 📊 时间日志\n\n" 
    
    final_content = template_header + today_items_section + notes_section + template_plan + time_log_section
    
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
    # 使用正则提取各个部分
    # 注意：正则需要非贪婪匹配，并且兼容最后一部分没有后续标题的情况
    today_items_match = re.search(r'##\s*📝\s*今日事项\s*([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)
    time_logs_match = re.search(r'##\s*📊\s*时间日志\s*([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)
    notes_match = re.search(r'##\s*✍️\s*随手记\s*([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)
    plan_match = re.search(r'##\s*🚀\s*明日计划\s*([\s\S]*?)(?=\n##|$)', content, re.IGNORECASE)

    today_items_content = today_items_match.group(1).strip() if today_items_match else ""
    time_logs_content = time_logs_match.group(1).strip() if time_logs_match else ""
    notes_content = notes_match.group(1).strip() if notes_match else ""
    plan_content = plan_match.group(1).strip() if plan_match else ""

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
        "time_logs": time_logs_content, # 直接返回原始文本供 LLM 分析
        "notes": notes_items,
        "plan": plan_items,
        "total": total_tasks,
        "progress": round(progress)
    }

async def _generate_period_summary(period_days: int, period_name: str, data: dict) -> dict:
    """
    通用函数，用于生成周度或月度总结报告。
    """
    system_prompt = data.get("system_prompt", "你是一位专业的个人成长教练和数据分析师。")

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
            # 文件名格式兼容 YYYY-MM-DD.md
            date_str = filename[:10]
            file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            if start_date <= file_date < today: # Exclude today
                relevant_files.append((file_date, filepath))
        except (ValueError, TypeError):
            continue
    
    if not relevant_files:
        return {
            "subject": f"{period_name}总结：范围内无历史数据",
            "html": f"<h4>无数据</h4><p>在过去 {period_days} 天内没有找到任何有效的每日总结历史记录。</p>"
        }

    relevant_files.sort()
    
    # 聚合数据容器
    all_done_tasks, all_todo_tasks, all_notes = [], [], []
    total_tasks_count = 0
    progress_per_day = []
    daily_stats_list = [] # 用于绘制堆叠图

    # 聚合象限数据
    aggregated_quadrants = {k: {'duration': 0} for k in LIFE_QUADRANTS.keys()}
    total_tracked_period = 0
    
    for file_date, filepath in relevant_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            parsed = _parse_daily_summary(content)
            
            # 任务数据
            all_done_tasks.extend(parsed["done"])
            all_todo_tasks.extend(parsed["todo"])
            all_notes.extend(parsed["notes"])
            total_tasks_count += parsed["total"]
            progress_per_day.append({"date": file_date.strftime("%m-%d"), "progress": parsed["progress"]})

            # 时间统计数据
            stats = _parse_time_log_statistics(parsed["time_logs"])
            daily_stats_list.append({'date_str': file_date.strftime("%m-%d"), 'stats': stats})
            
            # 全局累加
            total_tracked_period += stats['total_tracked']
            for q, q_data in stats['quadrants'].items():
                aggregated_quadrants[q]['duration'] += q_data['duration']

    overall_progress = (len(all_done_tasks) / total_tasks_count * 100) if total_tasks_count > 0 else 0

    # 计算周期内的象限占比
    quadrant_summary_text = []
    for q_name, q_data in aggregated_quadrants.items():
        dur = q_data['duration']
        pct = (dur / total_tracked_period * 100) if total_tracked_period > 0 else 0
        q_data['percent'] = pct # 补全 percent 字段用于绘图
        quadrant_summary_text.append(f"{q_name}: {_seconds_to_hm(dur)} ({pct:.1f}%)")
    
    # 构建可视化
    # 1. 周期总体热力图 (使用聚合数据)
    aggregated_stats_obj = {'total_tracked': total_tracked_period, 'quadrants': aggregated_quadrants}
    heatmap_html = _render_quadrant_heatmap(aggregated_stats_obj)
    
    # 2. 每日趋势堆叠图
    trend_chart_html = _render_trend_stack_chart(daily_stats_list)

    # 4. 构建AI Prompt
    progress_str = ", ".join([f"{p['date']}: {p['progress']}%" for p in progress_per_day])
    
    prompt = f"""
{system_prompt}
我将为你提供我过去{period_days}天的每日任务完成情况数据。请你基于这些数据，为我生成一份详细的{period_name}总结报告。

**数据概览:**
- 总任务数: {total_tasks_count}, 完成: {len(all_done_tasks)}, 完成率: {overall_progress:.1f}%
- 每日完成率趋势: {progress_str}

**生活平衡数据 (四象限分析):**
- 总记录时间: {_seconds_to_hm(total_tracked_period)}
- 象限分布: {', '.join(quadrant_summary_text)}

**详细内容:**
- 完成的任务: {'; '.join(all_done_tasks[:50])}...
- 遗留的任务: {'; '.join(all_todo_tasks[:20])}...
- 随手记 (Thoughts): {'; '.join(all_notes)}

关于四象限分析的简要介绍:
本日志采用 “能量流向”四象限模型 归类所有活动，以追踪时间在价值创造、能量恢复、维持生存和被动消耗中的分布。四象限及下辖的十六个子类定义如下：

生产	高能量输出	主动创造价值，构建未来，提升个人资本的活动。	工作、学习、创作、规划
恢复	能量回充	主动进行的、高质量的身心放松与自我关怀活动。	运动、娱乐、社交、独思
维护	维持基线	作为生物体和独立个体，为保持正常运作所必需的生存性、规律性活动。	睡眠、饮食、洗漱、养身
消耗	能量流失	低价值回报、伴随系统摩擦或无意识被动卷入的时间黑洞。	通勤、家务、琐事、沉溺
**你的任务:**
1.  **生活平衡诊断**: 基于象限数据，分析我的生活重心。是“生产”过载，还是“恢复”不足？是否存在过多的“消耗”？
2.  **趋势分析**: 效率是上升还是下降？
3.  **深层洞察**: 结合任务和随手记，发现我的焦虑来源或成就模式。
4.  **下阶段建议**: 给出具体的调整建议（例如：增加运动，减少碎片化家务等）。

请使用Markdown格式，分析要深刻且具建设性。
"""
    
    # 5. 调用AI并构建邮件
    ai_result = await llm_service.generate_text(prompt)
    ai_analysis_html = convert_markdown_to_html(ai_result['content']) if ai_result['success'] else f"<p>AI分析失败: {ai_result['content']}</p>"

    subject = f"您的专属{period_name}总结报告 ({start_date.strftime('%Y-%m-%d')} - {(today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')})"
    html_content = f"""
        <h4>数据概览</h4>
        <ul>
            <li><strong>时间范围:</strong> {start_date.strftime('%Y-%m-%d')} 至 {(today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')}</li>
            <li><strong>总计划任务:</strong> {total_tasks_count} 项</li>
            <li><strong>总完成任务:</strong> {len(all_done_tasks)} 项</li>
            <li><strong>总体完成率:</strong> <span style="font-size: 18px; color: #4CAF50; font-weight: bold;">{overall_progress:.1f}%</span></li>
        </ul>
        
        <h4>📊 生活平衡象限 (LifeQuadrant)</h4>
        {heatmap_html}
        
        <h4>📈 时间投入趋势</h4>
        {trend_chart_html}

        <h4>🧠 AI深度分析与建议</h4>
        {ai_analysis_html}
    """
    
    return {"subject": subject, "html": html_content}


# --- 步骤 1: 【新模板】每日总结与明日计划 ---
daily_summary_plan_meta = {
    "display_name": "每日总结与明日计划 (自动)",
    "description": "智能工作流：首次运行初始化当天计划（自动迁移昨日计划），后续运行则进行总结、分析和归档。",
    "fields": [
        {
            "name": "system_prompt",
            "label": "AI角色提示词 (System Prompt)",
            "type": "textarea",
            "default": "你是一位充满活力和鼓励精神的私人助理。你的任务是根据我今天的数据，用亲切自然的语气为我总结，并给予我激励。"
        }
    ]
}

async def generate_daily_summary_plan_template(data: dict) -> dict:
    system_prompt = data.get("system_prompt", "你是一位充满活力的私人助理。")
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
    today_filepath = os.path.join(base_path, f"{today.strftime('%Y-%m-%d')}.md")
    yesterday_filepath = os.path.join(base_path, f"{yesterday.strftime('%Y-%m-%d')}.md")

    if not os.path.exists(today_filepath):
        # 场景A: 当天首次运行 - 初始化
        yesterdays_plan = []
        
        # 2a. 查找并处理昨日文件
        if os.path.exists(yesterday_filepath):
            try:
                with open(yesterday_filepath, 'r', encoding='utf-8') as f:
                    y_content = f.read()
                
                # 从昨日文件中提取“明日计划”
                yesterdays_plan = _parse_daily_summary(y_content).get("plan", [])
                shutil.move(yesterday_filepath, os.path.join(history_path, f"{yesterday.strftime('%Y-%m-%d')}.md"))
            except Exception as e:
                print(f"处理昨日文件 {yesterday_filepath} 时出错: {e}")
        
        # 2b. 创建今日文件，并迁移计划
        _create_default_daily_template(today_filepath, plan_items_from_yesterday=yesterdays_plan)
        
        # 2c. 发送初始化邮件
        email_html = f"<h4>今日总结已初始化！</h4><p>系统已为您创建了今天的模板文件：</p><p><code>{today_filepath}</code></p>"
        email_html += "<p>并已将您昨天的“明日计划”自动迁移为今天的待办事项。请开始新的一天吧！</p>" if yesterdays_plan else "<p>请立即填写今日的计划与总结吧！</p>"
        return {"subject": f"✅ {today.strftime('%Y-%m-%d')} 新的一天，计划已就绪！", "html": email_html}
            
    else:
        # 场景B: 当天后续运行 - 总结
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
            
        # ========================== START: MODIFICATION (Time Log Stats) ==========================
        # 解析时间统计数据
        time_logs_text = parsed_data.get('time_logs', '')
        time_stats = _parse_time_log_statistics(time_logs_text)
        
        # 生成可视化 HTML
        timeline_html = _render_timeline_html(time_logs_text)
        heatmap_html = _render_quadrant_heatmap(time_stats)
        
        # 准备统计摘要给 AI
        quadrant_text_list = []
        for q, d in time_stats['quadrants'].items():
            if d['duration'] > 0:
                # 找出主要构成
                top_sub = max(d['breakdown'], key=d['breakdown'].get) if d['breakdown'] else "无"
                quadrant_text_list.append(f"{q}: {d['percent']:.1f}% ({_seconds_to_hm(d['duration'])}, 主项:{top_sub})")
        quadrant_summary = ", ".join(quadrant_text_list) if quadrant_text_list else "暂无有效时间记录"
        # ========================== END: MODIFICATION ============================

        # 3c. 构建AI Prompt
        prompt = f"""
{system_prompt}
请为我生成一份总结报告。
截至总结报告时，当前时间为 {datetime.datetime.now().strftime("%Y年%m月%d日%H:%M:%S")}
我的今日数据:
- **已完成事项**: {', '.join(parsed_data['done']) if parsed_data['done'] else '无'}
- **未完成事项**: {', '.join(parsed_data['todo']) if parsed_data['todo'] else '无'}
- **今日任务完成率**: {parsed_data['progress']}%
- **我的随手记**: {', '.join(parsed_data['notes']) if parsed_data['notes'] else '无'}
- **我的明日计划**: {', '.join(parsed_data['plan']) if parsed_data['plan'] else '未计划'}

我的时间投入记录：{parsed_data['time_logs'] if parsed_data['time_logs'] else "（今日暂无时间记录）"}

关于四象限分析的简要介绍:
本日志采用 “能量流向”四象限模型 归类所有活动，以追踪时间在价值创造、能量恢复、维持生存和被动消耗中的分布。四象限及下辖的十六个子类定义如下：

生产	高能量输出	主动创造价值，构建未来，提升个人资本的活动。	工作、学习、创作、规划
恢复	能量回充	主动进行的、高质量的身心放松与自我关怀活动。	运动、娱乐、社交、独思
维护	维持基线	作为生物体和独立个体，为保持正常运作所必需的生存性、规律性活动。	睡眠、饮食、洗漱、养身
消耗	能量流失	低价值回报、伴随系统摩擦或无意识被动卷入的时间黑洞。	通勤、家务、琐事、沉溺

**时间投入分析 (Life Quadrant):**
- 总记录时间: {_seconds_to_hm(time_stats['total_tracked'])}
- 象限分布: {quadrant_summary}
你的任务:
1.  **总结表现**: 简要总结我今天的表现。
2.  **时间利用分析**: 结合上述象限数据，点评我的时间分配。
3.  **关联分析**: 结合“随手记”和“未完成事项”，看看是否能发现一些潜在的关联或问题，并提出。
4.  **结尾建议**: 最后用一句符合你角色设定的话结尾。

请直接生成报告正文，使用Markdown格式，语言亲切自然。
"""

        # 3d. 调用AI并构建邮件
        ai_result = await llm_service.generate_text(prompt)
        ai_analysis_html = convert_markdown_to_html(ai_result['content']) if ai_result['success'] else f"<p>AI分析失败: {ai_result['content']}</p>"

        raw_logs = parsed_data.get('time_logs', '')
        if raw_logs:
            time_log_list_html = "<ul>" + "".join(f'<li>{item}</li>' for item in raw_logs.split('\n') if item.strip()) + "</ul>"
        else:
            time_log_list_html = "<ul><li>暂无时间记录。</li></ul>"

        subject = f"你的专属每日总结报告 - {today.strftime('%Y-%m-%d')}"
        html_content = f"""
            <h4>今日任务完成度: {parsed_data['progress']}%</h4>
            <div style="width: 100%; background-color: #e0e0e0; border-radius: 5px; height: 20px; overflow: hidden;">
                <div style="background-color: #4CAF50; width: {parsed_data['progress']}%; height: 100%; text-align: center; color: white; line-height: 20px; font-weight: bold; border-radius: 5px;">{parsed_data['progress']}%</div>
            </div>
            
            <h4>📊 LifeQuadrant 象限热力图</h4>
            {heatmap_html}

            <h4>⏱️ 时间轴可视化</h4>
            {timeline_html}
            
            <h4>✅ 已办清单</h4>
            <ul>{''.join(f'<li>{item}</li>' for item in parsed_data['done']) if parsed_data['done'] else '<li>今日暂无完成事项</li>'}</ul>

            <h4>📝 待办清单</h4>
            <ul>{''.join(f'<li>{item}</li>' for item in parsed_data['todo']) if parsed_data['todo'] else '<li>太棒了！没有待办遗留！</li>'}</ul>
            
            <h4>✍️ 随手记</h4>
            <ul>{''.join(f'<li>{item}</li>' for item in parsed_data['notes']) if parsed_data['notes'] else '<li>暂无随手记录。</li>'}</ul>

            <h4>🚀 明日计划</h4>
            <ul>{''.join(f'<li>{item}</li>' for item in parsed_data['plan']) if parsed_data['plan'] else '<li>暂未规划明日事项。</li>'}</ul>
            
            <details>
                <summary style="cursor: pointer; color: #666; margin-top: 5px;">查看原始时间文本</summary>
                {time_log_list_html}
            </details>

            <h4>💡 AI 智能助理分析</h4>
            {ai_analysis_html}
        """
        
        return {"subject": subject, "html": html_content}

# --- 模板 2 & 3: 周/月度总结报告 (自动) ---
weekly_summary_plan_meta = {
    "display_name": "周度总结报告 (自动)",
    "description": "自动聚合过去7天的每日总结历史，通过AI生成深度分析周报。",
    "fields": [
        {
            "name": "system_prompt",
            "label": "AI角色提示词 (System Prompt)",
            "type": "textarea",
            "default": "你是一位专业的个人成长教练和数据分析师。你的语气专业、富有洞察力且积极。你的目标是帮助我复盘过去，更好地规划未来。"
        }
    ]
}

monthly_summary_plan_meta = {
    "display_name": "月度总结报告 (自动)",
    "description": "自动聚合过去30天的每日总结历史，通过AI生成深度分析月报。",
    "fields": [
        {
            "name": "system_prompt",
            "label": "AI角色提示词 (System Prompt)",
            "type": "textarea",
            "default": "你是一位富有远见的战略顾问和生活导师。你的分析应更侧重于长期趋势、模式识别和深层动机的挖掘。你的语气应沉稳、睿智且鼓舞人心。"
        }
    ]
}


async def generate_weekly_summary_plan_template(data: dict) -> dict:
    return await _generate_period_summary(7, "周度", data)

async def generate_monthly_summary_plan_template(data: dict) -> dict:
    """生成月度总结报告。"""
    return await _generate_period_summary(30, "月度", data)


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


# ===================================================================================
# 【模板】: 自动运行脚本并获取日志结果
# ===================================================================================
# ========================== START: MODIFICATION (Flexible Attachments) ==========================
# DESIGNER'S NOTE:
# 我们大幅升级了这个模板的元数据和逻辑。
# 1. 元数据：将 `generated_attachment_paths` 升级为 `attachment_rules`，支持更复杂的规则。
# 2. 逻辑：引入 glob 模块，支持通配符 (*) 和目录扫描。
# 3. 报告：在 HTML 中增加了一个附件列表板块，让用户清晰看到哪些文件被匹配到了。
script_runner_meta = {
    "display_name": "自动运行脚本并获取日志结果",
    "description": (
        "在后台运行命令，捕获其输出。支持使用通配符或目录路径来灵活地收集和发送附件。\n\n"
        "【高级功能 - 反向控制】\n\n"
        "您可以在工作目录下用程序生成'eminder_meta.json'，用以动态地自定义正文、标题与附件情况。\n\n脚本执行结束后，如果工作目录下存在名为 'eminder_meta.json' 的文件，\n\n"
        "系统将读取并**自动删除**它，用以自定义邮件内容。\n\n"
        "这个操作的优先级高于下方的所有配置。\n\n"
        "JSON 格式示例：\n"
        "~~~json\n"
        "{\n"
        "  \"subject\": \"自定义标题\",\n"
        "  \"content\": \"# 自定义正文。可以输入 **Markdown** 语法。\",\n"
        "  \"attachments\": [\"相对路径/file1.jpg\", \"D:/绝对路径/file2.log\"]\n"
        "  \"skip_email\": true,              // [可选] 如果为 true，则完全不发送邮件（但脚本已运行）（默认false）\n"
        "  \"show_execution_details\": false, // [可选] 是否显示命令、耗时等信息 (默认 true)\n"
        "  \"show_logs\": false,              // [可选] 是否显示 stdout/stderr (默认 true)\n"
        "  \"show_attachments_list\": false   // [可选] 是否在正文中列出附件清单 (默认 true)\n"
        "}\n"
        "~~~"
    ),
    "fields": [
        {
            "name": "email_body_message",
            "label": "邮件说明与附言 (默认)",
            "type": "textarea",
            "default": "您好，这是脚本的运行报告，请查收附件中的文件（如有）。",
            "info": "如果在 'eminder_meta.json' 中指定了 'content' 字段，此内容将被忽略。"
        },
        {
            "name": "custom_subject",
            "label": "邮件标题模板 (默认)",
            "type": "text",
            "default": "脚本 <ifsuccess> 报告 - <time>",
            "info": "支持 <time> 和 <ifsuccess> 标记。如果在 'eminder_meta.json' 中指定了 'subject' 字段，此设置将被忽略。"
        },
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
        {
            "name": "attachment_rules",
            "label": "附件收集规则 (每行一条)",
            "type": "textarea",
            "default": (
                "# 支持绝对路径、文件夹路径或 Glob 通配符\n"
                "D:\\Logs\\error.log\n"
                "D:\\Reports\\*.pdf\n"
                "D:\\Output_Images\\"
            ),
            "info": "输入文件夹路径将发送该文件夹下的所有文件；使用 *.txt 等通配符可匹配多个文件。"
        },
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
    执行脚本，处理日志，并根据灵活的规则收集附件。
    新增功能：支持从脚本生成的配置文件中读取标题和正文（支持Markdown）。
    """
    default_message = data.get("email_body_message", '').strip()
    command = data.get('script_command', '').strip()
    work_dir = data.get('working_directory', '.').strip()
    summary_prompt = data.get('log_summary_prompt', '').strip()
    attachment_rules_str = data.get('attachment_rules', '').strip()
    custom_subject_template = data.get('custom_subject', '脚本执行报告').strip()

    if not command:
        return {
            "subject": "脚本执行失败：未提供命令",
            "html": "<h4>配置错误</h4><p>您必须在'脚本启动命令'字段中提供一个有效的命令。</p>",
            "attachments": []
        }
    
    # 1. 执行脚本
    exec_result = await script_runner_service.run_script(command, work_dir)

    # ========================== START: MODIFICATION (需求: Script Config) ==========================
    # DESIGNER'S NOTE:
    # 这里实现了“通过脚本生成的配置文件自定义邮件内容”的需求。
    # 脚本可以在工作目录生成 eminder_meta.json。如果存在，我们读取它，
    # 并在读取后删除以防止污染下次运行。
    
    meta_filename = "eminder_meta.json"
    # 确保使用绝对路径查找，基于脚本实际执行的工作目录
    abs_work_dir = os.path.abspath(work_dir)
    meta_path = os.path.join(abs_work_dir, meta_filename)
    
    script_meta = {}
    
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                script_meta = json.load(f)
            
            # 读取成功后，尝试删除该文件
            try:
                os.remove(meta_path)
                print(f"[EMinder Info] 成功读取并清除脚本配置文件: {meta_path}")
            except OSError as e:
                print(f"[EMinder Warning] 读取配置后删除文件失败: {e}")
                
        except Exception as e:
            # 解析失败，记录到 stderr 以便在报告中体现
            error_msg = f"\n[EMinder Error] 尝试解析 {meta_filename} 失败: {str(e)}"
            exec_result['stderr'] += error_msg
            print(error_msg)

    # 1.1 处理“不发送邮件”逻辑
    # 如果 json 中 skip_email 为 true，直接返回带 abort_sending 标志的字典
    if script_meta.get("skip_email", False):
        print(f"[EMinder Info] 脚本请求跳过本次邮件发送 (skip_email=True)。")
        return {
            "subject": "Skipped",
            "html": "",
            "attachments": [],
            "abort_sending": True # 这个标志将被 TemplateManager 和 Scheduler 识别
        }

    # 1.2 处理标题
    if script_meta.get("subject"):
        subject = script_meta["subject"]
    else:
        # 使用 UI 模板生成标题
        timestamp = exec_result.get('start_time', 'N/A')
        success_str = "成功" if exec_result['success'] else "失败"
        subject = custom_subject_template.replace("<time>", timestamp)
        subject = subject.replace("<ifsuccess>", success_str)

    # 优先使用脚本配置的正文，否则使用 UI 设置的默认消息
    raw_content = script_meta.get("content", default_message)
    
    # 【核心修正】将内容通过 convert_markdown_to_html 处理，以支持 Markdown 语法
    main_message = convert_markdown_to_html(raw_content)
    
    # 1.4 获取显示控制标志 (默认为 True)
    show_details = script_meta.get("show_execution_details", True)
    show_logs = script_meta.get("show_logs", True)
    show_att_list = script_meta.get("show_attachments_list", True)
    
    # ========================== END: MODIFICATION (需求: Script Config) ============================

    # 3. 处理附件规则 (合并 UI 规则 和 脚本动态规则)
    found_attachments = []
    attachment_report_lines = [] # 用于在HTML中展示

    # 3.1 处理 UI 定义的规则
    if attachment_rules_str:
        rules = [r.strip() for r in attachment_rules_str.split('\n') if r.strip() and not r.strip().startswith('#')]
        
        for rule in rules:
            # 尝试作为 glob 模式处理 (glob 也兼容普通路径)
            # 如果是目录，glob 默认不展开内容，需要我们手动处理
            try:
                # 检查是否是纯目录路径
                if os.path.isdir(rule):
                    # 如果是目录，列出目录下所有文件 (一级深度，不递归，为了安全)
                    dir_files = [os.path.join(rule, f) for f in os.listdir(rule) if os.path.isfile(os.path.join(rule, f))]
                    if dir_files:
                        found_attachments.extend(dir_files)
                        attachment_report_lines.append(f"<li>📂 目录 <code>{rule}</code>: 找到 {len(dir_files)} 个文件</li>")
                    else:
                        attachment_report_lines.append(f"<li>📂 目录 <code>{rule}</code>: 空文件夹或无权限</li>")
                
                else:
                    # 尝试作为 glob 通配符处理
                    matches = glob.glob(rule)
                    if matches:
                        files_only = [m for m in matches if os.path.isfile(m)]
                        found_attachments.extend(files_only)
                        attachment_report_lines.append(f"<li>🔍 规则 <code>{rule}</code>: 匹配到 {len(files_only)} 个文件</li>")
                    else:
                        attachment_report_lines.append(f"<li>⚠️ 规则 <code>{rule}</code>: 未找到任何匹配项</li>")
            
            except Exception as e:
                attachment_report_lines.append(f"<li>❌ 规则 <code>{rule}</code> 处理出错: {str(e)}</li>")

    # ========================== START: MODIFICATION (需求: Script Config Attachments) ==========================
    # 3.2 处理脚本配置文件中指定的额外附件
    script_attachments = script_meta.get("attachments", [])
    if script_attachments:
        count = 0
        for path in script_attachments:
            # 如果是相对路径，相对于工作目录解析
            full_path = path if os.path.isabs(path) else os.path.abspath(os.path.join(abs_work_dir, path))
            
            if os.path.exists(full_path) and os.path.isfile(full_path):
                found_attachments.append(full_path)
                count += 1
            else:
                attachment_report_lines.append(f"<li>❌ 脚本附件 <code>{path}</code>: 文件未找到</li>")
        
        if count > 0:
            attachment_report_lines.append(f"<li>📄 脚本配置指定: 成功添加 {count} 个附件</li>")
    # ========================== END: MODIFICATION (需求: Script Config Attachments) ============================

    # 去重
    found_attachments = sorted(list(set(found_attachments)))

    # --- 构建 HTML 报告 ---
    status_color = "#4CAF50" if exec_result['success'] else "#F44336"
    status_text = "成功" if exec_result['success'] else "失败"
    
    # 将文本中的特殊 HTML 字符转义，并保留换行
    def escape_html(text):
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')

    stdout_html = escape_html(exec_result.get('stdout', ''))
    stderr_html = escape_html(exec_result.get('stderr', ''))

    html_parts = []
    
    # 使用处理后的正文消息 (HTML)
    html_parts.append(f"<div>{main_message}</div>")

    # [控制] 执行详情
    if show_details:
        html_parts.append(f"""
            <h4>执行详情 📊</h4>
            <ul>
                <li><strong>命令:</strong> <code>{command}</code></li>
                <li><strong>工作目录:</strong> <code>{abs_work_dir}</code></li>
                <li><strong>状态:</strong> <span style="color: {status_color}; font-weight: bold;">{status_text} (返回码: {exec_result.get('return_code')})</span></li>
                <li><strong>开始时间:</strong> {exec_result.get('start_time', 'N/A')}</li>
                <li><strong>结束时间:</strong> {exec_result.get('end_time', 'N/A')}</li>
                <li><strong>总耗时:</strong> {exec_result.get('duration_seconds', 'N/A')} 秒</li>
            </ul>""")

    # [控制] 附件报告
    if show_att_list:
        if attachment_report_lines:
            html_parts.append("<h4>📎 附件收集报告</h4>")
            html_parts.append("<ul>" + "".join(attachment_report_lines) + "</ul>")
            if found_attachments:
                 html_parts.append(f"<p><strong>共计发送 {len(found_attachments)} 个文件。</strong></p>")
        elif attachment_rules_str or script_attachments:
            html_parts.append("<h4>📎 附件收集报告</h4><p>未找到任何符合规则的文件。</p>")

    # --- (可选) LLM 总结 ---
    log_for_summary = exec_result.get('stdout') or exec_result.get('stderr')
    if summary_prompt and log_for_summary:
        full_prompt = f"{summary_prompt}\n\n--- 日志开始 ---\n{log_for_summary}\n--- 日志结束 ---"
        summary_result = await llm_service.generate_text(full_prompt)
        
        summary_html = ""
        if summary_result["success"]:
            summary_html = f"<p>{escape_html(summary_result['content'])}</p>"
        else:
            summary_html = f"<p style='color: red;'>总结生成失败: {escape_html(summary_result['content'])}</p>"
            
        html_parts.append(f"<h4>智能日志摘要 📝</h4>{summary_html}")

    # [控制] 日志输出
    if show_logs:
        stdout_html = escape_html(exec_result.get('stdout', ''))
        stderr_html = escape_html(exec_result.get('stderr', ''))
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

    return {
        "subject": subject,
        "html": "".join(html_parts),
        "attachments": found_attachments
    }
# ========================== END: MODIFICATION (Flexible Attachments) ============================


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
    
    # 【异步改造】调用异步的 LLM 服务
    result = await llm_service.generate_text(text_to_process)
    # ========================== END: MODIFICATION ============================
    
    if result["success"]:
        # 处理成功
        subject = f"AI 处理结果 - {text_to_process[:20]}..."
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


# ========================== START: 新增区域 (需求：快速发送Markdown消息) ==========================
# ===================================================================================
# 【模板】: 快速发送消息 (Markdown)
# 设计师注：提供一个极简的接口，让用户快速发送任意Markdown格式的文本消息。
# 适用于需要定时发送通知、简报、思考笔记等场景。
# ===================================================================================

# --- 步骤 1: 定义元数据 ---
quick_message_meta = {
    "display_name": "快速发送消息 (Markdown)",
    "description": "快速发送一段支持Markdown格式的文字消息。系统会自动将Markdown渲染为HTML格式。",
    "fields": [
        {
            "name": "message",
            "label": "消息内容 (支持Markdown格式)",
            "type": "textarea",
            "default": "# 通知标题\n\n## 要点1\n- 内容A\n- 内容B\n\n## 要点2\n> 引用内容\n\n**加粗**、*斜体*等格式均可使用。"
        },
        {
            "name": "custom_subject",
            "label": "邮件主题 (可选)",
            "type": "text",
            "default": "",
            "info": "留空时，系统会自动从消息内容的第一行生成主题"
        }
    ]
}

# --- 步骤 2: 编写模板生成函数 ---
def get_quick_message_template(data: dict) -> dict:
    """
    快速发送消息模板：将用户输入的Markdown文本渲染为HTML并发送。
    支持自定义邮件主题，如果不提供则自动提取消息第一行作为主题。
    """
    message = data.get('message', '').strip()
    custom_subject = data.get('custom_subject', '').strip()
    
    # 健壮性：检查内容是否为空
    if not message:
        return {
            "subject": "错误：消息内容为空",
            "html": "<h4>错误</h4><p>您没有提供任何消息内容。请在'消息内容'字段中输入您要发送的文本。</p>"
        }
    
    # 将Markdown转换为HTML
    html_content = convert_markdown_to_html(message)
    
    # 生成邮件主题
    if custom_subject:
        subject = custom_subject
    else:
        # 自动从消息内容中提取主题
        # 找到第一行非空内容
        lines = [line.strip() for line in message.split('\n') if line.strip()]
        first_line = lines[0] if lines else "消息通知"
        first_line = first_line.lstrip('#').strip()  # 移除标题标记
        subject = f"消息通知 - {first_line}"
        # 限制主题长度，避免过长
        if len(subject) > 80:
            subject = subject[:77] + "..."
    
    return {
        "subject": subject,
        "html": html_content
    }
# ===================================================================================
# ========================== END: 新增区域 (需求：快速发送Markdown消息) ==========================


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
    # ========================== START: MODIFICATION (注册新模板) ==========================
    "quick_message": {
        "meta": quick_message_meta,
        "func": get_quick_message_template
    },
    # ========================== END: MODIFICATION (注册新模板) ============================
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