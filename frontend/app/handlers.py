# frontend/app/handlers.py
# ========================== START: MODIFICATION (Feature Addition) ==========================
# DESIGNER'S NOTE:
# This file is the "controller" layer. 
#
# CHANGES:
# 1. Added cancel modal handlers: `ask_confirm_cancel_job`, `execute_cancel_job`, `cancel_cancel_op`.
#    These manage the visibility of the new 'confirmation_row' in UI.
# 2. Refactored `on_select_job`:
#    - Now constructs the return list explicitly by index/order to prevent data mismatch.
#    - Added `gr.Info` to give immediate visual feedback (solving the "lag" feeling).
#    - Ensured types are handled correctly.

import gradio as gr
import pandas as pd
import datetime
import re
import json
import requests

from . import api_client
from . import state
from .config import config

# --- UI Logic & Helper Functions ---

def get_email_from_selection(selection: str) -> str:
    """Extracts the pure email address from a dropdown selection string."""
    if not selection: return ""
    match = re.search(r'<(.*?)>', selection)
    return match.group(1) if match else selection

def get_emails_from_selection_list(selections: list[str]) -> list[str]:
    """Extracts pure email addresses from a multi-select list."""
    if not selections: return []
    return [re.search(r'<(.*?)>', s).group(1) for s in selections if re.search(r'<(.*?)>', s)]

def find_selection_from_email(email: str) -> str:
    """Finds the full dropdown choice string from a pure email address."""
    # 确保 state.SUBSCRIBER_CHOICES 是最新的
    if not state.SUBSCRIBER_CHOICES:
        # 如果全局状态为空，尝试从后端获取一次
        try:
            subs = api_client.get_subscribers()
            state.SUBSCRIBER_CHOICES = [f"{s.get('remark_name', s['email'])} <{s['email']}>" for s in subs]
        except:
             return email # 如果获取失败，返回原始 email
    return next((choice for choice in state.SUBSCRIBER_CHOICES if f"<{email}>" in choice), email)

def find_selections_from_emails(emails: list[str]) -> list[str]:
    """Finds a list of full dropdown choice strings from a list of pure emails."""
    return [find_selection_from_email(email) for email in emails]

def get_template_key_from_display_name(display_name):
    """Finds a template's internal key from its display name."""
    return next((k for k, v in state.TEMPLATES_METADATA.items() if v["display_name"] == display_name), None)

def get_display_name_from_template_key(key):
    """Finds a template's display name from its internal key."""
    return state.TEMPLATES_METADATA.get(key, {}).get("display_name")

def navigate_on_success(message: str):
    """If the operation message indicates success, return a Gradio update to switch to the jobs tab."""
    if message and "成功调度" in message:
        return gr.update(selected="jobs_tab")
    return gr.update()

# --- Gradio Callback Handlers ---

def check_backend_status():
    """Callback to check backend status on load."""
    return api_client.check_backend()

def load_templates_info():
    """Callback to load template info from the backend and update the global state."""
    try:
        state.TEMPLATES_METADATA = api_client.get_templates_info()
        template_names = [v["display_name"] for v in state.TEMPLATES_METADATA.values()]
        if not template_names:
            fail_update = gr.update(choices=["无可用模板"], value=None, interactive=False)
            error_message = "无法加载模板，请检查后端。"
            return [fail_update, error_message, fail_update, error_message, fail_update, error_message, fail_update]

        success_update = gr.update(choices=template_names, value=template_names[0], interactive=True)
        status_message = "模板加载成功！"
        return [
            success_update, status_message,  # Manual tab
            success_update, status_message,  # Schedule tab
            success_update, status_message,  # Cron tab
            success_update                   # Edit Job form
        ]
        
    except requests.RequestException as e:
        fail_update = gr.update(choices=["加载失败"], value=None, interactive=False)
        error_message = f"无法连接到后端加载模板: {e}"
        return [fail_update, error_message, fail_update, error_message, fail_update, error_message, fail_update]


def refresh_subscribers_list():
    """Callback to refresh the subscriber list and all dependent UI components."""
    try:
        subs = api_client.get_subscribers()
        state.SUBSCRIBER_CHOICES = [f"{s.get('remark_name', s['email'])} <{s['email']}>" for s in subs]
        
        df = pd.DataFrame(subs, columns=["email", "remark_name"]).rename(columns={"email": "邮箱地址", "remark_name": "备注名"}) if subs else pd.DataFrame(columns=["邮箱地址", "备注名"])
        msg = f"✅ 订阅列表已于 {datetime.datetime.now().strftime('%H:%M:%S')} 刷新。"
        
        subscriber_list_update = gr.update(choices=state.SUBSCRIBER_CHOICES, value=None)
        return df, msg, subscriber_list_update, subscriber_list_update, subscriber_list_update, subscriber_list_update, subscriber_list_update

    except requests.RequestException as e:
        msg = f"🔴 获取订阅列表失败: {e}"
        gr.Warning(msg)
        return pd.DataFrame(columns=["邮箱地址", "备注名"]), msg, gr.update(choices=[], value=None), gr.update(choices=[], value=None), gr.update(choices=[], value=None)

def handle_add_subscriber(email, remark_name):
    """Callback for adding or updating a subscriber."""
    if not email or "@" not in email:
        gr.Warning("请输入有效的邮箱地址！")
        return
    if not remark_name:
        remark_name = email.split('@')[0]
    
    try:
        response = api_client.add_subscriber(email, remark_name)
        gr.Info(response.get("message"))
    except requests.RequestException as e:
        gr.Error(f"操作失败: {e.response.json().get('detail', e)}")

def handle_delete_subscriber(email):
    """Callback for deleting a subscriber."""
    if not email:
        gr.Warning("请先从列表中选择一个要删除的用户！")
        return
    try:
        response = api_client.delete_subscriber(email)
        gr.Info(response.get("message"))
    except requests.RequestException as e:
        gr.Error(f"删除失败: {e.response.json().get('detail', e)}")

def get_jobs_list():
    """Callback to fetch and format the list of scheduled jobs."""
    columns = ["任务ID", "任务名称", "类型", "下次运行时间", "发送目标"]
    try:
        jobs = api_client.get_jobs()
        if not jobs:
            return pd.DataFrame([], columns=columns), "✅ 暂无计划中的任务。"
        
        formatted_data = []
        for job in jobs:
            job_kwargs = job.get('kwargs', {})
            job_type = job.get("job_type", "unknown")
            receiver = "查看参数"
            
            if job_type == 'date':
                receiver = job_kwargs.get('receiver_email', 'N/A')
            elif job_type == 'cron':
                receivers_list = job_kwargs.get('receiver_emails', [])
                receiver = f"{len(receivers_list)}个用户" if receivers_list else "无"

            run_time = "N/A"
            if job['next_run_time']:
                try:
                    # Handle timezone-aware ISO format from backend
                    dt_object = datetime.datetime.fromisoformat(job['next_run_time'].replace('Z', '+00:00'))
                    run_time = dt_object.strftime('%Y-%m-%d %H:%M:%S %Z')
                except (ValueError, TypeError):
                    run_time = job['next_run_time']
            
            formatted_data.append({
                "任务ID": job['id'], "任务名称": job['name'],
                "类型": {"date": "一次性", "cron": "周期性"}.get(job_type, "未知"),
                "下次运行时间": run_time, "发送目标": receiver,
            })
        
        df = pd.DataFrame(formatted_data, columns=columns)
        return df, f"✅ 任务列表已于 {datetime.datetime.now().strftime('%H:%M:%S')} 刷新。"
    except requests.RequestException as e:
        msg = f"🔴 获取任务列表失败: {e}"
        gr.Warning(msg)
        return pd.DataFrame([], columns=columns), msg

# ========================== START: MODIFICATION (Fix Cancel UI) ==========================
def ask_confirm_cancel_job(job_id_to_cancel: str):
    """
    Called when user clicks "Cancel Task".
    Hides default buttons, shows confirm buttons.
    """
    if not job_id_to_cancel or not job_id_to_cancel.strip():
        gr.Warning("请先从列表中选择一个任务！")
        return gr.update(), gr.update()
    
    # Show confirmation row, Hide default row
    return gr.update(visible=False), gr.update(visible=True)

def cancel_cancel_op():
    """Called when user clicks "No/Cancel" in the confirmation row."""
    # Show default row, Hide confirmation row
    return gr.update(visible=True), gr.update(visible=False)

def execute_cancel_job(job_id_to_cancel: str):
    """Called when user clicks "Yes" to confirm cancellation."""
    if not job_id_to_cancel: return "未选择ID", gr.update(visible=True), gr.update(visible=False)

    try:
        response = api_client.cancel_job(job_id_to_cancel)
        msg = response.get("message", "任务已取消")
        gr.Info(msg)
        # Restore buttons to default state
        return msg, gr.update(visible=True), gr.update(visible=False)
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', '未知错误')
        gr.Warning(f"操作失败: {error_detail}")
        return f"操作失败: {error_detail}", gr.update(visible=True), gr.update(visible=False)
# ========================== END: MODIFICATION ============================

def send_or_schedule_email(action, receiver_selection, template_choice, custom_subject, send_at, silent_run, attachment_files_list, *dynamic_field_values):
    """Callback to handle both 'send now' and 'schedule once' actions."""
    receiver_email = get_email_from_selection(receiver_selection)
    if not receiver_email or not template_choice:
        gr.Warning("错误：接收者邮箱和模板类型为必填项。")
        return "错误：接收者邮箱和模板类型为必填项。"
    
    template_key = get_template_key_from_display_name(template_choice)
    if not template_key: return "错误：无效的模板选择。"

    fields = state.TEMPLATES_METADATA.get(template_key, {}).get("fields", [])
    template_data = {field["name"]: dynamic_field_values[i*2+1] if field.get("type") == "number" else dynamic_field_values[i*2] for i, field in enumerate(fields)}

    form_data = {
        "receiver_email": receiver_email, "template_type": template_key,
        "template_data_str": json.dumps(template_data), "custom_subject": custom_subject or "",
        "silent_run": silent_run
    }
    
    url = ""
    if action == "send_now":
        url = config.SEND_NOW_URL
    elif action == "schedule_once":
        if not send_at: return "错误：定时发送必须指定发送时间。"
        form_data["send_at_str"] = send_at
        url = config.SCHEDULE_ONCE_URL
    else:
        return "错误：未知的操作。"

    try:
        response = api_client.post_email_request(url, form_data, attachment_files_list)
        message = response.get("message", "操作成功！")
        if action == "schedule_once":
            gr.Info("任务已成功调度！将自动跳转并刷新任务列表。")
        return message
    except (requests.RequestException, IOError) as e:
        error_detail = str(e)
        if isinstance(e, requests.RequestException) and e.response is not None:
            try:
                error_detail = e.response.json().get('detail', e.response.text)
            except json.JSONDecodeError:
                error_detail = e.response.text
        gr.Error(f"操作失败: {error_detail}")
        return f"操作失败: {error_detail}"

def handle_schedule_cron(job_name, cron_string, subscriber_list, custom_emails_str, template_choice, custom_subject, silent_run, *dynamic_field_values):
    """Callback to schedule a recurring cron job."""
    if not all([job_name, cron_string, template_choice]):
        gr.Warning("任务名称, Cron表达式 和 邮件模板为必填项。")
        return "操作失败：请填写所有必填项。"
    
    subscriber_emails = get_emails_from_selection_list(subscriber_list)
    custom_emails = [e.strip() for e in custom_emails_str.split(',') if e.strip() and "@" in e.strip()]
    all_receiver_emails = sorted(list(set(subscriber_emails + custom_emails)))
    if not all_receiver_emails:
        gr.Warning("接收者邮箱列表为空！")
        return "操作失败：必须至少指定一个有效的接收者邮箱。"
        
    template_key = get_template_key_from_display_name(template_choice)
    if not template_key: return "错误：无效的模板选择。"

    fields = state.TEMPLATES_METADATA.get(template_key, {}).get("fields", [])
    template_data = {field["name"]: dynamic_field_values[i*2+1] if field.get("type") == "number" else dynamic_field_values[i*2] for i, field in enumerate(fields)}
    
    payload = {
        "job_name": job_name, "cron_string": cron_string, "receiver_emails": all_receiver_emails,
        "template_type": template_key, "template_data": template_data, "custom_subject": custom_subject,
        "silent_run": silent_run
    }

    try:
        response = api_client.post_cron_job(payload)
        message = response.get("message", "操作成功！")
        gr.Info("周期任务已成功调度！将自动跳转并刷新任务列表。")
        return message
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', e.response.text)
        gr.Error(f"操作失败: {error_detail}")
        return f"操作失败: {error_detail}"

def handle_update_job(job_id, job_type, cron_name, cron_string, cron_subscribers, cron_custom, date_receiver, date_send_at, template_choice, custom_subject, silent_run, *dynamic_field_values):
    """Callback to update an existing scheduled job."""
    if not job_id: return "错误：没有指定要更新的任务ID。"
    template_key = get_template_key_from_display_name(template_choice)
    if not template_key: return "错误：无效的模板选择。"

    fields = state.TEMPLATES_METADATA.get(template_key, {}).get("fields", [])
    template_data = {field["name"]: dynamic_field_values[i*2+1] if field.get("type") == "number" else dynamic_field_values[i*2] for i, field in enumerate(fields)}
    
    payload = { "template_type": template_key, "template_data": template_data, "custom_subject": custom_subject,
               "silent_run": silent_run
              }

    if job_type == 'cron':
        emails = get_emails_from_selection_list(cron_subscribers)
        custom = [e.strip() for e in cron_custom.split(',') if e.strip() and "@" in e.strip()]
        receivers = sorted(list(set(emails + custom)))
        if not receivers: return "错误: 接收者列表不能为空。"
        payload.update({"trigger_type": "cron", "job_name": cron_name, "cron_string": cron_string, "receiver_emails": receivers})
    elif job_type == 'date':
        receiver = get_email_from_selection(date_receiver)
        if not receiver: return "错误: 接收者不能为空。"
        payload.update({"trigger_type": "date", "send_at": date_send_at, "receiver_email": receiver})
    else:
        return f"错误：未知的任务类型 '{job_type}'。"

    try:
        response = api_client.update_job(job_id, payload)
        msg = response.get("message", "任务更新成功！")
        gr.Info(msg)
        return msg
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', '未知错误')
        gr.Error(f"更新失败: {error_detail}")
        return f"更新失败: {error_detail}"

def handle_run_job_now(job_id_to_run: str):
    """Callback to trigger a job to run immediately."""
    if not job_id_to_run or not job_id_to_run.strip():
        gr.Warning("无法运行：没有提供任务ID。")
        return "无法运行：没有提供任务ID。"
    try:
        response = api_client.run_job_now(job_id_to_run)
        msg = response.get("message", "任务已触发执行。")
        gr.Info(msg)
        return msg
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', e.response.text)
        gr.Warning(f"操作失败: {error_detail}")
        return f"操作失败: {error_detail}"
        
def on_select_subscriber(df: pd.DataFrame, evt: gr.SelectData):
    """Callback for when a row is selected in the subscriber dataframe."""
    if evt.index is None: return "", ""
    email = df.iloc[evt.index[0]]['邮箱地址']
    remark = df.iloc[evt.index[0]]['备注名']
    return email, remark

def clear_subscriber_inputs():
    """Callback to clear subscriber input fields."""
    return "", ""

# ========================== START: MODIFICATION (BUG FIX) ==========================
# DESIGNER'S NOTE:
# 修复了一个 TypeError，该错误导致所有模板的动态字段无法显示。
# 错误原因: 在 main.py 中，Gradio 事件通过 functools.partial 将 `max_fields` (整数) 作为第一个参数传递，
# 而将下拉框的 `choice` (字符串) 作为第二个参数传递。
# 原函数签名 `def toggle_template_fields(choice, max_fields)` 导致参数错位，
# `max_fields` 变量接收了字符串，从而在 `range(max_fields)` 时引发 TypeError。
# 解决方案: 交换函数签名的参数顺序为 `def toggle_template_fields(max_fields, choice)`，
# 使其与实际的参数传递顺序一致。同时增加了对 `max_fields` 的类型转换以增强代码健壮性。
def toggle_template_fields(max_fields, choice):
    """Callback to dynamically show/hide form fields based on template selection."""
    
    # 为了代码健壮性，对 max_fields 进行显式类型转换
    try:
        max_fields_int = int(max_fields)
    except (ValueError, TypeError):
        # 如果转换失败 (虽然理论上不应该发生)，提供一个安全的回退值并记录警告
        gr.Warning(f"处理模板字段时出现内部错误。预期的字段数 '{max_fields}' 无效。")
        max_fields_int = 0 # 设置为0将安全地隐藏所有字段
        
    template_key = get_template_key_from_display_name(choice)
    # Start with a default set of "hidden" updates for all components
    updates = [gr.update(visible=False), gr.update(value="")]  # For area and description
    # 使用转换后的整数
    for _ in range(max_fields_int):
        updates.extend([gr.update(visible=False), gr.update(value=""), gr.update(value=None)])

    if not template_key or template_key not in state.TEMPLATES_METADATA:
        # Hide everything if template is not found
        updates = [gr.update(visible=False), gr.update(value="")]
        updates.extend([gr.update(visible=False)] * max_fields_int * 3) # group, text, number
        return updates

    meta = state.TEMPLATES_METADATA[template_key]
    fields = meta.get("fields", [])
    
    updates[0] = gr.update(visible=bool(fields))
    updates[1] = gr.update(value=f"#### {meta.get('description', '')}")

    for i in range(max_fields_int):
        base_idx = 2 + i * 3
        if i < len(fields):
            field = fields[i]
            f_type, label, default = field.get("type", "text"), field.get('label'), field.get('default')
            updates[base_idx] = gr.update(visible=True)  # Group
            if f_type == "number":
                updates[base_idx + 1] = gr.update(visible=False) # Hide Textbox
                updates[base_idx + 2] = gr.update(visible=True, label=label, value=default) # Show Number
            else: # text or textarea
                lines = 3 if f_type == "textarea" else 1
                updates[base_idx + 1] = gr.update(visible=True, label=label, value=default, lines=lines) # Show Textbox
                updates[base_idx + 2] = gr.update(visible=False) # Hide Number
    return updates

def on_select_job(df_input: pd.DataFrame, evt: gr.SelectData):
    """
    Callback for when a row is selected in the jobs dataframe.
    Populates the edit form.
    CRITICAL FIX: 
    1. Returns explicit list to avoid dictionary ordering issues.
    2. Uses gr.Info to give user immediate feedback that selection worked.
    """
    # Total outputs = 14 fixed fields + 2 dynamic areas + (10 * 3 fields) = 46 items
    TOTAL_EDIT_OUTPUTS = 14 + 2 + (10 * 3)
    
    if df_input.empty or evt.index is None:
        return [gr.update()] * TOTAL_EDIT_OUTPUTS

    job_id = df_input.iloc[evt.index[0]]['任务ID']
    
    try:
        job = api_client.get_job_details(job_id)

        if not all(k in job for k in ['template_type']):
            gr.Info(f"任务 '{job.get('name')}' 是内置任务或参数不完整，不支持编辑。")
            updates_list = [gr.update()] * TOTAL_EDIT_OUTPUTS
            # Hide the edit column to avoid confusion
            updates_list[0] = gr.update(visible=False)
            return updates_list

        gr.Info(f"已加载任务: {job.get('name')}")

        # --- 1. Prepare Fixed Component Updates ---
        template_key = job.get("template_type")
        template_data = job.get("template_data", {})
        silent_run_status = job.get("silent_run", False)
        
        # Determine visibility of type-specific groups
        is_cron = (job["trigger_type"] == 'cron')
        is_date = (job["trigger_type"] == 'date')
        
        # Prepare lists for selection components
        cron_subscribers_val = find_selections_from_emails(job.get("receiver_emails", [])) if is_cron else []
        date_receiver_val = find_selection_from_email(job.get("receiver_email", "")) if is_date else None

        # Build fixed updates list explicitly matching main.py order:
        # [edit_column, job_id_input, edit_id_state, edit_type_state, 
        #  edit_template_dd, edit_custom_subject, edit_cron_group, edit_date_group,
        #  edit_cron_name, edit_cron_string, edit_cron_subscribers,
        #  edit_date_receiver, edit_date_send_at, edit_silent_run_checkbox]
        
        fixed_updates = [
            gr.update(visible=True), # edit_column
            job_id,                  # job_id_input
            job_id,                  # edit_id_state
            job["trigger_type"],     # edit_type_state
            gr.update(value=get_display_name_from_template_key(template_key)), # edit_template_dd
            job.get("custom_subject", ""), # edit_custom_subject
            gr.update(visible=is_cron),    # edit_cron_group
            gr.update(visible=is_date),    # edit_date_group
            job.get("name", "") if is_cron else "", # edit_cron_name
            job.get("cron_string", "") if is_cron else "", # edit_cron_string
            gr.update(value=cron_subscribers_val), # edit_cron_subscribers
            gr.update(value=date_receiver_val),    # edit_date_receiver
            job.get("run_date", "") if is_date else "", # edit_date_send_at
            gr.update(value=silent_run_status)     # edit_silent_run_checkbox
        ]

        # --- 2. Prepare Dynamic Field Updates ---
        meta = state.TEMPLATES_METADATA.get(template_key, {})
        
        # Dynamic Area visibility & Description
        dynamic_area_updates = [
            gr.update(visible=True), # edit_dynamic_area
            gr.update(value=f"#### {meta.get('description', '')}") # edit_form_desc
        ]

        # 3. Dynamic field updates
        dynamic_field_updates = []
        fields = meta.get("fields", [])
        for i in range(10): # max_fields_edit
            if i < len(fields):
                field = fields[i]
                f_type = field.get("type", "text") # Get type for logic
                val = template_data.get(field["name"], field.get("default"))
                
                # Group visible
                dynamic_field_updates.append(gr.update(visible=True))
                
                if f_type == "number":
                    dynamic_field_updates.append(gr.update(visible=False)) # Textbox
                    dynamic_field_updates.append(gr.update(visible=True, value=val)) # Number
                else:
                    lines = 3 if f_type == "textarea" else 1
                    dynamic_field_updates.append(gr.update(visible=True, value=val, lines=lines)) # Textbox
                    dynamic_field_updates.append(gr.update(visible=False)) # Number
            else:
                # Reset unused fields
                dynamic_field_updates.extend([gr.update(visible=False), gr.update(value=""), gr.update(value=None)])
        
        # Combine all parts
        return fixed_updates + dynamic_area_updates + dynamic_field_updates
        
    except requests.RequestException as e:
        gr.Error(f"获取任务详情失败: {e}")
        return [gr.update()] * TOTAL_EDIT_OUTPUTS

# ========================== END: MODIFICATION (File Splitting) ============================

def refresh_llm_configs():
    """回调函数：从后端获取并刷新LLM配置列表。"""
    columns = ["ID", "当前服务", "服务商名称", "API URL", "API Key (末4位)", "模型名称"]
    try:
        configs = api_client.get_llm_configs()
        
        # 格式化数据以适应DataFrame
        formatted_data = []
        for config in configs:
            formatted_data.append({
                "ID": config['id'],
                "当前服务": "✅ 是" if config['is_active'] else "否",
                "服务商名称": config['provider_name'],
                "API URL": config['api_url'],
                "API Key (末4位)": config['api_key'],
                "模型名称": config['model_name']
            })
        
        df = pd.DataFrame(formatted_data, columns=columns)
        msg = f"✅ LLM配置列表已于 {datetime.datetime.now().strftime('%H:%M:%S')} 刷新。"
        return df, msg
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', str(e)) if e.response else str(e)
        msg = f"🔴 获取LLM配置列表失败: {error_detail}"
        gr.Warning(msg)
        return pd.DataFrame([], columns=columns), msg

def on_select_llm_config(df: pd.DataFrame, evt: gr.SelectData):
    """回调函数：当用户在LLM配置表格中选中一行时，填充编辑表单。"""
    if df.empty or evt.index is None:
        return [gr.update()] * 5 # ID, provider, url, key, model

    selected_row = df.iloc[evt.index[0]]
    config_id = selected_row['ID']
    
    # 需要从原始数据（未格式化）中找到完整信息，但这里无法直接获取
    # 因此我们只填充已知信息，并提示用户API Key需要重新输入
    provider_name = selected_row['服务商名称']
    api_url = selected_row['API URL']
    model_name = selected_row['模型名称']

    # 返回ID状态、以及各个输入框的值
    return config_id, provider_name, api_url, "", model_name

def clear_llm_form_inputs():
    """回调函数：清空LLM配置表单的输入。"""
    return None, "", "", "", "" # id_state, provider, url, key, model

def handle_save_llm_config(config_id, provider_name, api_url, api_key, model_name):
    """回调函数：保存（添加或更新）一个LLM配置。"""
    if not all([provider_name, api_url, model_name]):
        gr.Warning("服务商名称、API URL 和模型名称为必填项。")
        return
        
    payload = {
        "provider_name": provider_name,
        "api_url": api_url,
        "api_key": api_key, # 如果是更新且此项为空，后端会忽略
        "model_name": model_name
    }

    try:
        if config_id: # 更新
            if not api_key:
                # 提醒用户，如果他们只是想修改其他字段
                gr.Info("API Key留空，将不会被修改。")
            response = api_client.update_llm_config(config_id, payload)
        else: # 添加
            if not api_key:
                gr.Warning("添加新配置时，API Key不能为空。")
                return
            response = api_client.add_llm_config(payload)
        
        gr.Info(response.get("message", "操作成功！"))

    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', str(e)) if e.response else str(e)
        gr.Error(f"保存失败: {error_detail}")

def handle_delete_llm_config(config_id: int):
    """回调函数：删除一个LLM配置。"""
    if not config_id:
        gr.Warning("请先从列表中选择一个要删除的配置。")
        return "操作失败：未选择配置。"
    try:
        response = api_client.delete_llm_config(config_id)
        msg = response.get("message", "删除成功！")
        gr.Info(msg)
        return msg
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', str(e)) if e.response else str(e)
        gr.Error(f"删除失败: {error_detail}")
        return f"删除失败: {error_detail}"

def handle_set_active_llm_config(config_id: int):
    """回调函数：设置一个LLM配置为当前服务。"""
    if not config_id:
        gr.Warning("请先从列表中选择一个要设为当前服务的配置。")
        return "操作失败：未选择配置。"
    try:
        response = api_client.set_active_llm_config(config_id)
        msg = response.get("message", "设置成功！")
        gr.Info(msg)
        return msg
    except requests.RequestException as e:
        error_detail = e.response.json().get('detail', str(e)) if e.response else str(e)
        gr.Error(f"设置失败: {error_detail}")
        return f"设置失败: {error_detail}"

# ========================== END: MODIFICATION ============================