# frontend/app/main.py
# ========================== START: MODIFICATION (Wiring and Robustness) ==========================
# DESIGNER'S NOTE:
# This file assembles the UI and wires the event handlers.
#
# CHANGES:
# 1. FIXED: Corrected the order of 'edit_form_outputs_list' to perfectly match the 'fixed_updates'
#    returned by 'on_select_job' in handlers.py. Specifically, 'job_name_display' is now
#    correctly placed at index 2. This resolves the InvalidComponentError.

import os
import gradio as gr
from functools import partial

# Import application modules
from .config import config
from . import handlers
from . import ui

def main():
    """
    Builds the Gradio UI, wires up all the event handlers, and launches the interface.
    """
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"

    with gr.Blocks(theme=gr.themes.Soft(primary_hue="green", secondary_hue="lime"), title="EMinder 控制中心") as demo:
        # --- 1. Global Components ---
        backend_status = gr.Markdown()
        gr.Markdown("# EMinder 邮件任务控制中心")

        # Create the single, shared dropdown here, outside the tabs.
        shared_receiver_dd = gr.Dropdown(
            label="1. 选择或输入接收者邮箱",
            info="适用于'手动发送'和'定时单次任务'",
            allow_custom_value=True,
            interactive=True
        )

        # --- 2. Build UI from Tabs ---
        with gr.Tabs() as tabs:
            sub_ui = ui.create_subscriber_management_tab()
            
            with gr.TabItem("手动发送邮件", id="manual_tab") as manual_tab:
                # The form now starts from Step 2, as Step 1 is the shared dropdown above.
                manual_ui = ui.create_email_form(is_scheduled=False)
            
            with gr.TabItem("定时单次任务", id="schedule_tab") as schedule_tab:
                schedule_ui = ui.create_email_form(is_scheduled=True)
            
            cron_ui = ui.create_cron_job_tab()
            jobs_ui = ui.create_job_management_tab()
            
            llm_ui = ui.create_llm_settings_tab()

        # --- 3. Wire Event Handlers ---

        # --- Wire Event Handlers ---
        demo.load(handlers.check_backend_status, outputs=backend_status)
        
        # Initial data loading for templates - targets ALL template dropdowns across ALL tabs.
        demo.load(
            handlers.load_templates_info, 
            outputs=[
                manual_ui["template_dd"], manual_ui["load_status"],
                schedule_ui["template_dd"], schedule_ui["load_status"],
                cron_ui["template_dd"], cron_ui["load_status"],
                jobs_ui["edit_template_dd"]
            ]
        )
        
        # Initial data loading for subscribers
        sub_refresh_outputs = [
            sub_ui["dataframe"], sub_ui["status_output"], 
            shared_receiver_dd,             
            cron_ui["receiver_subscribers"],
            jobs_ui["edit_date_receiver"],
            jobs_ui["edit_cron_subscribers"] # <--- ADDED: This is the fix for the broken component in Edit Job tab
        ]
        
        # 在应用加载时也执行一次订阅者刷新
        demo.load(handlers.refresh_subscribers_list, outputs=sub_refresh_outputs)
        
        # Subscriber Management Tab Events
        sub_ui["tab"].select(handlers.refresh_subscribers_list, outputs=sub_refresh_outputs) # 选中Tab时刷新
        sub_ui["refresh_btn"].click(handlers.refresh_subscribers_list, outputs=sub_refresh_outputs)
        sub_ui["add_btn"].click(handlers.handle_add_subscriber, inputs=[sub_ui["email_input"], sub_ui["remark_input"]]).then(handlers.refresh_subscribers_list, outputs=sub_refresh_outputs)
        sub_ui["delete_btn"].click(handlers.handle_delete_subscriber, inputs=[sub_ui["email_input"]]).then(handlers.refresh_subscribers_list, outputs=sub_refresh_outputs)
        sub_ui["dataframe"].select(handlers.on_select_subscriber, inputs=[sub_ui["dataframe"]], outputs=[sub_ui["email_input"], sub_ui["remark_input"]], trigger_mode='once')
        sub_ui["clear_btn"].click(handlers.clear_subscriber_inputs, outputs=[sub_ui["email_input"], sub_ui["remark_input"]])

        # Dynamic Form Events (for all forms)
        # Combine all dynamic field outputs into a single list for wiring.
        manual_dynamic_outputs = [manual_ui["dynamic_form_area"], manual_ui["form_description"]] + [comp for d in manual_ui["dynamic_fields"] for comp in d.values()]
        schedule_dynamic_outputs = [schedule_ui["dynamic_form_area"], schedule_ui["form_description"]] + [comp for d in schedule_ui["dynamic_fields"] for comp in d.values()]
        cron_dynamic_outputs = [cron_ui["dynamic_form_area"], cron_ui["form_description"]] + [comp for d in cron_ui["dynamic_fields"] for comp in d.values()]
        edit_dynamic_outputs = [jobs_ui["edit_dynamic_area"], jobs_ui["edit_form_desc"]] + [comp for d in jobs_ui["edit_dynamic_fields"] for comp in d.values()]

        manual_ui["template_dd"].change(partial(handlers.toggle_template_fields, ui.MAX_FIELDS), inputs=manual_ui["template_dd"], outputs=manual_dynamic_outputs)
        schedule_ui["template_dd"].change(partial(handlers.toggle_template_fields, ui.MAX_FIELDS), inputs=schedule_ui["template_dd"], outputs=schedule_dynamic_outputs)
        cron_ui["template_dd"].change(partial(handlers.toggle_template_fields, ui.MAX_FIELDS), inputs=cron_ui["template_dd"], outputs=cron_dynamic_outputs)
        jobs_ui["edit_template_dd"].change(partial(handlers.toggle_template_fields, ui.MAX_FIELDS), inputs=jobs_ui["edit_template_dd"], outputs=edit_dynamic_outputs)
        
        # Manual & Schedule Once Form Events
        for form_ui in [manual_ui, schedule_ui]:
            form_ui["file_uploader"].upload(
                lambda cur, new: (sorted(list(set(cur+new))), "\n".join(sorted(list(set(cur+new))))),
                inputs=[form_ui["attachment_state"], form_ui["file_uploader"]],
                outputs=[form_ui["attachment_state"], form_ui["attachment_display"]]
            )
            form_ui["clear_attachments_btn"].click(lambda: ([], ""), outputs=[form_ui["attachment_state"], form_ui["attachment_display"]])
            form_ui["action_btn"].click(
                handlers.send_or_schedule_email,
                inputs=[form_ui["action_type"], shared_receiver_dd, form_ui["template_dd"], form_ui["custom_subject"], form_ui["send_at_input"], form_ui["silent_run_checkbox"], form_ui["attachment_state"]] + form_ui["all_field_inputs"],
                outputs=form_ui["output_text"]
            ).then(handlers.navigate_on_success, inputs=form_ui["output_text"], outputs=tabs).then(handlers.get_jobs_list, outputs=[jobs_ui["dataframe"], jobs_ui["status_output"]])
            
        # Schedule Cron Job Tab Events
        cron_ui["create_btn"].click(
            handlers.handle_schedule_cron,
            inputs=[cron_ui["job_name"], cron_ui["cron_string"], cron_ui["receiver_subscribers"], cron_ui["receiver_custom"], cron_ui["template_dd"], cron_ui["custom_subject"], cron_ui["silent_run_checkbox"]] + cron_ui["all_field_inputs"],
            outputs=cron_ui["output_text"]
        ).then(handlers.navigate_on_success, inputs=cron_ui["output_text"], outputs=tabs).then(handlers.get_jobs_list, outputs=[jobs_ui["dataframe"], jobs_ui["status_output"]])
        
        # Job Management Tab Events
        jobs_ui["tab"].select(handlers.get_jobs_list, outputs=[jobs_ui["dataframe"], jobs_ui["status_output"]])
        jobs_ui["refresh_btn"].click(handlers.get_jobs_list, outputs=[jobs_ui["dataframe"], jobs_ui["status_output"]])
        jobs_ui["cancel_btn"].click(
            handlers.ask_confirm_cancel_job, 
            inputs=[jobs_ui["job_id_input"]], 
            outputs=[jobs_ui["default_action_row"], jobs_ui["confirm_action_row"]]
        )
        
        # 2. Click Yes -> Delete -> Refresh List -> Reset UI
        jobs_ui["confirm_yes_btn"].click(
            handlers.execute_cancel_job,
            inputs=[jobs_ui["job_id_input"]],
            outputs=[jobs_ui["cancel_status"], jobs_ui["default_action_row"], jobs_ui["confirm_action_row"]]
        ).then(
            handlers.get_jobs_list, outputs=[jobs_ui["dataframe"], jobs_ui["status_output"]]
        ).then(
            handlers.reset_job_selection_ui,
            outputs=[jobs_ui["job_id_input"], jobs_ui["job_name_display"], jobs_ui["edit_column"], jobs_ui["cancel_status"]]
        )

        # 3. Click No -> Restore UI
        jobs_ui["confirm_no_btn"].click(
            handlers.cancel_cancel_op,
            outputs=[jobs_ui["default_action_row"], jobs_ui["confirm_action_row"]]
        )

        jobs_ui["run_now_btn"].click(handlers.handle_run_job_now, inputs=[jobs_ui["job_id_input"]], outputs=[jobs_ui["cancel_status"]])

        # Job Edit Form Events
        edit_form_outputs_list = [
            jobs_ui["edit_column"],         # 1
            jobs_ui["job_id_input"],        # 2
            jobs_ui["job_name_display"],    # 3 (Text Display) - CORRECTLY PLACED
            jobs_ui["default_action_row"],  # 4 (Group)
            jobs_ui["confirm_action_row"],  # 5 (Group)
            jobs_ui["edit_id_state"],       # 6
            jobs_ui["edit_type_state"],     # 7
            jobs_ui["edit_template_dd"],    # 8
            jobs_ui["edit_custom_subject"], # 9
            jobs_ui["edit_cron_group"],     # 10
            jobs_ui["edit_date_group"],     # 11
            jobs_ui["edit_cron_name"],      # 12
            jobs_ui["edit_cron_string"],    # 13
            jobs_ui["edit_cron_subscribers"],# 14
            jobs_ui["edit_date_receiver"],  # 15
            jobs_ui["edit_date_send_at"],   # 16
            jobs_ui["edit_silent_run_checkbox"] # 17
        ] + edit_dynamic_outputs
        
        jobs_ui["dataframe"].select(handlers.on_select_job, inputs=[jobs_ui["dataframe"]], outputs=edit_form_outputs_list)
        jobs_ui["cancel_edit_btn"].click(lambda: gr.update(visible=False), outputs=jobs_ui["edit_column"])
        
        edit_form_inputs_list = [
            jobs_ui["edit_id_state"], jobs_ui["edit_type_state"], jobs_ui["edit_cron_name"], jobs_ui["edit_cron_string"],
            jobs_ui["edit_cron_subscribers"], jobs_ui["edit_cron_custom"], jobs_ui["edit_date_receiver"],
            jobs_ui["edit_date_send_at"], jobs_ui["edit_template_dd"], jobs_ui["edit_custom_subject"],
            jobs_ui["edit_silent_run_checkbox"]
        ] + jobs_ui["edit_all_field_inputs"]
        jobs_ui["update_btn"].click(
            handlers.handle_update_job, inputs=edit_form_inputs_list, outputs=jobs_ui["update_status"]
        ).then(
            handlers.get_jobs_list, outputs=[jobs_ui["dataframe"], jobs_ui["status_output"]]
        ).then(
            lambda: gr.update(visible=False), outputs=jobs_ui["edit_column"]
        )

        llm_refresh_outputs = [llm_ui["dataframe"], llm_ui["status_output"]]
        llm_ui["tab"].select(handlers.refresh_llm_configs, outputs=llm_refresh_outputs)
        llm_ui["refresh_btn"].click(handlers.refresh_llm_configs, outputs=llm_refresh_outputs)
        
        # 2. 当在表格中选中一行时，填充表单
        llm_select_outputs = [
            llm_ui["config_id_state"], 
            llm_ui["provider_name_input"], 
            llm_ui["api_url_input"],
            llm_ui["api_key_input"],
            llm_ui["model_name_input"]
        ]
        llm_ui["dataframe"].select(handlers.on_select_llm_config, inputs=[llm_ui["dataframe"]], outputs=llm_select_outputs, trigger_mode='once')
        
        # 3. 清空表单按钮
        llm_ui["clear_btn"].click(handlers.clear_llm_form_inputs, outputs=llm_select_outputs)

        # 4. 保存按钮（添加或更新）
        llm_save_inputs = [
            llm_ui["config_id_state"], 
            llm_ui["provider_name_input"], 
            llm_ui["api_url_input"], 
            llm_ui["api_key_input"], 
            llm_ui["model_name_input"]
        ]
        llm_ui["save_btn"].click(handlers.handle_save_llm_config, inputs=llm_save_inputs).then(
            handlers.refresh_llm_configs, outputs=llm_refresh_outputs
        ).then(
            handlers.clear_llm_form_inputs, outputs=llm_select_outputs
        )
        
        # 5. 删除按钮
        llm_ui["delete_btn"].click(
            handlers.handle_delete_llm_config, 
            inputs=[llm_ui["config_id_state"]], 
            outputs=[llm_ui["action_status_output"]],
            js='_ => confirm("您确定要删除这个配置吗？此操作无法撤销。")'
        ).then(
            handlers.refresh_llm_configs, outputs=llm_refresh_outputs
        ).then(
             handlers.clear_llm_form_inputs, outputs=llm_select_outputs
        )
        
        # 6. 设为当前服务按钮
        llm_ui["set_active_btn"].click(
            handlers.handle_set_active_llm_config,
            inputs=[llm_ui["config_id_state"]],
            outputs=[llm_ui["action_status_output"]]
        ).then(
            handlers.refresh_llm_configs, outputs=llm_refresh_outputs
        )
        # ========================== END: MODIFICATION ============================

    # --- 4. Launch the App ---
    print("EMinder 前端控制中心即将启动...")
    demo.launch(server_name="0.0.0.0", server_port=config.run_port, inbrowser=False)

# ========================== END: MODIFICATION (Wiring and Robustness) ============================