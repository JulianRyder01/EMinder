# backend/app/api/jobs.py (已修改)
from fastapi import APIRouter, HTTPException
from ..services.scheduler_service import scheduler_service
from apscheduler.jobstores.base import JobLookupError
import datetime

router = APIRouter()

@router.get("/jobs")
def get_scheduled_jobs():
    """
    【修改点】获取所有当前计划中的任务，包括一次性和周期性任务。
    """
    jobs_list = []
    # 遍历所有任务，不再进行 trigger 类型过滤
    for job in scheduler_service.scheduler.get_jobs():
        next_run = job.next_run_time
        # 将 datetime 对象转换为 ISO 8601 格式的字符串，方便前端处理
        run_time_str = next_run.isoformat() if next_run else None

        jobs_list.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": run_time_str,
            "args": job.args, # 任务执行时所需的参数
            "trigger": str(job.trigger), # 返回触发器的字符串表示，例如 cron[minute='0', hour='8']
        })
            
    return {"status": "success", "jobs": jobs_list}


@router.delete("/jobs/{job_id}")
def cancel_scheduled_job(job_id: str):
    """
    根据任务 ID 取消一个已计划的任务。
    """
    try:
        scheduler_service.scheduler.remove_job(job_id)
        print(f"任务 {job_id} 已被用户请求取消。")
        return {"status": "success", "message": f"任务 {job_id} 已成功取消。"}
    except JobLookupError:
        print(f"尝试取消一个不存在的任务: {job_id}")
        raise HTTPException(status_code=404, detail=f"未找到ID为 {job_id} 的任务。")
    except Exception as e:
        # 【修改点】对于周期性任务，如果前端尝试取消，APScheduler会抛出不同类型的错误
        # 这里统一处理，使其更加健壮
        print(f"取消任务 {job_id} 时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"取消任务时发生错误: {str(e)}")