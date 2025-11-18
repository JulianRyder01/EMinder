# backend/app/api/subscribers.py (已修改)
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Body, Form, File, UploadFile
from typing import Dict, Optional, List # <-- 新增导入 List
from croniter import croniter
import uuid
import asyncio
import json
import os
import shutil
import logging
from ..storage.sqlite_store import store
# ========================== START: MODIFICATION (Async Job Execution Fix) ==========================
# DESIGNER'S NOTE:
# 这里的导入也得到了简化。我们不再需要 _run_async_job，
# 只需要 scheduler_service 实例和 SchedulerService 类（用于引用静态方法）。
from ..services.scheduler_service import scheduler_service, SchedulerService
# ========================== END: MODIFICATION (Final Async Fix) ============================
from ..services.email_service import email_service
from ..templates.email_templates import template_manager
import datetime
import pytz
from urllib.parse import unquote

router = APIRouter()
logger = logging.getLogger(__name__)

# --- 辅助函数：处理临时文件 ---
def save_temp_upload_file(upload_file: UploadFile) -> Optional[str]:
    """将上传的文件保存到临时目录，并返回其绝对路径。"""
    if not upload_file:
        return None
    try:
        # 创建一个唯一的文件名以避免冲突
        temp_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'temp_uploads')
        unique_filename = f"{uuid.uuid4().hex}_{upload_file.filename}"
        file_path = os.path.join(temp_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
            
        return file_path
    except Exception as e:
        logger.error(f"Failed to save temporary upload file: {e}", exc_info=True)
        return None
    finally:
        upload_file.file.close()

# ... (get_all_subscribers, add_subscriber, update_subscriber, delete_subscriber 方法保持不变) ...
@router.get("/subscribers")
def get_all_subscribers():
    """
    获取所有已确认的订阅者列表。
    前端将调用此接口来可视化订阅账号。
    """
    try:
        active_subscribers = store.get_active_subscribers()
        return {"status": "success", "subscribers": active_subscribers}
    except Exception as e:
        logger.error(f"Error getting subscriber list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取订阅者列表时发生内部错误。")

@router.post("/subscribers")
async def add_subscriber(payload: Dict = Body(...)):
    """直接添加一个订阅者"""
    email = payload.get("email")
    remark_name = payload.get("remark_name")

    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="提供了无效的邮箱地址。")
    
    if not remark_name:
        # 如果备注名为空，默认使用邮箱前缀
        remark_name = email.split('@')[0]

    success = store.add_subscriber(email, remark_name)
    
    if success:
        return {"status": "success", "message": f"已成功添加/更新订阅者: {remark_name} <{email}>"}
    else:
        raise HTTPException(status_code=500, detail="添加订阅者时发生数据库错误。")

@router.put("/subscribers/{email}")
async def update_subscriber(email: str, payload: Dict = Body(...)):
    """【新增】更新订阅者的备注名"""
    email = unquote(email) # URL解码邮箱地址
    new_remark_name = payload.get("remark_name")

    if not new_remark_name:
        raise HTTPException(status_code=422, detail="备注名不能为空。")

    success = store.update_subscriber(email, new_remark_name)
    if success:
        return {"status": "success", "message": f"已成功将 {email} 的备注更新为 {new_remark_name}。"}
    else:
        raise HTTPException(status_code=404, detail=f"未找到邮箱为 {email} 的订阅者。")

@router.delete("/subscribers/{email}")
async def delete_subscriber(email: str):
    """【新增】删除一个订阅者"""
    email = unquote(email) # URL解码邮箱地址
    success = store.delete_subscriber(email)
    if success:
        return {"status": "success", "message": f"已成功删除订阅者 {email}。"}
    else:
        raise HTTPException(status_code=404, detail=f"未找到邮箱为 {email} 的订阅者。")


@router.post("/send-now")
async def send_email_now(
    background_tasks: BackgroundTasks,
    receiver_email: str = Form(...),
    template_type: str = Form(...),
    template_data_str: str = Form(...),
    custom_subject: Optional[str] = Form(None),
# ========================== START: MODIFICATION (需求 ①) ==========================
    silent_run: bool = Form(False),
# ========================== END: MODIFICATION (需求 ①) ============================
    attachments: List[UploadFile] = File(default=[])
):
    if not receiver_email or not template_type:
        raise HTTPException(status_code=422, detail="请求体中缺少 'receiver_email' 或 'template_type'。")

    try:
        template_data = json.loads(template_data_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的 template_data JSON 字符串。")

    temp_file_paths = []
    if attachments:
        for attachment in attachments:
            temp_path = save_temp_upload_file(attachment)
            if temp_path:
                temp_file_paths.append(temp_path)
    
    template_func = getattr(template_manager, template_type, None)
    
    if not template_func:
        # 确保在出错时清理已上传的临时文件
        for path in temp_file_paths: os.remove(path)
        raise HTTPException(status_code=404, detail=f"模板 '{template_type}' 未找到。")
    
    # 【异步修复】由于模板函数可能为异步（例如调用大模型），这里必须 await
    # TemplateManager 的包装器确保了所有模板都可以被 await
    email_content = await template_func(template_data)
    
    final_subject = custom_subject if custom_subject else email_content["subject"]
    
    # 将模板自身生成的附件路径与用户上传的临时文件路径合并
    final_attachments = email_content.get("attachments", []) + temp_file_paths

# ========================== START: MODIFICATION (需求 ①) ==========================
    # DESIGNER'S NOTE:
    # 对于“立即发送”，我们直接在API层判断。如果为静默运行，则只记录日志，不添加邮件发送任务。
    # 模板自身的逻辑（如文件操作）已经在上面 await template_func(template_data) 时执行完毕。
    if silent_run:
        logger.info(f"Silent run triggered for 'send-now'. Template '{template_type}' logic executed, but email to {receiver_email} was suppressed.")
        message = "静默运行成功！模板逻辑已执行，邮件未发送。"
    else:
        background_tasks.add_task(
            email_service.send_email,
            receiver_email,
            final_subject,
            email_content["html"],
            attachments=final_attachments, # 传递合并后的附件列表
            embedded_images=email_content.get("embedded_images", [])
        )
        message = f"邮件正在发送至 {receiver_email}。"
# ========================== END: MODIFICATION (需求 ①) ============================
    
    # 为所有临时文件添加清理任务
    if temp_file_paths:
        for path in temp_file_paths:
            background_tasks.add_task(os.remove, path)
    
    return {"status": "success", "message": message}


@router.post("/schedule-once")
async def schedule_email_once(
    receiver_email: str = Form(...),
    template_type: str = Form(...),
    send_at_str: str = Form(...),
    template_data_str: str = Form(...),
    custom_subject: Optional[str] = Form(None),
# ========================== START: MODIFICATION (需求 ①) ==========================
    silent_run: bool = Form(False),
# ========================== END: MODIFICATION (需求 ①) ============================
    attachments: List[UploadFile] = File(default=[])
):
    """
    调度一个一次性的邮件发送任务，支持动态模板字段和可选的文件附件。
    """
    if not all([receiver_email, template_type, send_at_str]):
        raise HTTPException(status_code=422, detail="请求体中缺少 'receiver_email', 'template_type' 或 'send_at'。")

    try:
        template_data = json.loads(template_data_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的 template_data JSON 字符串。")
        
    try:
        naive_dt = datetime.datetime.strptime(send_at_str, "%Y-%m-%d %H:%M")
        tz = pytz.timezone(str(scheduler_service.scheduler.timezone))
        aware_dt = tz.localize(naive_dt)
    except ValueError:
        raise HTTPException(status_code=422, detail="时间格式错误，请使用 'YYYY-MM-DD HH:MM' 格式。")

    temp_file_paths = []
    if attachments:
        for attachment in attachments:
            temp_path = save_temp_upload_file(attachment)
            if temp_path:
                temp_file_paths.append(temp_path)

    job_id = f"once_{template_type}_{uuid.uuid4().hex[:8]}"

    task_kwargs = {
        "job_id": job_id,
        "receiver_email": receiver_email,
        "template_type": template_type,
        "template_data": template_data,
        "custom_subject": custom_subject,
        "temp_file_paths": temp_file_paths,
# ========================== START: MODIFICATION (需求 ①) ==========================
        "silent_run": silent_run  # 将静默运行标志传递给任务
# ========================== END: MODIFICATION (需求 ①) ============================
    }

    job = scheduler_service.scheduler.add_job(
        SchedulerService.send_single_email_task,
        trigger='date',
        run_date=aware_dt,
        kwargs=task_kwargs,
        id=job_id,
        name=f"One-time email to {receiver_email} using template {template_type}"
    )
    
    logger.info(f"API: Successfully scheduled one-time job. [ID: {job.id}, RunTime: {aware_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}]")

    return {
        "status": "success", 
        "message": f"任务已成功调度！邮件将在 {aware_dt.strftime('%Y-%m-%d %H:%M:%S %Z')} 发送至 {receiver_email}。",
        "job_id": job.id
    }

@router.post("/schedule-cron")
async def schedule_email_cron(request: Request):
    """
    【新增】通过 Cron 表达式调度一个周期性的邮件发送任务。
    【新增】支持 custom_subject 字段。
    【注意】周期性任务不支持即时文件上传，文件来源需由模板自身逻辑定义（例如从固定服务器路径读取）。
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 JSON 请求体。")

    job_name = payload.get("job_name")
    cron_string = payload.get("cron_string")
    template_type = payload.get("template_type")
    template_data = payload.get("template_data", {})
    receiver_emails = payload.get("receiver_emails", [])
    custom_subject = payload.get("custom_subject") # 新增
# ========================== START: MODIFICATION (需求 ①) ==========================
    silent_run = payload.get("silent_run", False) # 新增
# ========================== END: MODIFICATION (需求 ①) ============================

    if not all([job_name, cron_string, template_type, receiver_emails]):
        raise HTTPException(status_code=422, detail="请求体中缺少 'job_name', 'cron_string', 'template_type' 或 'receiver_emails'。")
    
    if not croniter.is_valid(cron_string):
        raise HTTPException(status_code=422, detail="提供了无效的 Cron 表达式。")

    # 生成一个唯一的 job_id
    job_id = f"cron_{template_type}_{uuid.uuid4().hex[:8]}"
    
    try:
        logger.info(f"API: Received request to schedule a new cron job. [Name: {job_name}, Cron: '{cron_string}']")

        task_kwargs = {
            "receiver_emails": receiver_emails,
            "template_type": template_type,
            "template_data": template_data,
            "custom_subject": custom_subject,
# ========================== START: MODIFICATION (需求 ①) ==========================
            "silent_run": silent_run  # 将静默运行标志传递给任务
# ========================== END: MODIFICATION (需求 ①) ============================
        }
        
        job = scheduler_service.add_cron_job(
            job_id=job_id,
            name=job_name,
            cron_string=cron_string,
            task_kwargs=task_kwargs # <-- 核心改变：传递字典
        )
        return {
            "status": "success",
            "message": f"周期任务 '{job_name}' 已成功调度！",
            "job_id": job.id
        }
    except ValueError as e:
        logger.warning(f"API: Failed to schedule cron job '{job_name}' due to validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"API: An unexpected error occurred while scheduling cron job '{job_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"调度任务时发生内部错误: {str(e)}")