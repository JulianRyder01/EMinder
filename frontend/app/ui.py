# frontend/app/ui.py
# ========================== START: MODIFICATION (Feature Addition) ==========================
# DESIGNER'S NOTE:
# This file is dedicated to building the user interface. It defines the layout and
# creates all the Gradio components.
#
# CHANGES:
# 1. create_job_management_tab: Added a 'confirmation_row' to handle safe deletion within the UI
#    instead of using browser alerts.

import gradio as gr
import datetime

MAX_FIELDS = 10 # Max number of dynamic fields a template can have.

def create_subscriber_management_tab():
    """Builds the UI for the 'Subscription Management' tab."""
    with gr.TabItem("订阅管理", id="subscribe_tab") as tab:
        gr.Markdown("## 订阅者管理面板")
        with gr.Row():
            refresh_btn = gr.Button("🔄 刷新订阅列表", variant="secondary")
        status_output = gr.Markdown()
        dataframe = gr.DataFrame(headers=["邮箱地址", "备注名"], interactive=False, row_count=(10, "dynamic"))
        
        with gr.Group():
            gr.Markdown("### 添加 / 编辑订阅者")
            gr.Markdown("在下方输入信息后点击“添加/更新”。若要编辑，请先在上方表格中**点击选中**一行。")
            email_input = gr.Textbox(label="邮箱地址", placeholder="user@example.com")
            remark_input = gr.Textbox(label="备注名", placeholder="例如：用户A")
            with gr.Row():
                add_btn = gr.Button("➕ 添加/更新", variant="primary")
                delete_btn = gr.Button("🗑️ 删除选中项", variant="stop")
                clear_btn = gr.Button("清空表单")
    
    components = {
        "tab": tab, "refresh_btn": refresh_btn, "status_output": status_output, "dataframe": dataframe,
        "email_input": email_input, "remark_input": remark_input, "add_btn": add_btn,
        "delete_btn": delete_btn, "clear_btn": clear_btn
    }
    return components

def create_email_form(is_scheduled: bool):
    """
    Builds the reusable form for sending or scheduling emails.
    """
    gr.Markdown("### 1. 选择或输入接收者邮箱")
    with gr.Row():
        receiver_dd = gr.Dropdown(
            label="选择或输入接收者",
            allow_custom_value=True,
            interactive=True
        )

    gr.Markdown("### 2. 选择邮件模板")
    load_status = gr.Markdown()
    template_dd = gr.Dropdown(label="选择邮件模板", choices=["正在加载..."], interactive=False)
    custom_subject = gr.Textbox(label="自定义邮件标题 (可选)", info="留空则使用模板默认标题")

    gr.Markdown("### 3. 填写模板所需信息")
    with gr.Column(visible=False) as dynamic_form_area: # Initially hidden
        form_description = gr.Markdown()
        dynamic_fields_components = []
        for i in range(MAX_FIELDS):
            with gr.Group(visible=False) as field_group:
                comp_text = gr.Textbox(label=f"字段{i+1}")
                comp_num = gr.Number(label=f"字段{i+1}", visible=False)
            dynamic_fields_components.append({"group": field_group, "text": comp_text, "number": comp_num})

    gr.Markdown("### 4. 添加附件 (可选)")
    attachment_state = gr.State([])
    with gr.Row():
        attachment_display = gr.Textbox(label="已选择的附件列表", interactive=False, lines=4)
    with gr.Row():
        file_uploader = gr.File(label="点击选择或拖拽文件到此处添加", file_count="multiple", type="filepath")
        clear_attachments_btn = gr.Button("🗑️ 清空列表")

    gr.Markdown("### 5. 执行操作")
    silent_run_checkbox = gr.Checkbox(label="静默运行", info="勾选后，任务将正常执行（包括脚本运行、文件归档等），但不会发送邮件。")
    
    if is_scheduled:
        now_plus_10 = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")
        send_at_input = gr.Textbox(label="预定发送时间", value=now_plus_10, info="格式: YYYY-MM-DD HH:MM")
        action_btn = gr.Button("创建一次性定时任务", variant="primary")
        action_type = gr.State("schedule_once")
    else:
        send_at_input = gr.State(None)
        action_btn = gr.Button("立即发送邮件", variant="primary")
        action_type = gr.State("send_now")
    
    output_text = gr.Textbox(label="操作结果", interactive=False)

    # Collect all dynamic field inputs for the handler
    all_field_inputs = [c for d in dynamic_fields_components for c in (d['text'], d['number'])]
    dynamic_outputs = [dynamic_form_area, form_description] + [comp for d in dynamic_fields_components for comp in d.values()]

    components = {
        "receiver_dd": receiver_dd,
        "load_status": load_status, "template_dd": template_dd, "custom_subject": custom_subject,
        "dynamic_form_area": dynamic_form_area, "form_description": form_description,
        "dynamic_fields": dynamic_fields_components, "all_field_inputs": all_field_inputs,
        "dynamic_outputs": dynamic_outputs, # 统一动态输出
        "attachment_state": attachment_state, "attachment_display": attachment_display,
        "file_uploader": file_uploader, "clear_attachments_btn": clear_attachments_btn,
        "send_at_input": send_at_input, "action_btn": action_btn, "action_type": action_type,
        "output_text": output_text,
        "silent_run_checkbox": silent_run_checkbox
    }
    return components
    
def create_cron_job_tab():
    """Builds the UI for the 'Schedule Cron Job' tab."""
    with gr.TabItem("计划周期任务", id="cron_tab") as tab:
        gr.Markdown("## 创建周期性邮件发送任务")
        gr.Markdown("通过 [Cron 表达式](https://crontab.guru/) 定义一个重复执行的计划，例如在每个周一上午9点向指定用户发送周报。")
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 1. 定义任务属性")
                job_name = gr.Textbox(label="任务名称", placeholder="例如：项目组每周一九点周报")
                cron_string = gr.Textbox(label="Cron 表达式", placeholder="分 时 日 月 周 (例如: 0 9 * * 1)")
                
                gr.Markdown("### 2. 选择接收者")
                receiver_subscribers = gr.CheckboxGroup(label="从订阅列表中选择 (可多选)")
                receiver_custom = gr.Textbox(label="添加自定义邮箱", placeholder="多个邮箱请用英文逗号 , 分隔")

            with gr.Column(scale=3):
                gr.Markdown("### 3. 选择并填写邮件模板")
                load_status = gr.Markdown()
                template_dd = gr.Dropdown(label="选择邮件模板", choices=["正在加载..."], interactive=False)
                custom_subject = gr.Textbox(label="自定义邮件标题 (可选)")
                
                with gr.Column(visible=False) as dynamic_form_area: # Initially hidden
                    form_description = gr.Markdown()
                    dynamic_fields_components = []
                    for i in range(MAX_FIELDS):
                        with gr.Group(visible=False) as fg:
                            ct = gr.Textbox(label=f"字段{i+1}")
                            cn = gr.Number(label=f"字段{i+1}", visible=False)
                        dynamic_fields_components.append({"group": fg, "text": ct, "number": cn})
        
        gr.Markdown("### 4. 创建任务")
        silent_run_checkbox = gr.Checkbox(label="静默运行", info="勾选后，任务将正常执行（包括脚本运行、文件归档等），但不会发送邮件。")
        with gr.Row():
            create_btn = gr.Button("✔️ 创建周期任务", variant="primary")
        output_text = gr.Textbox(label="操作结果", interactive=False)

    all_field_inputs = [c for d in dynamic_fields_components for c in (d['text'], d['number'])]
    dynamic_outputs = [dynamic_form_area, form_description] + [comp for d in dynamic_fields_components for comp in d.values()]

    components = {
        "tab": tab, "job_name": job_name, "cron_string": cron_string, "receiver_subscribers": receiver_subscribers,
        "receiver_custom": receiver_custom, "load_status": load_status, "template_dd": template_dd,
        "custom_subject": custom_subject, "dynamic_form_area": dynamic_form_area, "form_description": form_description,
        "dynamic_fields": dynamic_fields_components, "all_field_inputs": all_field_inputs, "dynamic_outputs": dynamic_outputs,
        "create_btn": create_btn, "output_text": output_text,
        "silent_run_checkbox": silent_run_checkbox
    }
    return components

def create_job_management_tab():
    """Builds the UI for the 'Job Management' tab, including the job list and edit form."""
    with gr.TabItem("📅 计划任务管理", id="jobs_tab") as tab:
        gr.Markdown("## 查看并管理所有已计划的邮件任务")
        with gr.Row():
            refresh_btn = gr.Button("🔄 刷新任务列表", variant="primary")
        status_output = gr.Markdown()
        dataframe = gr.DataFrame(headers=["任务ID", "任务名称", "类型", "下次运行时间", "发送目标"], interactive=False, row_count=(5, "dynamic"), wrap=True)
        
        with gr.Row():
            with gr.Column(scale=2):
                with gr.Group():
                    gr.Markdown("### 操作选中任务")
                    job_id_input = gr.Textbox(label="要操作的任务ID (自动填充)")
                    
                    # ========================== START: MODIFICATION (Fix Cancel UI) ==========================
                    # DESIGNER'S NOTE: 
                    # 使用两组 Row 来实现“交互式确认”。
                    # 'default_action_row' 显示常规按钮。
                    # 'confirm_action_row' 默认隐藏，仅在点击删除时显示，提供 Yes/No 选项。
                    # 这避免了使用浏览器原生弹窗，视觉更统一。
                    with gr.Row(visible=True) as default_action_row:
                        cancel_btn = gr.Button("🗑️ 取消任务", variant="stop")
                        run_now_btn = gr.Button("▶️ 立即运行", variant="secondary")
                    
                    with gr.Row(visible=False) as confirm_action_row:
                        confirm_yes_btn = gr.Button("⚠️ 确认删除", variant="stop")
                        confirm_no_btn = gr.Button("❌ 再想想", variant="secondary")
                    # ========================== END: MODIFICATION ============================

                    cancel_status = gr.Textbox(label="操作结果", interactive=False)
            
            with gr.Column(scale=3, visible=False) as edit_column:
                 with gr.Group():
                    gr.Markdown("### 📝 编辑任务")
                    edit_id_state = gr.State()
                    edit_type_state = gr.State()
                    
                    with gr.Group(visible=False) as edit_cron_group:
                        edit_cron_name = gr.Textbox(label="任务名称")
                        edit_cron_string = gr.Textbox(label="Cron 表达式")
                        edit_cron_subscribers = gr.CheckboxGroup(label="从订阅列表选择")
                        edit_cron_custom = gr.Textbox(label="添加自定义邮箱")
                    
                    with gr.Group(visible=False) as edit_date_group:
                        edit_date_receiver = gr.Dropdown(label="接收者邮箱", allow_custom_value=True)
                        edit_date_send_at = gr.Textbox(label="预定发送时间")

                    edit_template_dd = gr.Dropdown(label="邮件模板")
                    edit_custom_subject = gr.Textbox(label="自定义邮件标题 (可选)")
                    
                    with gr.Column(visible=False) as edit_dynamic_area: # Initially hidden
                        edit_form_desc = gr.Markdown()
                        edit_dynamic_fields = []
                        for i in range(MAX_FIELDS):
                            with gr.Group(visible=False) as fg:
                                et = gr.Textbox(label=f"字段{i+1}")
                                en = gr.Number(label=f"字段{i+1}", visible=False)
                            edit_dynamic_fields.append({"group": fg, "text": et, "number": en})
                    
                    edit_silent_run_checkbox = gr.Checkbox(label="静默运行", info="勾选后，任务将正常执行，但不会发送邮件。")
                    with gr.Row():
                        update_btn = gr.Button("✔️ 更新任务", variant="primary")
                        cancel_edit_btn = gr.Button("❌ 取消编辑")
                    update_status = gr.Textbox(label="更新结果", interactive=False)
    
    edit_all_field_inputs = [c for d in edit_dynamic_fields for c in (d['text'], d['number'])]
    edit_dynamic_outputs = [edit_dynamic_area, edit_form_desc] + [comp for d in edit_dynamic_fields for comp in d.values()]

    components = {
        "tab": tab, "refresh_btn": refresh_btn, "status_output": status_output, "dataframe": dataframe,
        "job_id_input": job_id_input, "cancel_status": cancel_status,
        
        # New components for confirmation UI
        "cancel_btn": cancel_btn, "run_now_btn": run_now_btn,
        "confirm_yes_btn": confirm_yes_btn, "confirm_no_btn": confirm_no_btn,
        "default_action_row": default_action_row, "confirm_action_row": confirm_action_row,

        "edit_column": edit_column, "edit_id_state": edit_id_state, "edit_type_state": edit_type_state,
        "edit_cron_group": edit_cron_group, "edit_cron_name": edit_cron_name, "edit_cron_string": edit_cron_string,
        "edit_cron_subscribers": edit_cron_subscribers, "edit_cron_custom": edit_cron_custom,
        "edit_date_group": edit_date_group, "edit_date_receiver": edit_date_receiver, "edit_date_send_at": edit_date_send_at,
        "edit_template_dd": edit_template_dd, "edit_custom_subject": edit_custom_subject,
        "edit_dynamic_area": edit_dynamic_area, "edit_form_desc": edit_form_desc,
        "edit_dynamic_fields": edit_dynamic_fields, "edit_all_field_inputs": edit_all_field_inputs, "dynamic_outputs": edit_dynamic_outputs,
        "update_btn": update_btn, "cancel_edit_btn": cancel_edit_btn, "update_status": update_status,
        "edit_silent_run_checkbox": edit_silent_run_checkbox
    }
    return components

def create_llm_settings_tab():
    """构建 "LLM 服务配置" 选项卡的UI界面。"""
    with gr.TabItem("⚙️ LLM 服务配置", id="llm_settings_tab") as tab:
        gr.Markdown("## 大模型（LLM）服务配置中心")
        gr.Markdown("在这里管理用于邮件内容生成、总结等功能的语言模型API。**在任何时候，只有一个服务可以被设为“当前服务”**。")
        
        with gr.Row():
            refresh_btn = gr.Button("🔄 刷新配置列表", variant="secondary")
        status_output = gr.Markdown()
        dataframe = gr.DataFrame(
            headers=["ID", "当前服务", "服务商名称", "API URL", "API Key (末4位)", "模型名称"],
            interactive=False,
            row_count=(5, "dynamic")
        )
        
        with gr.Row():
            with gr.Column(scale=2):
                with gr.Group():
                    gr.Markdown("### 🎛️ 操作选中配置")
                    gr.Markdown("请先在上方表格中**点击选中**一行以进行操作。")
                    config_id_state = gr.State() # 用于存储选中行的ID
                    
                    with gr.Row():
                        set_active_btn = gr.Button("✅ 设为当前服务", variant="primary")
                        delete_btn = gr.Button("🗑️ 删除此配置", variant="stop")
                    
                    action_status_output = gr.Textbox(label="操作结果", interactive=False)

            with gr.Column(scale=3):
                with gr.Group():
                    gr.Markdown("### ✨ 添加新配置 / 编辑选中配置")
                    provider_name_input = gr.Textbox(label="服务商名称", placeholder="例如：硅基流动 (SiliconFlow)")
                    api_url_input = gr.Textbox(label="API URL", placeholder="例如：https://api.siliconflow.cn/v1")
                    api_key_input = gr.Textbox(label="API Key", type="password", placeholder="sk-...  (编辑时留空则不修改)")
                    model_name_input = gr.Textbox(label="模型名称", placeholder="例如：deepseek-ai/DeepSeek-V3")
                    
                    with gr.Row():
                        save_btn = gr.Button("💾 保存配置", variant="primary")
                        clear_btn = gr.Button("📋 清空表单")

    components = {
        "tab": tab,
        "refresh_btn": refresh_btn,
        "status_output": status_output,
        "dataframe": dataframe,
        "config_id_state": config_id_state,
        "set_active_btn": set_active_btn,
        "delete_btn": delete_btn,
        "action_status_output": action_status_output,
        "provider_name_input": provider_name_input,
        "api_url_input": api_url_input,
        "api_key_input": api_key_input,
        "model_name_input": model_name_input,
        "save_btn": save_btn,
        "clear_btn": clear_btn,
    }
    return components