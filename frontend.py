# frontend.py (已修改)
import os
import gradio as gr
import requests
import datetime
import pandas as pd
import re
import json # <-- 新增导入
from urllib.parse import quote
import argparse

run_port = 10101
if __name__ == "__main__":
    # --- 后端 API 地址 ---
    parser = argparse.ArgumentParser(description="EMinder Frontend Launcher")
    parser.add_argument("--port",type=int,default=10101,help="Port to run the frontend server on (default: 10101)")
    parser.add_argument("--bnport",type=int,default=8421,help="Port to run the backend server on (default: 8421)")
    parser.add_argument("--bnserver",type=str,default="http://127.0.0.1",help="Backend server address (default: http://127.0.0.1)")
    arg = parser.parse_args()

    run_port = getattr(arg, "port")
    backend = getattr(arg, "bnserver")
    backend_port = getattr(arg, "bnport")

    API_BASE_URL = f"{backend}:{backend_port}/api"
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
    TEMPLATES_INFO_URL = f"{API_BASE_URL}/templates/info"
    # 【修改点】API URL 更新
    SUBSCRIBERS_URL = f"{API_BASE_URL}/subscribers"
    SEND_NOW_URL = f"{API_BASE_URL}/send-now"
    SCHEDULE_ONCE_URL = f"{API_BASE_URL}/schedule-once"
    SCHEDULE_CRON_URL = f"{API_BASE_URL}/schedule-cron"
    JOBS_URL = f"{API_BASE_URL}/jobs"

    # --- 全局状态 ---
    # 用于存储从后端获取的模板信息
    TEMPLATES_METADATA = {}
    # 用于在下拉列表中存储 email -> remark_name 的映射
    SUBSCRIBER_CHOICES = []
# --- API 调用函数 ---

def refresh_subscribers_list():
    """获取订阅者列表，并更新DataFrame和所有相关的选择组件"""
    global SUBSCRIBER_CHOICES
    try:
        response = requests.get(SUBSCRIBERS_URL)
        response.raise_for_status()
        subs = response.json().get("subscribers", [])
        
        # 更新全局选择列表
        SUBSCRIBER_CHOICES = [f"{s.get('remark_name', s['email'])} <{s['email']}>" for s in subs]
        
        if not subs:
            return pd.DataFrame(columns=["邮箱地址", "备注名"]), "✅ 暂无订阅者。", gr.update(choices=[], value=None), gr.update(choices=[], value=None), gr.update(choices=[], value=None)
        
        df = pd.DataFrame(subs, columns=["email", "remark_name"])
        df.rename(columns={"email": "邮箱地址", "remark_name": "备注名"}, inplace=True)
        
        msg = f"✅ 订阅列表已于 {datetime.datetime.now().strftime('%H:%M:%S')} 刷新。"
        return df, msg, gr.update(choices=SUBSCRIBER_CHOICES, value=None), gr.update(choices=SUBSCRIBER_CHOICES, value=None), gr.update(choices=SUBSCRIBER_CHOICES, value=None)
    except requests.RequestException as e:
        msg = f"🔴 获取订阅列表失败: {e}"
        gr.Warning(msg)
        return pd.DataFrame(columns=["邮箱地址", "备注名"]), msg, gr.update(choices=[], value=None), gr.update(choices=[], value=None), gr.update(choices=[], value=None)

def handle_add_subscriber(email, remark_name):
    """处理添加或更新订阅者的逻辑"""
    if not email or "@" not in email:
        gr.Warning("请输入有效的邮箱地址！")
        return
    if not remark_name:
        remark_name = email.split('@')[0]
    
    try:
        response = requests.post(SUBSCRIBERS_URL, json={"email": email, "remark_name": remark_name})
        response.raise_for_status()
        msg = response.json().get("message")
        gr.Info(msg)
    except requests.RequestException as e:
        gr.Error(f"操作失败: {e.response.json().get('detail', e)}")

def handle_delete_subscriber(email):
    """处理删除订阅者的逻辑"""
    if not email:
        gr.Warning("请先从列表中选择一个要删除的用户！")
        return
    try:
        encoded_email = quote(email)
        response = requests.delete(f"{SUBSCRIBERS_URL}/{encoded_email}")
        response.raise_for_status()
        msg = response.json().get("message")
        gr.Info(msg)
    except requests.RequestException as e:
        gr.Error(f"删除失败: {e.response.json().get('detail', e)}")

def get_email_from_selection(selection: str) -> str:
    """从下拉框的选择中提取纯邮箱地址"""
    if not selection:
        return ""
    # 正则表达式匹配尖括号内的邮箱
    match = re.search(r'<(.*?)>', selection)
    if match:
        return match.group(1)
    # 如果没有匹配到，说明是用户手动输入的
    return selection

def get_emails_from_selection_list(selections: list[str]) -> list[str]:
    """从多选框的选择列表中提取纯邮箱地址"""
    if not selections: return []
    return [re.search(r'<(.*?)>', s).group(1) for s in selections if re.search(r'<(.*?)>', s)]

def find_selection_from_email(email: str) -> str:
    """【新增】根据纯邮箱地址在全局选择列表中找到对应的完整选项"""
    return next((choice for choice in SUBSCRIBER_CHOICES if f"<{email}>" in choice), email)

def find_selections_from_emails(emails: list[str]) -> list[str]:
    """【新增】根据纯邮箱列表找到对应的完整选项列表"""
    return [find_selection_from_email(email) for email in emails]

def get_jobs_list():
    """从后端获取所有计划任务列表并格式化，健壮地处理空列表情况。"""
    # 步骤 1: 预定义 DataFrame 的列，确保结构一致性。
    columns = ["任务ID", "任务名称", "类型", "下次运行时间", "发送目标"]
    
    try:
        response = requests.get(JOBS_URL)
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        if not jobs:
            return pd.DataFrame([], columns=columns), "✅ 暂无计划中的任务。快去创建一个吧 😊"
        
        formatted_data = []
        for job in jobs:
            receiver = "查看参数"
            job_kwargs = job.get('kwargs', {}) # 安全地获取 kwargs
            job_type = job.get("job_type", "unknown")
            
            if job_type == 'date':
                receiver = job_kwargs.get('receiver_email', 'N/A')
            elif job_type == 'cron':
                receivers_list = job_kwargs.get('receiver_emails', [])
                receiver = f"{len(receivers_list)}个用户" if receivers_list else "无"
            run_time = "N/A"
            # ========================== END: 错误修复区域 ============================
            if job['next_run_time']:
                try:
                    dt_object = datetime.datetime.fromisoformat(job['next_run_time'])
                    run_time = dt_object.strftime('%Y-%m-%d %H:%M:%S %Z')
                except ValueError:
                    run_time = job['next_run_time']
            
            if job_type == 'cron' and job.get('name') == '每日总结 (周期性)':
                receiver = "所有已订阅用户"

            formatted_data.append({
                "任务ID": job['id'],
                "任务名称": job['name'],
                "类型": {"date": "一次性", "cron": "周期性"}.get(job_type, "未知"),
                "下次运行时间": run_time, # <- 使用我们正确处理后的 run_time
                "发送目标": receiver,
            })
        
        df = pd.DataFrame(formatted_data, columns=columns)
        return df, f"✅ 任务列表已于 {datetime.datetime.now().strftime('%H:%M:%S')} 刷新。"
    except requests.RequestException as e:
        msg = f"🔴 获取任务列表失败: {e}"
        gr.Warning(msg)
        # 步骤 5: 在异常情况下，同样返回一个带有正确列的空 DataFrame。
        return pd.DataFrame([], columns=columns), msg

def cancel_job_by_id(job_id_to_cancel: str):
    """根据ID调用后端API取消任务"""
    if not job_id_to_cancel or not job_id_to_cancel.strip():
        gr.Warning("请输入有效的任务ID！")
        return "请输入任务ID。"
    
    try:
        url = f"{JOBS_URL}/{job_id_to_cancel.strip()}"
        response = requests.delete(url)
        response.raise_for_status()
        msg = response.json().get("message", "任务已取消")
        gr.Info(msg)
        return msg
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', '未知错误')
        gr.Warning(f"操作失败: {error_detail}")
        return f"操作失败: {error_detail}"
        
def check_backend_status():
    """检查后端服务状态"""
    try:
        response = requests.get(API_BASE_URL.replace("/api", "/"), timeout=2)
        if response.status_code == 200:
            return "🟢 后端服务正常"
        return f"🟡 后端服务异常 (状态码: {response.status_code})"
    except requests.ConnectionError:
        return "🔴 后端服务未连接"

def load_templates_info():
    """从后端加载模板元数据"""
    global TEMPLATES_METADATA
    try:
        response = requests.get(TEMPLATES_INFO_URL)
        response.raise_for_status()
        TEMPLATES_METADATA = response.json()
        template_names = [v["display_name"] for v in TEMPLATES_METADATA.values()]
        if not template_names:
            return gr.update(choices=["无可用模板"], value=None, interactive=False), "无法加载模板，请检查后端。"
        return gr.update(choices=template_names, value=template_names[0], interactive=True), "模板加载成功！"
    except requests.RequestException as e:
        return gr.update(choices=["加载失败"], value=None, interactive=False), f"无法连接到后端加载模板: {e}"

def get_template_key_from_display_name(display_name):
    """根据显示名称查找模板的内部key"""
    return next((key for key, value in TEMPLATES_METADATA.items() if value["display_name"] == display_name), None)

def get_display_name_from_template_key(key):
    """【新增】根据内部key查找模板的显示名称"""
    return TEMPLATES_METADATA.get(key, {}).get("display_name")

# ========================== START: 修改区域 (需求 ①) ==========================
# DESIGNER'S NOTE:
# `send_or_schedule_email` 函数被重构以支持文件上传。
# - 新增 `attachment_file` 参数，用于接收 Gradio 文件组件的对象。
# - API 调用从 `requests.post(..., json=...)` 改为 `requests.post(..., data=..., files=...)` 以发送 multipart/form-data。
# - `template_data` 字典被序列化为 JSON 字符串后作为表单字段发送。
def send_or_schedule_email(
    action: str, 
    receiver_selection: str, 
    template_choice: str, 
    custom_subject: str, 
    send_at: str, 
    # ========================== START: BUG 修复 ==========================
    # DESIGNER'S NOTE:
    # 修复了由 Traceback 指出的 AttributeError。
    # 当 gr.File(type="filepath") 时，Gradio 返回的是一个字符串路径，而不是一个文件对象。
    # 因此，函数签名中的类型提示虽然是 gr.File，但实际接收到的 `attachment_file` 是 str。
    # 我们将直接使用这个字符串路径，而不是错误的 `attachment_file.name`。
    attachment_files_list: list,
    # ========================== END: BUG 修复 ============================
    *dynamic_field_values
):
    """处理立即发送或单次调度的邮件，支持附件上传。"""
    receiver_email = get_email_from_selection(receiver_selection)
    if not receiver_email or not template_choice:
        return "错误：接收者邮箱和模板类型为必填项。"
    
    template_key = get_template_key_from_display_name(template_choice)
    if not template_key:
        return "错误：无效的模板选择。"

    fields = TEMPLATES_METADATA.get(template_key, {}).get("fields", [])
    template_data = {}
    components_per_field = 2

    # 我们遍历模板元数据中定义的字段 (fields)，
    # 这样可以确保我们只处理当前模板需要的字段。
    for i, field in enumerate(fields):
        # 计算当前字段对应的两个组件值在元组中的起始索引
        base_index = i * components_per_field
        
        field_name = field["name"]
        field_type = field.get("type", "text")

        # 根据字段类型，从正确的位置提取值
        if field_type == "number":
            # 如果字段类型是 'number'，我们取 Number 组件的值。
            # 它的索引是 base_index + 1。
            value = dynamic_field_values[base_index + 1]
        else: # 'text' or 'textarea'
            # 否则，我们取 Textbox 组件的值。
            # 它的索引是 base_index + 0。
            value = dynamic_field_values[base_index]
        
        # 将字段名和正确的值关联起来
        template_data[field_name] = value

    # 准备表单数据
    form_data = {
        "receiver_email": receiver_email,
        "template_type": template_key,
        "template_data_str": json.dumps(template_data),
        "custom_subject": custom_subject or ""
    }
    
    files = {}
    # ========================== START: BUG 修复 ==========================
    # DESIGNER'S NOTE:
    # 这是 `requests` 库发送多个文件的标准方式。
    # 我们构造一个元组列表 `(field_name, file_info_tuple)`。
    # 重要的是，所有文件的 `field_name` 都是相同的 ("attachments")，
    # 这样 FastAPI 才能将它们正确地解析为一个列表。
    files_to_send = []
    if attachment_files_list:
        try:
            for file_path in attachment_files_list:
                file_info = (
                    'attachments', # 字段名
                    (os.path.basename(file_path), open(file_path, "rb"), 'application/octet-stream')
                )
                files_to_send.append(file_info)
        except Exception as e:
            return f"错误：无法打开附件文件。请检查文件是否存在或权限是否正确。详情: {e}"
    # ========================== END: BUG 修复 ============================

    url = ""
    if action == "send_now":
        url = SEND_NOW_URL
    elif action == "schedule_once":
        if not send_at:
            if files and "attachment" in files: files["attachment"][1].close() # 清理
            return "错误：定时发送必须指定发送时间。"
        form_data["send_at_str"] = send_at
        url = SCHEDULE_ONCE_URL
    else:
        if files and "attachment" in files: files["attachment"][1].close() # 清理
        return "错误：未知的操作。"

    try:
        response = requests.post(url, data=form_data, files=files)
        response.raise_for_status()
        if action == "schedule_once":
            gr.Info("任务已成功调度！将自动刷新任务列表。")
        return response.json().get("message", "操作成功！")
    except requests.RequestException as e:
        error_detail = "未知错误"
        try: error_detail = e.response.json().get('detail', e.response.text)
        except: pass
        return f"操作失败: {error_detail}"
    finally:
        # 确保所有打开的文件句柄都被关闭
        if files_to_send:
            for _, file_tuple in files_to_send:
                file_tuple[1].close()
# ========================== END: 修改区域 (需求 ①) ============================


# ... (handle_schedule_cron 和 handle_update_job 保持不变，因为周期性任务不支持上传) ...
def handle_schedule_cron(
    job_name: str, 
    cron_string: str, 
    subscriber_list: list, 
    custom_emails_str: str, 
    template_choice: str, 
    custom_subject: str, # 新增
    *dynamic_field_values
):
    """【修改】新增 custom_subject 参数"""
    if not all([job_name, cron_string, template_choice]):
        gr.Warning("任务名称, Cron表达式 和 邮件模板为必填项。")
        return "操作失败：请填写所有必填项。"
    
    subscriber_emails = get_emails_from_selection_list(subscriber_list)
    custom_emails = [email.strip() for email in custom_emails_str.split(',') if email.strip() and "@" in email.strip()]
    
    all_receiver_emails = sorted(list(set(subscriber_emails + custom_emails)))
    
    if not all_receiver_emails:
        gr.Warning("接收者邮箱列表为空！")
        return "操作失败：必须至少指定一个有效的接收者邮箱。"
        
    template_key = get_template_key_from_display_name(template_choice)
    if not template_key:
        return "错误：无效的模板选择。"

    fields = TEMPLATES_METADATA.get(template_key, {}).get("fields", [])
    template_data = {}
    components_per_field = 2

    for i, field in enumerate(fields):
        base_index = i * components_per_field
        field_name = field["name"]
        field_type = field.get("type", "text")

        if field_type == "number":
            value = dynamic_field_values[base_index + 1]
        else:
            value = dynamic_field_values[base_index]
        template_data[field_name] = value

    payload = {
        "job_name": job_name,
        "cron_string": cron_string,
        "receiver_emails": all_receiver_emails,
        "template_type": template_key,
        "template_data": template_data,
        "custom_subject": custom_subject # 新增
    }

    try:
        response = requests.post(SCHEDULE_CRON_URL, json=payload)
        response.raise_for_status()
        gr.Info("周期任务已成功调度！将自动刷新任务列表。")
        return response.json().get("message", "操作成功！")
    except requests.exceptions.HTTPError as e:
        error_detail = "未知错误"
        try:
            error_detail = e.response.json().get('detail', e.response.text)
        except Exception:
            pass
        gr.Error(f"操作失败: {error_detail}")
        return f"操作失败: {error_detail}"

def handle_update_job(job_id:str, job_type:str, # State
    # Cron fields
    cron_name:str, cron_string:str, cron_subscribers:list, cron_custom:str,
    # Date fields
    date_receiver:str, date_send_at:str,
    # Common fields
    template_choice: str, custom_subject: str, 
    *dynamic_field_values):
    """【新增】处理更新任务的逻辑"""
    if not job_id: return "错误：没有指定要更新的任务ID。"
    template_key = get_template_key_from_display_name(template_choice)
    if not template_key: return "错误：无效的模板选择。"

    fields = TEMPLATES_METADATA.get(template_key, {}).get("fields", [])
    template_data = {}
    components_per_field = 2
    for i, field in enumerate(fields):
        base_index = i * components_per_field
        field_name, field_type = field["name"], field.get("type", "text")
        value = dynamic_field_values[base_index + 1] if field_type == "number" else dynamic_field_values[base_index]
        template_data[field_name] = value

    payload = { "template_type": template_key, "template_data": template_data, "custom_subject": custom_subject }

    if job_type == 'cron':
        subscriber_emails = get_emails_from_selection_list(cron_subscribers)
        custom_emails = [e.strip() for e in cron_custom.split(',') if e.strip() and "@" in e.strip()]
        all_receivers = sorted(list(set(subscriber_emails + custom_emails)))
        if not all_receivers: 
            gr.Warning("接收者列表不能为空！")
            return "错误: 接收者列表不能为空。"
        payload.update({
            "trigger_type": "cron", "job_name": cron_name, "cron_string": cron_string,
            "receiver_emails": all_receivers
        })
    elif job_type == 'date':
        receiver = get_email_from_selection(date_receiver)
        if not receiver:
            gr.Warning("接收者不能为空！")
            return "错误: 接收者不能为空。"
        payload.update({
            "trigger_type": "date", "send_at": date_send_at, "receiver_email": receiver
        })
    else:
        return f"错误：未知的任务类型 '{job_type}'。"

    try:
        response = requests.put(f"{JOBS_URL}/{job_id}", json=payload)
        response.raise_for_status()
        msg = response.json().get("message", "任务更新成功！")
        gr.Info(msg)
        return msg
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', '未知错误')
        gr.Error(f"更新失败: {error_detail}")
        return f"更新失败: {error_detail}"

# --- Gradio 界面构建 ---

with gr.Blocks(theme=gr.themes.Soft(primary_hue="green", secondary_hue="lime"), title="EMinder 控制中心") as demo:
    backend_status_output = gr.Markdown(check_backend_status)
    gr.Markdown("# EMinder 邮件任务控制中心")

    # 【修改1】将两个独立的接收者输入框合并为一个共享组件，并放置在 Tabs 的外部，使其对两个 Tab 可见
    shared_receiver_input = gr.Dropdown(
        label="1. 选择或输入接收者邮箱 (适用于'手动发送'和'定时单次任务')",
        allow_custom_value=True,
        interactive=True
    )

    def create_email_form(is_scheduled: bool, receiver_dropdown: gr.Dropdown):
        # 【修改2】调整标题，因为接收人选择框已移至外部
        gr.Markdown("### 2. 选择邮件模板")
        load_status = gr.Markdown()
        template_dropdown = gr.Dropdown(label="选择邮件模板", choices=["正在加载..."], interactive=False)
        
        # 【新增】自定义标题输入框
        custom_subject_input = gr.Textbox(label="自定义邮件标题 (可选)", info="留空则使用模板默认标题", placeholder="例如：这是一封特别的邮件")

        gr.Markdown("### 3. 填写模板所需信息")
        
        # --- 创建动态表单 ---
        dynamic_form_area = gr.Column()
        with dynamic_form_area:
            form_description = gr.Markdown()
            max_fields = 10
            dynamic_fields_components = []
            for i in range(max_fields):
                with gr.Group(visible=False) as field_group:
                    # 【修正点 #1】为不同类型使用不同组件
                    comp_text = gr.Textbox(label=f"字段{i+1}")
                    comp_num = gr.Number(label=f"字段{i+1}", visible=False)
                dynamic_fields_components.append({"group": field_group, "text": comp_text, "number": comp_num})
        
        all_field_inputs = []
        for comp_dict in dynamic_fields_components:
            all_field_inputs.extend([comp_dict['text'], comp_dict['number']])

        all_field_outputs = [dynamic_form_area, form_description]
        for comp_dict in dynamic_fields_components:
            all_field_outputs.extend([comp_dict['group'], comp_dict['text'], comp_dict['number']])

        def toggle_template_fields(choice):
            updates = []
            template_key = get_template_key_from_display_name(choice)
            if not template_key:
                return [gr.update(visible=False)] * len(all_field_outputs)
            
            meta = TEMPLATES_METADATA[template_key]
            fields = meta.get("fields", [])
            updates.append(gr.update(visible=True))
            updates.append(gr.update(value=f"#### {meta.get('description', '')}"))

            for i in range(max_fields):
                if i < len(fields):
                    field = fields[i]
                    field_type = field.get("type", "text")
                    updates.append(gr.update(visible=True)) # Group
                    if field_type == "number":
                        updates.append(gr.update(visible=False)) # Hide Textbox
                        updates.append(gr.update(visible=True, label=field.get('label'), value=field.get('default'))) # Show Number
                    else: # text or textarea
                        lines = 3 if field_type == "textarea" else 1
                        updates.append(gr.update(visible=True, label=field.get('label'), value=field.get('default'), lines=lines)) # Show Textbox
                        updates.append(gr.update(visible=False)) # Hide Number
                else:
                    updates.extend([gr.update(visible=False)] * 3)
            return updates

        template_dropdown.change(
            fn=toggle_template_fields,
            inputs=template_dropdown,
            outputs=all_field_outputs
        )

        gr.Markdown("### 4. 添加附件 (可选)")
    
        # 状态变量，用于在后台维护一个完整的、累加的文件路径列表
        attachment_state = gr.State([])

        with gr.Row():
            # 用于显示当前已选择的所有附件
            attachment_display = gr.Textbox(
                label="已选择的附件列表", 
                interactive=False, 
                lines=4,
                placeholder="这里将显示您所有已选择的文件..."
            )
        
        with gr.Row():
            # 允许用户选择多个文件的上传器
            file_uploader = gr.File(
                label="点击选择或拖拽文件到此处添加",
                file_count="multiple",
                type="filepath"
            )
            # 清空按钮
            clear_attachments_btn = gr.Button("🗑️ 清空列表")

        def update_attachment_list(current_list, new_files):
            """
            处理文件上传事件，将新文件添加到现有列表中。
            """
            if not new_files:
                return current_list, "\n".join(current_list)
            
            # 合并新旧列表，并去重
            updated_list = sorted(list(set(current_list + new_files)))
            
            # 更新状态变量和显示框
            return updated_list, "\n".join(updated_list)

        def clear_attachment_list():
            """
            清空附件列表。
            """
            return [], ""

        # 事件绑定：当有新文件上传时，调用 update_attachment_list
        file_uploader.upload(
            fn=update_attachment_list,
            inputs=[attachment_state, file_uploader],
            outputs=[attachment_state, attachment_display]
        )

        # 事件绑定：点击清空按钮时，调用 clear_attachment_list
        clear_attachments_btn.click(
            fn=clear_attachment_list,
            outputs=[attachment_state, attachment_display]
        )

        gr.Markdown("### 5. 执行操作")
        
        if is_scheduled:
            now_plus_10_min = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")
            send_at_component = gr.Textbox(label="预定发送时间", value=now_plus_10_min, info="格式: YYYY-MM-DD HH:MM")
            action_button = gr.Button("创建一次性定时任务", variant="primary")
            action_type = gr.State("schedule_once")
        else:
            send_at_component = gr.State(None)
            action_button = gr.Button("立即发送邮件", variant="primary")
            action_type = gr.State("send_now")
        
        output_text = gr.Textbox(label="操作结果", interactive=False)
        action_button.click(
            fn=send_or_schedule_email,
            # 【修改】在 inputs 列表中添加 attachment_component
            inputs=[action_type, receiver_dropdown, template_dropdown, custom_subject_input, send_at_component, attachment_state] + all_field_inputs,
            outputs=output_text
        )
        # 【修改】将 custom_subject_input 和 attachment_component 添加到返回值
        return load_status, template_dropdown, custom_subject_input, attachment_state, action_button, all_field_outputs, toggle_template_fields

    with gr.Tabs() as tabs:
        # --- Tab 1: 订阅管理 ---
        with gr.TabItem("订阅管理", id="subscribe_tab") as tab_subscribe:
            gr.Markdown("## 订阅者管理面板")
            with gr.Row():
                refresh_subs_button = gr.Button("🔄 刷新订阅列表", variant="secondary")
            subs_status_output = gr.Markdown()
            subscribers_dataframe = gr.DataFrame(headers=["邮箱地址", "备注名"], interactive=False, row_count=(10, "dynamic"))
            
            with gr.Group():
                gr.Markdown("### 添加 / 编辑订阅者")
                gr.Markdown("在下方输入信息后点击“添加/更新”。若要编辑，请先在上方表格中**点击选中**一行。")
                sub_email_input = gr.Textbox(label="邮箱地址", placeholder="user@example.com", interactive=True)
                sub_remark_input = gr.Textbox(label="备注名", placeholder="例如：用户A", interactive=True)
                with gr.Row():
                    add_button = gr.Button("➕ 添加/更新", variant="primary")
                    delete_button = gr.Button("🗑️ 删除选中项", variant="stop")
                    clear_button = gr.Button("清空表单")

        with gr.TabItem("手动发送邮件") as tab_manual:
            # 【修改】接收新增的 custom_subject_input 和 attachment_component
            manual_load_status, manual_template_dropdown, manual_custom_subject, manual_attachment, manual_action_button, manual_all_field_outputs, manual_toggle_fn = create_email_form(is_scheduled=False, receiver_dropdown=shared_receiver_input)
        
        with gr.TabItem("定时单次任务") as tab_schedule:
            # 【修改】接收新增的 custom_subject_input 和 attachment_component
            schedule_load_status, schedule_template_dropdown, schedule_custom_subject, schedule_attachment, schedule_action_button, schedule_all_field_outputs, schedule_toggle_fn = create_email_form(is_scheduled=True, receiver_dropdown=shared_receiver_input)
        
        # --- 【新增】Tab 3: 计划周期任务 ---
        with gr.TabItem("计划周期任务", id="cron_tab") as tab_cron:
            gr.Markdown("## 创建周期性邮件发送任务")
            gr.Markdown("通过 [Cron 表达式](https://crontab.guru/) 定义一个重复执行的计划，例如在每个周一上午9点向指定用户发送周报。")
            with gr.Row():
                with gr.Column(scale=2):
                    gr.Markdown("### 1. 定义任务属性")
                    cron_job_name = gr.Textbox(label="任务名称", placeholder="例如：项目组每周一九点周报")
                    cron_expression = gr.Textbox(label="Cron 表达式", placeholder="分 时 日 月 周 (例如: 0 9 * * 1)")
                    
                    gr.Markdown("### 2. 选择接收者")
                    cron_receiver_subscribers = gr.CheckboxGroup(label="从订阅列表中选择 (可多选)")
                    cron_receiver_custom = gr.Textbox(label="添加自定义邮箱", placeholder="多个邮箱请用英文逗号 , 分隔", info="可随时添加不在订阅列表中的临时邮箱。")

                with gr.Column(scale=3):
                    gr.Markdown("### 3. 选择并填写邮件模板")
                    cron_load_status = gr.Markdown()
                    cron_template_dropdown = gr.Dropdown(label="选择邮件模板", choices=["正在加载..."], interactive=False)
                    cron_custom_subject = gr.Textbox(label="自定义邮件标题 (可选)", info="留空则使用模板默认标题")
                    
                    cron_dynamic_form_area = gr.Column()
                    with cron_dynamic_form_area:
                        cron_form_description = gr.Markdown()
                        max_fields_cron = 10
                        cron_dynamic_fields_components = []
                        for i in range(max_fields_cron):
                            with gr.Group(visible=False) as fg:
                                ct = gr.Textbox(label=f"字段{i+1}")
                                cn = gr.Number(label=f"字段{i+1}", visible=False)
                            cron_dynamic_fields_components.append({"group": fg, "text": ct, "number": cn})
                    
                    cron_all_field_inputs = []
                    for comp_dict in cron_dynamic_fields_components:
                        cron_all_field_inputs.extend([comp_dict['text'], comp_dict['number']])

                    cron_all_field_outputs = [cron_dynamic_form_area, cron_form_description]
                    for comp_dict in cron_dynamic_fields_components:
                        cron_all_field_outputs.extend([comp_dict['group'], comp_dict['text'], comp_dict['number']])

                    # 注意: 此函数与 create_email_form 中的 toggle_template_fields 逻辑相同
                    def toggle_cron_template_fields(choice):
                        updates = []
                        template_key = get_template_key_from_display_name(choice)
                        if not template_key:
                            return [gr.update(visible=False)] * len(cron_all_field_outputs)
                        
                        meta = TEMPLATES_METADATA[template_key]
                        fields = meta.get("fields", [])
                        updates.extend([gr.update(visible=True), gr.update(value=f"#### {meta.get('description', '')}")])
                        for i in range(max_fields_cron):
                            if i < len(fields):
                                field = fields[i]
                                f_type, label, default = field.get("type", "text"), field.get('label'), field.get('default')
                                updates.append(gr.update(visible=True))
                                if f_type == "number":
                                    updates.extend([gr.update(visible=False), gr.update(visible=True, label=label, value=default)])
                                else:
                                    lines = 3 if f_type == "textarea" else 1
                                    updates.extend([gr.update(visible=True, label=label, value=default, lines=lines), gr.update(visible=False)])
                            else:
                                updates.extend([gr.update(visible=False)] * 3)
                        return updates

                    cron_template_dropdown.change(
                        fn=toggle_cron_template_fields,
                        inputs=cron_template_dropdown,
                        outputs=cron_all_field_outputs
                    )

            gr.Markdown("### 4. 创建任务")
            with gr.Row():
                create_cron_button = gr.Button("✔️ 创建周期任务", variant="primary")
            cron_output_text = gr.Textbox(label="操作结果", interactive=False)

        with gr.TabItem("📅 计划任务管理", id="jobs_tab") as tab_jobs:
            gr.Markdown("## 查看并管理所有已计划的邮件任务")
            gr.Markdown("在这里，你可以看到所有等待执行的一次性任务和周期性任务，并可以手动取消它们。")
            
            with gr.Row():
                refresh_jobs_button = gr.Button("🔄 刷新任务列表", variant="primary")
            jobs_status_output = gr.Markdown()
            jobs_dataframe = gr.DataFrame(headers=["任务ID", "任务名称", "类型", "下次运行时间", "发送目标"], interactive=False, row_count=(5, "dynamic"), wrap=True)
            
            with gr.Row():
                with gr.Column(scale=2):
                    with gr.Group():
                        gr.Markdown("### 取消任务")
                        job_id_input = gr.Textbox(label="要操作的任务ID (自动填充)", interactive=True)
                        cancel_button = gr.Button("🗑️ 取消指定任务", variant="stop")
                        cancel_status_output = gr.Textbox(label="操作结果", interactive=False)
                with gr.Column(scale=3, visible=False) as edit_job_column:
                     with gr.Group():
                        gr.Markdown("### 📝 编辑任务")
                        edit_job_id_state = gr.State()
                        edit_job_type_state = gr.State()
                        # -- Edit form for CRON jobs
                        with gr.Group(visible=False) as edit_cron_group:
                            edit_cron_name = gr.Textbox(label="任务名称")
                            edit_cron_string = gr.Textbox(label="Cron 表达式")
                            edit_cron_subscribers = gr.CheckboxGroup(label="从订阅列表选择接收者")
                            edit_cron_custom = gr.Textbox(label="添加自定义邮箱")
                        # -- Edit form for DATE jobs
                        with gr.Group(visible=False) as edit_date_group:
                            edit_date_receiver = gr.Dropdown(label="接收者邮箱", allow_custom_value=True)
                            edit_date_send_at = gr.Textbox(label="预定发送时间")
                        # -- Common edit form elements
                        edit_template_dropdown = gr.Dropdown(label="邮件模板")
                        edit_custom_subject = gr.Textbox(label="自定义邮件标题 (可选)")
                        
                        edit_dynamic_form_area = gr.Column()
                        with edit_dynamic_form_area:
                            edit_form_description = gr.Markdown()
                            max_fields_edit = 10
                            edit_dynamic_fields_components = []
                            for i in range(max_fields_edit):
                                with gr.Group(visible=False) as fg:
                                    et = gr.Textbox(label=f"字段{i+1}")
                                    en = gr.Number(label=f"字段{i+1}", visible=False)
                                edit_dynamic_fields_components.append({"group": fg, "text": et, "number": en})
                        
                        edit_all_field_inputs = [c for d in edit_dynamic_fields_components for c in (d['text'], d['number'])]
                        edit_all_field_outputs = [edit_dynamic_form_area, edit_form_description] + [c for d in edit_dynamic_fields_components for c in d.values()]
                        
                        # Link template dropdown to dynamic fields visibility
                        edit_template_dropdown.change(fn=toggle_cron_template_fields, inputs=edit_template_dropdown, outputs=edit_all_field_outputs)
                        
                        with gr.Row():
                            update_button = gr.Button("✔️ 更新任务", variant="primary")
                            cancel_edit_button = gr.Button("❌ 取消编辑")
                        update_status_output = gr.Textbox(label="更新结果", interactive=False)

    # --- 事件绑定 ---
    
    # 订阅管理 Tab
    def on_select_subscriber(df: pd.DataFrame, evt: gr.SelectData):
        if evt.index is None: return "", ""
        row_index = evt.index[0]
        selected_row = df.iloc[row_index]
        email = selected_row['邮箱地址']
        remark = selected_row['备注名']
        return email, remark
    subscribers_dataframe.select(fn=on_select_subscriber, inputs=[subscribers_dataframe], outputs=[sub_email_input, sub_remark_input], trigger_mode='once')
    
    # 【修改】将 cron_receiver_subscribers 添加到刷新列表
    add_button.click(fn=handle_add_subscriber, inputs=[sub_email_input, sub_remark_input]).then(
        fn=refresh_subscribers_list, outputs=[subscribers_dataframe, subs_status_output, shared_receiver_input, cron_receiver_subscribers, edit_cron_subscribers]
    )
    
    delete_button.click(fn=handle_delete_subscriber, inputs=[sub_email_input]).then(
        fn=refresh_subscribers_list, outputs=[subscribers_dataframe, subs_status_output, shared_receiver_input, cron_receiver_subscribers]
    )
    
    def clear_inputs(): return "", ""
    clear_button.click(fn=clear_inputs, outputs=[sub_email_input, sub_remark_input])

    refresh_subs_button.click(
        fn=refresh_subscribers_list, outputs=[subscribers_dataframe, subs_status_output, shared_receiver_input, cron_receiver_subscribers]
    )

    # 邮件发送 Tab
    demo.load(fn=load_templates_info, outputs=[manual_template_dropdown, manual_load_status]).then(fn=manual_toggle_fn, inputs=manual_template_dropdown, outputs=manual_all_field_outputs)
    demo.load(fn=load_templates_info, outputs=[schedule_template_dropdown, schedule_load_status]).then(fn=schedule_toggle_fn, inputs=schedule_template_dropdown, outputs=schedule_all_field_outputs)
    demo.load(fn=load_templates_info, outputs=[cron_template_dropdown, cron_load_status]).then(fn=toggle_cron_template_fields, inputs=cron_template_dropdown, outputs=cron_all_field_outputs)
    
    # 全局加载
    demo.load(fn=refresh_subscribers_list, outputs=[subscribers_dataframe, subs_status_output, shared_receiver_input, cron_receiver_subscribers])

    # 计划任务 Tab
    tab_jobs.select(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])
    refresh_jobs_button.click(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])
    cancel_button.click(fn=cancel_job_by_id, inputs=[job_id_input], outputs=[cancel_status_output]).then(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])
    
    # 【核心新增逻辑】点击任务列表，填充并显示编辑区域
    def on_select_job(df_input: any, evt: gr.SelectData):
        """
        【已修复】当用户在任务列表中选择一行时触发。
        此函数现在会返回一个固定长度（45）的更新对象列表，以匹配 outputs 的数量，从而修复 ValueError。
        """
        # 定义输出组件的总数，用于在异常或未选中情况下返回正确数量的更新
        TOTAL_OUTPUTS = 45 # 13 (fixed) + 2 (dynamic area/desc) + 30 (dynamic fields)
        # ========================== START: 错误修复区域 ==========================
        # MODIFIED: 区分处理 DataFrame 对象和原始字典，以避免 ValueError。
        is_dataframe = isinstance(df_input, pd.DataFrame)
        
        # 1. 根据不同类型，用正确的方式判断输入是否为空
        if (is_dataframe and df_input.empty) or \
           (not is_dataframe and (not df_input or not df_input.get('data'))):
            return [gr.update()] * TOTAL_OUTPUTS

        # 2. 确保我们有一个可以操作的 DataFrame 对象 'df'
        if is_dataframe:
            df = df_input
        else:
            # 如果是原始数据，手动创建 DataFrame
            df = pd.DataFrame(df_input['data'], columns=df_input['headers'])
        # ========================== END: 错误修复区域 ============================

        # 如果没有选中任何行 (例如点击了表头)，也直接返回
        # 如果没有选中任何行，隐藏编辑区域并返回正确数量的更新对象
        if not isinstance(df_input, pd.DataFrame) or df_input.empty or evt.index is None:
            # 返回45个 "no change" 更新
            return [gr.update()] * TOTAL_OUTPUTS

        job_id = df.iloc[evt.index[0], 0]
        
        try:
            response = requests.get(f"{JOBS_URL}/{job_id}")
            response.raise_for_status()
            job = response.json().get("job")

            # ========================== START: 错误修复区域 ==========================
            # MODIFIED: 安全地处理任务参数(args)，防止因参数列表长度不足而崩溃。
            # 内置的“每日总结”任务没有参数，因此在这里需要特殊处理。
            job_args = job.get("args", [])
            if not all(k in job for k in ['template_type', 'template_data']):
                gr.Info(f"任务 '{job.get('name')}' 是一个内置的系统任务或参数不完整，不支持编辑。但你仍然可以取消它。")
                # 必须为所有45个输出组件返回一个更新。
                # 我们只更新 Job ID 输入框，并确保编辑区域是隐藏的。
                updates = [gr.update()] * TOTAL_OUTPUTS  # Start with "no change" for all
                updates[0] = gr.update(visible=False)    # Hide edit_job_column
                updates[1] = job_id                      # Populate job_id_input for cancellation
                return updates
            # ========================== END: 错误修复区域 ============================

            # --- 步骤 1: 初始化所有13个固定组件的返回值 ---
            edit_job_column_update = gr.update(visible=True)
            job_id_input_update = job_id
            edit_job_id_state_update = job_id
            edit_job_type_state_update = job["trigger_type"]
            
            # 从现在已确认安全的 job_args 列表中解包参数
            template_key = job.get("template_type")
            template_data = job.get("template_data", {})
            custom_subject = job.get("custom_subject")
            
            template_display_name = get_display_name_from_template_key(template_key)
            edit_template_dropdown_update = gr.update(value=template_display_name)
            edit_custom_subject_update = custom_subject

            # 首先将所有 cron 和 date 相关的字段重置/隐藏
            edit_cron_group_update = gr.update(visible=False)
            edit_date_group_update = gr.update(visible=False)
            edit_cron_name_update = ""
            edit_cron_string_update = ""
            edit_cron_subscribers_update = gr.update(value=[])
            edit_date_receiver_update = gr.update(value=None)
            edit_date_send_at_update = ""

            # --- 步骤 2: 根据任务类型填充特定字段 ---
            if job["trigger_type"] == 'cron':
                receivers = find_selections_from_emails(job.get("receiver_emails", []))
                edit_cron_group_update = gr.update(visible=True)
                edit_cron_name_update = job["name"]
                edit_cron_string_update = job["cron_string"]
                edit_cron_subscribers_update = gr.update(value=receivers)
            elif job["trigger_type"] == 'date':
                receiver = find_selection_from_email(job.get("receiver_email", ""))
                edit_date_group_update = gr.update(visible=True)
                edit_date_receiver_update = gr.update(value=receiver)
                edit_date_send_at_update = job["run_date"]
            
            # --- 步骤 3: 准备动态表单区域的2个更新 ---
            meta = TEMPLATES_METADATA.get(template_key, {})
            edit_dynamic_form_area_update = gr.update(visible=True)
            edit_form_description_update = gr.update(value=f"#### {meta.get('description', '')}")

            # --- 步骤 4: 准备动态表单字段的30个更新 ---
            dynamic_field_updates = []
            fields = meta.get("fields", [])
            for i in range(max_fields_edit):
                if i < len(fields):
                    field_meta = fields[i]
                    name = field_meta["name"]
                    f_type = field_meta.get("type", "text")
                    value = template_data.get(name, field_meta.get("default"))
                    
                    dynamic_field_updates.append(gr.update(visible=True))  # Group is visible
                    if f_type == "number":
                        dynamic_field_updates.append(gr.update(visible=False, value=""))      # Textbox is hidden and cleared
                        dynamic_field_updates.append(gr.update(visible=True, value=value))      # Number is visible with value
                    else: # 'text' or 'textarea'
                        lines = 3 if f_type == "textarea" else 1
                        dynamic_field_updates.append(gr.update(visible=True, value=value, lines=lines)) # Textbox is visible
                        dynamic_field_updates.append(gr.update(visible=False, value=None))    # Number is hidden and cleared
                else:
                    # Hide and clear unused field groups
                    dynamic_field_updates.extend([gr.update(visible=False), gr.update(value=""), gr.update(value=None)])

            # --- 步骤 5: 按正确顺序组装所有45个返回值 ---
            return [
                # 13个固定组件
                edit_job_column_update, job_id_input_update, edit_job_id_state_update, edit_job_type_state_update,
                edit_template_dropdown_update, edit_custom_subject_update,
                edit_cron_group_update, edit_date_group_update,
                edit_cron_name_update, edit_cron_string_update, edit_cron_subscribers_update,
                edit_date_receiver_update, edit_date_send_at_update,
                # 2个动态表单容器组件
                edit_dynamic_form_area_update, edit_form_description_update,
            ] + dynamic_field_updates # 30个动态字段组件

        except requests.RequestException as e:
            gr.Error(f"获取任务详情失败: {e}")
            return [gr.update()] * TOTAL_OUTPUTS
        except Exception as e:
            gr.Error(f"处理点击事件时发生未知错误: {e}")
            return [gr.update()] * TOTAL_OUTPUTS

    jobs_dataframe.select(
        fn=on_select_job, inputs=[jobs_dataframe],
        outputs=[
            edit_job_column, job_id_input, edit_job_id_state, edit_job_type_state, 
            edit_template_dropdown, edit_custom_subject,
            edit_cron_group, edit_date_group, edit_cron_name, edit_cron_string, edit_cron_subscribers,
            edit_date_receiver, edit_date_send_at
        ] + edit_all_field_outputs
    )

    cancel_edit_button.click(lambda: gr.update(visible=False), outputs=edit_job_column)
    
    update_button.click(
        fn=handle_update_job,
        inputs=[edit_job_id_state, edit_job_type_state, edit_cron_name, edit_cron_string, edit_cron_subscribers, edit_cron_custom,
                edit_date_receiver, edit_date_send_at, edit_template_dropdown, edit_custom_subject] + edit_all_field_inputs,
        outputs=update_status_output
    ).then(
        fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output]
    ).then(
        lambda: gr.update(visible=False), outputs=edit_job_column
    )
    
    # 任务创建成功后跳转到任务管理并刷新
    schedule_action_button.click(lambda: gr.update(selected=tab_jobs.id), outputs=tabs).then(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])
    create_cron_button.click(
        fn=handle_schedule_cron,
        # 【修改】在 inputs 列表中添加 cron_custom_subject
        inputs=[cron_job_name, cron_expression, cron_receiver_subscribers, cron_receiver_custom, cron_template_dropdown, cron_custom_subject] + cron_all_field_inputs,
        outputs=cron_output_text
    ).then(lambda: gr.update(selected=tab_jobs.id), outputs=tabs).then(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])
    
    # Demo加载时的初始化操作
    def initial_load():
        # 并发执行模板加载和订阅者刷新
        templates_update, templates_status = load_templates_info()
        subs_df, subs_status, shared_dd_update, cron_cb_update, edit_cb_update = refresh_subscribers_list()
        
        # 将更新应用到所有相关组件
        return {
            manual_template_dropdown: templates_update, manual_load_status: templates_status,
            schedule_template_dropdown: templates_update, schedule_load_status: templates_status,
            cron_template_dropdown: templates_update, cron_load_status: templates_status,
            edit_template_dropdown: templates_update,
            subscribers_dataframe: subs_df, subs_status_output: subs_status,
            shared_receiver_input: shared_dd_update,
            edit_date_receiver: gr.update(choices=SUBSCRIBER_CHOICES), # 更新编辑区域的下拉框
            cron_receiver_subscribers: cron_cb_update,
            edit_cron_subscribers: gr.update(choices=SUBSCRIBER_CHOICES)
        }

    # Gradio 2.0: Use a dictionary for component updates in demo.load
    all_load_outputs = [
        manual_template_dropdown, manual_load_status, schedule_template_dropdown, schedule_load_status,
        cron_template_dropdown, cron_load_status, edit_template_dropdown,
        subscribers_dataframe, subs_status_output, shared_receiver_input, edit_date_receiver,
        cron_receiver_subscribers, edit_cron_subscribers
    ]
    demo.load(
        fn=initial_load,
        outputs=all_load_outputs
    ).then(
        fn=manual_toggle_fn, inputs=manual_template_dropdown, outputs=manual_all_field_outputs
    ).then(
        fn=schedule_toggle_fn, inputs=schedule_template_dropdown, outputs=schedule_all_field_outputs
    ).then(
        fn=toggle_cron_template_fields, inputs=cron_template_dropdown, outputs=cron_all_field_outputs
    )


if __name__ == "__main__":
    print("EMinder 前端控制中心即将启动...")
    demo.launch(server_name="0.0.0.0", server_port=run_port, inbrowser=True)