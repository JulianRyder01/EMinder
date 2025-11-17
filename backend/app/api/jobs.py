# backend/app/api/jobs.py
from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
import logging
from ..services.scheduler_service import scheduler_service
from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/jobs")
def get_scheduled_jobs():
    jobs_list = []
    # 遍历所有任务，不再进行 trigger 类型过滤
    for job in scheduler_service.scheduler.get_jobs():
        next_run = job.next_run_time
        # 将 datetime 对象转换为 ISO 8601 格式的字符串，方便前端处理
        run_time_str = next_run.isoformat() if next_run else None

        job_type = "unknown"
        if isinstance(job.trigger, CronTrigger):
            job_type = "cron"
        elif isinstance(job.trigger, DateTrigger):
            job_type = "date"

        jobs_list.append({
            "id": job.id,
            "name": job.name,
            "job_type": job_type, # 新增字段，方便前端区分
            "next_run_time": run_time_str,
            # <--- 核心修正 1: 返回 job.kwargs 而不是 job.args
            "kwargs": job.kwargs,
            "trigger": str(job.trigger),
        })
            
    return {"status": "success", "jobs": jobs_list}

@router.get("/jobs/{job_id}")
def get_job_details(job_id: str):
    """
    【新增】根据任务 ID 获取单个任务的详细信息，用于填充编辑表单。
    """
    try:
        job = scheduler_service.scheduler.get_job(job_id)
        if not job:
            # 这里的 raise JobLookupError 是正确的，但不需要传递参数
            # 因为 APScheduler 的 get_job 在找不到时返回 None，我们手动触发异常流程
            raise JobLookupError
        
        job_details = {
            "id": job.id,
            "name": job.name,
            **job.kwargs  # <--- 使用字典解包，将所有任务参数包含进来
        }

        if isinstance(job.trigger, DateTrigger):
            job_details["trigger_type"] = "date"
            # APScheduler 存储的是带时区的 datetime 对象，我们格式化为前端需要的字符串
            job_details["run_date"] = job.trigger.run_date.strftime("%Y-%m-%d %H:%M")
        elif isinstance(job.trigger, CronTrigger):
            job_details["trigger_type"] = "cron"
            # 从 trigger 对象中安全地重建 Cron 表达式字符串
            # 字段顺序: year, month, day, week, day_of_week, hour, minute, second
            fields = job.trigger.fields
            minute = str(fields[6])
            hour = str(fields[5])
            day = str(fields[2])
            month = str(fields[1])
            day_of_week = str(fields[4])
            job_details["cron_string"] = f"{minute} {hour} {day} {month} {day_of_week}"
        else:
            job_details["trigger_type"] = "unknown"

        return {"status": "success", "job": job_details}

    except JobLookupError:
        # ========================== START: MODIFICATION (Backend Error Fix) ==========================
        # DESIGNER'S NOTE:
        # 相应地，我们现在可以捕获正确的 JobLookupError 并返回一个标准的 404 错误。
        raise HTTPException(status_code=404, detail=f"未找到ID为 {job_id} 的任务。")
        # ========================== END: MODIFICATION (Backend Error Fix) ============================
    except Exception as e:
        logger.error(f"Error getting details for job '{job_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取任务详情时发生错误: {str(e)}")

@router.put("/jobs/{job_id}")
async def update_scheduled_job(job_id: str, payload: Dict[str, Any] = Body(...)):
    """
    【新增】根据任务 ID 修改一个已存在的计划任务。
    """
    try:
        job = scheduler_service.scheduler.get_job(job_id)
        if not job:
            raise JobLookupError
        
        trigger_type = payload.get("trigger_type")

        # --- 更新一次性任务 ---
        if trigger_type == "date":
            run_date_str = payload.get("send_at")
            if not run_date_str:
                 raise HTTPException(status_code=422, detail="缺少 'send_at' 字段。")

            try:
                naive_dt = datetime.datetime.strptime(run_date_str, "%Y-%m-%d %H:%M")
                aware_dt = scheduler_service.scheduler.timezone.localize(naive_dt)
            except ValueError:
                raise HTTPException(status_code=422, detail="时间格式错误，请使用 'YYYY-MM-DD HH:MM' 格式。")

            # 构建新的 kwargs 字典
            new_kwargs = {
                "job_id": job_id, # 保持 job_id
                "receiver_email": payload.get("receiver_email"),
                "template_type": payload.get("template_type"),
                "template_data": payload.get("template_data", {}),
                "custom_subject": payload.get("custom_subject"),
                "temp_file_paths": job.kwargs.get("temp_file_paths", []) # 保留旧的附件
            }
            
            scheduler_service.scheduler.modify_job(job_id, kwargs=new_kwargs) # <-- 使用 kwargs
            scheduler_service.scheduler.reschedule_job(job_id, trigger='date', run_date=aware_dt)
            
            logger.info(f"API: Job [ID: {job_id}] was successfully updated. New run time: {aware_dt}")
            return {"status": "success", "message": f"任务 {job_id} 已成功更新。"}

        # --- 更新周期性任务 ---
        elif trigger_type == "cron":
            new_kwargs = {
                "job_id": job_id,
                "job_name": payload.get("job_name"),
                "receiver_emails": payload.get("receiver_emails", []),
                "template_type": payload.get("template_type"),
                "template_data": payload.get("template_data", {}),
                "custom_subject": payload.get("custom_subject")
            }
            new_name = payload.get("job_name")

            scheduler_service.scheduler.modify_job(job_id, name=new_name, kwargs=new_kwargs) # <-- 使用 kwargs

            new_cron = payload.get("cron_string")
            if new_cron:
                parts = new_cron.split()
                if len(parts) != 5:
                    raise HTTPException(status_code=422, detail="Cron 表达式必须包含5个部分 (分 时 日 月 周)。")
                
                scheduler_service.scheduler.reschedule_job(
                    job_id, 
                    trigger='cron', 
                    minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]
                )
            
            logger.info(f"API: Cron job [ID: {job_id}] was successfully updated. New name: '{new_name}', New cron: '{new_cron}'.")
            return {"status": "success", "message": f"周期任务 {job_id} 已成功更新。"}
        else:
            raise HTTPException(status_code=422, detail="请求中缺少有效的 'trigger_type'。")

    except JobLookupError:
        raise HTTPException(status_code=404, detail=f"未找到ID为 {job_id} 的任务。")
    except Exception as e:
        logger.error(f"API: Error updating job '{job_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新任务时发生错误: {str(e)}")


@router.delete("/jobs/{job_id}")
def cancel_scheduled_job(job_id: str):
    """
    根据任务 ID 取消一个已计划的任务。
    """
    try:
        scheduler_service.scheduler.remove_job(job_id)
        logger.info(f"API: Job [ID: {job_id}] was successfully cancelled by user request.")
        return {"status": "success", "message": f"任务 {job_id} 已成功取消。"}
    except JobLookupError:
        logger.warning(f"API: Attempted to cancel a non-existent job with ID: {job_id}")
        raise HTTPException(status_code=404, detail=f"未找到ID为 {job_id} 的任务。")
    except Exception as e:
        logger.error(f"API: Error cancelling job '{job_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"取消任务时发生错误: {str(e)}")