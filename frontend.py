# frontend.py (已修改)
import os
import gradio as gr
import requests
import datetime
import pandas as pd
import re
from urllib.parse import quote

os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"

# --- 后端 API 地址 ---
API_BASE_URL = "http://127.0.0.1:8000/api"
TEMPLATES_INFO_URL = f"{API_BASE_URL}/templates/info"
# 【修改点】API URL 更新
SUBSCRIBERS_URL = f"{API_BASE_URL}/subscribers"
SEND_NOW_URL = f"{API_BASE_URL}/send-now"
SCHEDULE_ONCE_URL = f"{API_BASE_URL}/schedule-once"
JOBS_URL = f"{API_BASE_URL}/jobs" 
# 【修改点】新增获取订阅者列表的 API 地址
SUBSCRIBERS_URL = f"{API_BASE_URL}/subscribers"

# --- 全局状态 ---
# 用于存储从后端获取的模板信息
TEMPLATES_METADATA = {}
# 用于在下拉列表中存储 email -> remark_name 的映射
SUBSCRIBER_CHOICES = []

# --- API 调用函数 ---

def refresh_subscribers_list():
    """【修改】获取订阅者列表，并更新DataFrame和全局选择列表"""
    global SUBSCRIBER_CHOICES
    try:
        response = requests.get(SUBSCRIBERS_URL)
        response.raise_for_status()
        subs = response.json().get("subscribers", [])
        
        # 更新全局选择列表
        SUBSCRIBER_CHOICES = [f"{s.get('remark_name', s['email'])} <{s['email']}>" for s in subs]
        
        if not subs:
            return pd.DataFrame(columns=["邮箱地址", "备注名"]), "✅ 暂无订阅者。", gr.update(choices=[], value=None)
        
        df = pd.DataFrame(subs, columns=["email", "remark_name"])
        df.rename(columns={"email": "邮箱地址", "remark_name": "备注名"}, inplace=True)
        
        msg = f"✅ 订阅列表已于 {datetime.datetime.now().strftime('%H:%M:%S')} 刷新。"
        return df, msg, gr.update(choices=SUBSCRIBER_CHOICES, value=None)
    except requests.RequestException as e:
        msg = f"🔴 获取订阅列表失败: {e}"
        gr.Warning(msg)
        return pd.DataFrame(columns=["邮箱地址", "备注名"]), msg, gr.update(choices=[], value=None)

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

def handle_update_subscriber(email, remark_name):
    """处理更新订阅者备注的逻辑"""
    if not email:
        gr.Warning("请先从列表中选择一个要编辑的用户！")
        return
    if not remark_name:
        gr.Warning("备注名不能为空！")
        return
    
    try:
        # URL 编码 email
        encoded_email = quote(email)
        response = requests.put(f"{SUBSCRIBERS_URL}/{encoded_email}", json={"remark_name": remark_name})
        response.raise_for_status()
        msg = response.json().get("message")
        gr.Info(msg)
    except requests.RequestException as e:
        gr.Error(f"更新失败: {e.response.json().get('detail', e)}")

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

# 其他API函数（get_jobs_list, cancel_job_by_id 等）保持不变...
def get_jobs_list():
    """从后端获取所有计划任务列表并格式化"""
    try:
        response = requests.get(JOBS_URL)
        if response.status_code == 200:
            jobs = response.json().get("jobs", [])
            if not jobs:
                return pd.DataFrame(columns=["任务ID", "任务名称", "下次运行时间", "发送目标", "触发器详情"]), "✅ 暂无计划中的任务。"
            formatted_data = []
            for job in jobs:
                # 兼容周期性任务和一次性任务的参数结构
                receiver = "所有已订阅用户"
                if job.get('args') and len(job['args']) > 0:
                    receiver = job['args'][0]

                run_time = "N/A"
                if job['next_run_time']:
                    # 尝试解析带时区或不带时区的时间字符串
                    try:
                        dt_object = datetime.datetime.fromisoformat(job['next_run_time'])
                        run_time = dt_object.strftime('%Y-%m-%d %H:%M:%S %Z')
                    except ValueError:
                        run_time = job['next_run_time']


                formatted_data.append({
                    "任务ID": job['id'],
                    "任务名称": job['name'],
                    "下次运行时间": run_time,
                    "发送目标": receiver,
                    "触发器详情": job['trigger']
                })

            df = pd.DataFrame(formatted_data)
            return df, f"✅ 任务列表已于 {datetime.datetime.now().strftime('%H:%M:%S')} 刷新。"
        else:
            error_msg = f"获取任务列表失败: {response.text}"
            return pd.DataFrame(), error_msg
    except requests.ConnectionError:
        return pd.DataFrame(), "🔴 无法连接到后端。"
def cancel_job_by_id(job_id_to_cancel: str):
    """根据ID调用后端API取消任务"""
    if not job_id_to_cancel or not job_id_to_cancel.strip():
        gr.Warning("请输入有效的任务ID！")
        return "请输入任务ID。"
    
    try:
        url = f"{JOBS_URL}/{job_id_to_cancel.strip()}"
        response = requests.delete(url)
        if response.status_code == 200:
            msg = response.json().get("message", "任务已取消")
            gr.Info(msg)
            return msg
        else:
            error_detail = response.json().get('detail', '未知错误')
            gr.Warning(f"操作失败: {error_detail}")
            return f"操作失败: {error_detail}"
    except requests.ConnectionError:
        gr.Error("无法连接到后端！")
        return "🔴 无法连接到后端服务。"
        
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
        if response.status_code == 200:
            TEMPLATES_METADATA = response.json()
            template_names = [v["display_name"] for v in TEMPLATES_METADATA.values()]
            if not template_names:
                return gr.update(choices=["无可用模板"], value=None, interactive=False), "无法加载模板，请检查后端。"
            return gr.update(choices=template_names, value=template_names[0], interactive=True), "模板加载成功！"
        else:
            return gr.update(choices=["加载失败"], value=None, interactive=False), f"加载模板失败: {response.text}"
    except requests.ConnectionError:
        return gr.update(choices=["加载失败"], value=None, interactive=False), "无法连接到后端以加载模板。"

def get_template_key_from_display_name(display_name):
    """根据显示名称查找模板的内部key"""
    for key, value in TEMPLATES_METADATA.items():
        if value["display_name"] == display_name:
            return key
    return None
def send_or_schedule_email(action: str, receiver_selection: str, template_choice: str, send_at: str, *dynamic_field_values):
    receiver_email = get_email_from_selection(receiver_selection)
    if not receiver_email or not template_choice:
        return "错误：接收者邮箱和模板类型为必填项。"
    
    template_key = get_template_key_from_display_name(template_choice)
    if not template_key:
        return "错误：无效的模板选择。"

    fields = TEMPLATES_METADATA.get(template_key, {}).get("fields", [])
    template_data = {}
    components_per_field = 3 
    
    for i, field in enumerate(fields):
        field_type = field.get("type", "text")
        base_index = i * components_per_field
        if field_type == "textarea":
            value_index = base_index + 0
        elif field_type == "number":
            value_index = base_index + 1
        else:
            value_index = base_index + 2
        template_data[field["name"]] = dynamic_field_values[value_index]

    payload = {
        "receiver_email": receiver_email,
        "template_type": template_key,
        "template_data": template_data,
    }
    
    url = ""
    if action == "send_now":
        url = SEND_NOW_URL
    elif action == "schedule_once":
        if not send_at:
            return "错误：定时发送必须指定发送时间。"
        payload["send_at"] = send_at
        url = SCHEDULE_ONCE_URL
    else:
        return "错误：未知的操作。"

    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            return f"操作失败 (状态码 {response.status_code}): {response.json().get('detail', response.text)}"
        if action == "schedule_once":
            gr.Info("任务已成功调度！将自动刷新任务列表。")
        return response.json().get("message", "操作成功！")
    except requests.ConnectionError:
        return "错误：无法连接到后端服务。"
    except Exception as e:
        return f"发生未知异常: {e}"

# --- Gradio 界面构建 ---

with gr.Blocks(theme=gr.themes.Soft(primary_hue="green", secondary_hue="lime"), title="EMinder 控制中心") as demo:
    backend_status_output = gr.Markdown(check_backend_status)
    gr.Markdown("# EMinder 邮件任务控制中心")

    # 【修改1】将两个独立的接收者输入框合并为一个共享组件，并放置在 Tabs 的外部，使其对两个 Tab 可见
    shared_receiver_input = gr.Dropdown(
        label="1. 选择或输入接收者邮箱 (适用于下方所有邮件操作)",
        allow_custom_value=True,
        interactive=True
    )

    def create_email_form(is_scheduled: bool, receiver_dropdown: gr.Dropdown):
        # 【修改2】调整标题，因为接收人选择框已移至外部
        gr.Markdown("### 2. 选择邮件模板")
        load_status = gr.Markdown()
        with gr.Row():
            template_dropdown = gr.Dropdown(label="选择邮件模板", choices=["正在加载..."], interactive=False, scale=2)
        
        gr.Markdown("### 3. 填写模板所需信息")
        dynamic_fields_components = []
        with gr.Column() as dynamic_form_area:
            form_description = gr.Markdown()
            max_fields = 10
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

        gr.Markdown("### 4. 执行操作")
        
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
            inputs=[action_type, receiver_dropdown, template_dropdown, send_at_component] + all_field_inputs,
            outputs=output_text
        )
        return load_status, template_dropdown, action_button, all_field_outputs, toggle_template_fields

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
            # 【修改3】移除原先用于放置独立输入框的布局，并将共享输入框传入表单创建函数
            manual_load_status, manual_template_dropdown, manual_action_button, manual_all_field_outputs, manual_toggle_fn = create_email_form(is_scheduled=False, receiver_dropdown=shared_receiver_input)
        
        with gr.TabItem("定时单次任务") as tab_schedule:
            # 【修改3】移除原先用于放置独立输入框的布局，并将共享输入框传入表单创建函数
            schedule_load_status, schedule_template_dropdown, schedule_action_button, schedule_all_field_outputs, schedule_toggle_fn = create_email_form(is_scheduled=True, receiver_dropdown=shared_receiver_input)

        with gr.TabItem("📅 计划任务管理", id="jobs_tab") as tab_jobs:
            gr.Markdown("## 查看并管理所有已计划的邮件任务")
            gr.Markdown("在这里，你可以看到所有等待执行的一次性任务和周期性任务，并可以手动取消它们。")
            
            with gr.Row():
                refresh_jobs_button = gr.Button("🔄 刷新任务列表", variant="primary")
            jobs_status_output = gr.Markdown()
            jobs_dataframe = gr.DataFrame(
                headers=["任务ID", "任务名称", "下次运行时间", "发送目标", "触发器详情"],
                interactive=False, row_count=(5, "dynamic"), col_count=(5, "fixed"), wrap=True
            )
            
            with gr.Group():
                gr.Markdown("### 取消任务")
                gr.Markdown("注意：取消周期性任务 (`cron`) 会使其永久停止，直到后端服务重启。")
                with gr.Row():
                    job_id_input = gr.Textbox(label="要取消的任务ID", scale=3)
                    cancel_button = gr.Button("🗑️ 取消指定任务", variant="stop", scale=1)
            cancel_status_output = gr.Textbox(label="操作结果", interactive=False)

    # --- 事件绑定 ---
    
    # 订阅管理 Tab
    # 【修正点 #2】修正 DataFrame select 事件的处理方式
    def on_select_subscriber(df: pd.DataFrame, evt: gr.SelectData):
        if evt.index is None: return "", ""
        row_index = evt.index[0]
        selected_row = df.iloc[row_index]
        email = selected_row['邮箱地址']
        remark = selected_row['备注名']
        return email, remark
    subscribers_dataframe.select(fn=on_select_subscriber, inputs=[subscribers_dataframe], outputs=[sub_email_input, sub_remark_input], trigger_mode='once')
    
    add_button.click(fn=handle_add_subscriber, inputs=[sub_email_input, sub_remark_input]).then(
        fn=refresh_subscribers_list, outputs=[subscribers_dataframe, subs_status_output, shared_receiver_input]
    )
    
    delete_button.click(fn=handle_delete_subscriber, inputs=[sub_email_input]).then(
        fn=refresh_subscribers_list, outputs=[subscribers_dataframe, subs_status_output, shared_receiver_input]
    )
    
    def clear_inputs(): return "", ""
    clear_button.click(fn=clear_inputs, outputs=[sub_email_input, sub_remark_input])

    refresh_subs_button.click(
        fn=refresh_subscribers_list, outputs=[subscribers_dataframe, subs_status_output, shared_receiver_input]
    )

    # 邮件发送 Tab
    demo.load(fn=load_templates_info, outputs=[manual_template_dropdown, manual_load_status]).then(fn=manual_toggle_fn, inputs=manual_template_dropdown, outputs=manual_all_field_outputs)
    demo.load(fn=load_templates_info, outputs=[schedule_template_dropdown, schedule_load_status]).then(fn=schedule_toggle_fn, inputs=schedule_template_dropdown, outputs=schedule_all_field_outputs)
    
    # 全局加载
    demo.load(fn=refresh_subscribers_list, outputs=[subscribers_dataframe, subs_status_output, shared_receiver_input])

    # 计划任务 Tab
    tab_jobs.select(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])
    refresh_jobs_button.click(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])
    cancel_button.click(fn=cancel_job_by_id, inputs=[job_id_input], outputs=[cancel_status_output]).then(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])
    schedule_action_button.click(fn=lambda: gr.update(selected=tab_jobs.id), outputs=tabs).then(fn=get_jobs_list, outputs=[jobs_dataframe, jobs_status_output])


if __name__ == "__main__":
    print("EMinder 前端控制中心即将启动...")
    print("请在浏览器中打开 http://127.0.0.1:7860")
    demo.launch(server_name="0.0.0.0", server_port=7860)