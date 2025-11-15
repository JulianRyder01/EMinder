# backend/app/api/subscribers.py (已修改)
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Body
from typing import Dict
from croniter import croniter  # 新增导入
import uuid  # 新增导入
# 【修改点】导入重命名后的 sqlite_store
from ..storage.sqlite_store import store
from ..services.scheduler_service import scheduler_service
from ..services.email_service import email_service
from ..templates.email_templates import template_manager
import datetime
import pytz
from urllib.parse import unquote

router = APIRouter()

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
        print(f"获取订阅者列表时出错: {e}")
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

# 【修改点】原有的 /subscribe 和 /confirm 端点已废弃，被新的 /subscribers 增删改查 API 替代
# 保留邮件发送相关的 API

@router.post("/send-now")
async def send_email_now(request: Request, background_tasks: BackgroundTasks):
    """
    立即发送一封指定的邮件。
    现在接收 JSON body，以支持动态模板字段。
    【新增】支持 custom_subject 字段。
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 JSON 请求体。")

    receiver_email = payload.get("receiver_email")
    template_type = payload.get("template_type")
    template_data = payload.get("template_data", {})
    custom_subject = payload.get("custom_subject") # 新增

    if not receiver_email or not template_type:
        raise HTTPException(status_code=422, detail="请求体中缺少 'receiver_email' 或 'template_type'。")

    template_func_name = f"get_{template_type}_template"
    template_func = getattr(template_manager, template_type, None)
    
    if not template_func:
        raise HTTPException(status_code=404, detail=f"模板 '{template_type}' 未找到。")
    
    email_content = template_func(template_data)
    
    # 【修改】决定最终使用的标题
    final_subject = custom_subject if custom_subject else email_content["subject"]
    
    background_tasks.add_task(
        email_service.send_email,
        receiver_email,
        final_subject,
        email_content["html"]
    )
    
    return {"status": "success", "message": f"邮件正在发送至 {receiver_email}。"}


@router.post("/schedule-once")
async def schedule_email_once(request: Request):
    """
    调度一个一次性的邮件发送任务。
    现在接收 JSON body。
    【新增】支持 custom_subject 字段。
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 JSON 请求体。")
        
    receiver_email = payload.get("receiver_email")
    template_type = payload.get("template_type")
    send_at_str = payload.get("send_at") # 格式: "YYYY-MM-DD HH:MM"
    template_data = payload.get("template_data", {})
    custom_subject = payload.get("custom_subject") # 新增

    if not all([receiver_email, template_type, send_at_str]):
        raise HTTPException(status_code=422, detail="请求体中缺少 'receiver_email', 'template_type' 或 'send_at'。")

    try:
        naive_dt = datetime.datetime.strptime(send_at_str, "%Y-%m-%d %H:%M")
        tz = pytz.timezone(str(scheduler_service.scheduler.timezone))
        aware_dt = tz.localize(naive_dt)
    except ValueError:
        raise HTTPException(status_code=422, detail="时间格式错误，请使用 'YYYY-MM-DD HH:MM' 格式。")

    # 【修改】将 custom_subject 添加到传递给任务的参数列表中
    job = scheduler_service.scheduler.add_job(
        scheduler_service.send_single_email_task,
        trigger='date',
        run_date=aware_dt,
        args=[receiver_email, template_type, template_data, custom_subject],
        id=f"once_{receiver_email}_{datetime.datetime.now().timestamp()}",
        name=f"One-time email to {receiver_email}"
    )

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

    if not all([job_name, cron_string, template_type, receiver_emails]):
        raise HTTPException(status_code=422, detail="请求体中缺少 'job_name', 'cron_string', 'template_type' 或 'receiver_emails'。")
    
    if not croniter.is_valid(cron_string):
        raise HTTPException(status_code=422, detail="提供了无效的 Cron 表达式。")

    # 生成一个唯一的 job_id
    job_id = f"cron_{template_type}_{uuid.uuid4().hex[:8]}"
    
    try:
        # 【修改】将 custom_subject 添加到传递给任务的参数列表中
        job = scheduler_service.add_cron_job(
            job_id=job_id,
            name=job_name,
            cron_string=cron_string,
            args=[receiver_emails, template_type, template_data, custom_subject]
        )
        return {
            "status": "success",
            "message": f"周期任务 '{job_name}' 已成功调度！",
            "job_id": job.id
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"调度周期任务时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"调度任务时发生内部错误: {str(e)}")