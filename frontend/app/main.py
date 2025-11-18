# frontend/app/main.py
# ========================== START: MODIFICATION (Wiring and Robustness) ==========================
# DESIGNER'S NOTE:
# This file assembles the UI and wires the event handlers.
# Key fixes and restorations have been made here:
# 1. **Complete Data Loading**: Ensured that on app start, ALL dropdowns and lists across ALL tabs
#    (including the previously missed 'Edit Job' form) are populated with data.
# 2. **Confirmation Dialog**: Re-instated the crucial 'confirm' dialog for the 'Cancel Job' button.
# 3. **Smart Navigation**: The `.then()` chain for creating tasks now uses a handler (`navigate_on_success`)
#    to conditionally navigate to the jobs tab only on success.
# 4. **'Run Now' Wiring**: The new 'Run Now' button is now correctly wired to its handler.

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

        # --- 3. Wire Event Handlers ---

        # App Load Events
        demo.load(handlers.check_backend_status, outputs=backend_status)
        
        # ========================== START: CORRECTION (Omission Fix) ==========================
        # DESIGNER'S NOTE:
        # 这是对上次提交中重大遗漏的修正。
        # 之前的代码只为主Tab页加载了模板和订阅者，导致其他Tab页的下拉框是空的。
        # 现在的代码确保了在应用启动时，所有需要这些数据的UI组件都能被正确填充。

        # Initial data loading for templates - targets ALL template dropdowns across ALL tabs.
        demo.load(
            handlers.load_templates_info, 
            outputs=[
                manual_ui["template_dd"], manual_ui["load_status"],
                schedule_ui["template_dd"], schedule_ui["load_status"],
                cron_ui["template_dd"], cron_ui["load_status"],
                jobs_ui["edit_template_dd"] # <-- 遗漏点：任务编辑区的模板下拉框
            ]
        )
        
        # Initial data loading for subscribers - targets ALL subscriber components.
        demo.load(
            handlers.refresh_subscribers_list, 
            outputs=[
                sub_ui["dataframe"], sub_ui["status_output"], 
                shared_receiver_dd,             # <-- The single shared dropdown
                cron_ui["receiver_subscribers"],# <-- Cron job subscriber checkboxes
                jobs_ui["edit_date_receiver"]   # <-- Job edit 'date' receiver dropdown
            ]
        )
        # ========================== END: CORRECTION (Omission Fix) ============================


        # Subscriber Management Tab Events
        sub_refresh_outputs = [sub_ui["dataframe"], sub_ui["status_output"], shared_receiver_dd, cron_ui["receiver_subscribers"], jobs_ui["edit_date_receiver"]]
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
            handlers.cancel_job_by_id, inputs=[jobs_ui["job_id_input"]], outputs=[jobs_ui["cancel_status"]],
            js='_ => confirm("您确定要取消这个计划任务吗？此操作无法撤销。")'
        ).then(handlers.get_jobs_list, outputs=[jobs_ui["dataframe"], jobs_ui["status_output"]])
        jobs_ui["run_now_btn"].click(handlers.handle_run_job_now, inputs=[jobs_ui["job_id_input"]], outputs=[jobs_ui["cancel_status"]])

        # Job Edit Form Events
        edit_form_outputs_list = [
            jobs_ui["edit_column"], jobs_ui["job_id_input"], jobs_ui["edit_id_state"], jobs_ui["edit_type_state"],
            jobs_ui["edit_template_dd"], jobs_ui["edit_custom_subject"], jobs_ui["edit_cron_group"], jobs_ui["edit_date_group"],
            jobs_ui["edit_cron_name"], jobs_ui["edit_cron_string"], jobs_ui["edit_cron_subscribers"],
            jobs_ui["edit_date_receiver"], jobs_ui["edit_date_send_at"], jobs_ui["edit_silent_run_checkbox"]
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

    # --- 4. Launch the App ---
    print("EMinder 前端控制中心即将启动...")
    demo.launch(server_name="0.0.0.0", server_port=config.run_port, inbrowser=False)

# ========================== END: MODIFICATION (Wiring and Robustness) ============================