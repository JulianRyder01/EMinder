# backend/app/services/scheduler_service.py (已修正序列化错误)
import datetime
import asyncio
import os
# ========================== START: MODIFICATION (Async Job Execution Fix) ==========================
# DESIGNER'S NOTE: 导入 functools 用于更灵活地创建可调用对象，这是我们通用包装器的一部分。
import functools
# ========================== END: MODIFICATION (Async Job Execution Fix) ============================
import logging
# ========================== START: MODIFICATION (Final Async Fix) ==========================
# DESIGNER'S NOTE:
# 关键变更：我们不再使用为多线程环境设计的 BackgroundScheduler，
# 而是切换到为 asyncio 应用量身打造的 AsyncIOScheduler。
# 这将从根本上解决 "coroutine was never awaited" 的问题。
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# ========================== END: MODIFICATION (Final Async Fix) ============================
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from croniter import croniter
from ..core.config import settings
from .email_service import email_service
from ..templates.email_templates import template_manager
from ..storage.sqlite_store import store

# ========================== START: MODIFICATION (Logging) ==========================
# DESIGNER'S NOTE: 获取一个 logger 实例，用于记录此模块中的事件。
logger = logging.getLogger(__name__)
# ========================== END: MODIFICATION (Logging) ============================


# --- 【核心修正点】 ---
# 将执行周期性任务的逻辑移到一个独立的、顶级的函数中。
# 这样做是为了解决 APScheduler 的序列化问题。当任务被持久化到数据库时，
# APScheduler 无法序列化一个包含调度器实例的对象 (self)。
# 将其作为普通函数，就不再有关联的 self 对象，问题迎刃而解。
async def _send_recurring_emails_task():
    """【异步改造】扫描订阅者并发送相应模板的邮件。这是一个独立的函数，用于周期性任务。"""
    print(f"\n[{datetime.datetime.now()}] --- 开始执行定时邮件发送任务 ---")
    active_subscribers = store.get_active_subscribers()

    if not active_subscribers:
        print("没有活跃的订阅者，本次任务结束。")
        return

    tasks = []
    for sub in active_subscribers:
        email = sub["email"]
        template_type = sub.get("template_type", "daily_summary")

        # --- 模拟为每个用户生成动态数据 ---
        mock_data = {
            "player_name": email.split('@')[0],
            "tasks_completed": 5,
            "level": 12,
            "progress": 80,
            "todo_list": ["完成项目报告", "学习 FastAPI", "锻炼30分钟"]
        }

        template_func = getattr(template_manager, template_type, None)
        
        if template_func:
            # 检查模板函数是否为异步
            if asyncio.iscoroutinefunction(template_func):
                email_content = await template_func(mock_data)
            else:
                email_content = template_func(mock_data)

            # 创建异步发送任务
            task = email_service.send_email(
                receiver_email=email,
                subject=email_content["subject"],
                html_content=email_content["html"]
            )
            tasks.append(task)
        else:
            print(f"警告：未找到名为 '{template_type}' 的邮件模板，无法为 {email} 发送。")
    
    # 并发执行所有邮件发送任务
    if tasks:
        await asyncio.gather(*tasks)
    
    print("--- 定时邮件发送任务执行完毕 ---\n")

async def _send_custom_cron_email_task(**kwargs):
    """
    【重构】这是一个独立的函数，用于用户自定义的周期性任务。
    现在通过 kwargs 接收所有参数。
    """
    # 从 kwargs 中安全地提取参数
    job_id = kwargs.get("job_id", "unknown_id")
    job_name = kwargs.get("job_name", "untitled_cron")
    receiver_emails = kwargs.get("receiver_emails", [])
    template_type = kwargs.get("template_type")
    data = kwargs.get("template_data", {})
    custom_subject = kwargs.get("custom_subject")
# ========================== START: MODIFICATION (需求 ①) ==========================
    silent_run = kwargs.get("silent_run", False)
# ========================== END: MODIFICATION (需求 ①) ============================

    logger.info(f"Executing cron job: [ID: {job_id}, Name: {job_name}]. Sending template '{template_type}' to {len(receiver_emails)} recipients.")
    try:
    # ========================== END: MODIFICATION (Logging) ============================
        if not receiver_emails:
            logger.warning(f"Cron job [ID: {job_id}] skipped: Recipient list is empty.")
            return
            
        if not template_type:
            logger.error(f"Cron job [ID: {job_id}] failed: Template type was not provided.")
            return

        template_func = getattr(template_manager, template_type, None)
        if not template_func:
            logger.error(f"Cron job [ID: {job_id}] failed: Template '{template_type}' not found.")
            return

        # 检查模板函数是否为异步
        email_content = await template_func(data)
        
        # 【修改】如果提供了自定义标题，则使用它；否则，使用模板的默认标题。
        final_subject = custom_subject if custom_subject else email_content["subject"]
        
        # 从模板函数的返回结果中提取附件路径列表 (新)
        attachments_to_send = email_content.get("attachments", [])
        embedded_images_to_send = email_content.get("embedded_images", [])

# ========================== START: MODIFICATION (需求 ①) ==========================
        if silent_run:
            logger.info(f"Silent run for cron job [ID: {job_id}, Name: {job_name}]. Email sending was suppressed.")
        else:
            tasks = []
            for email in receiver_emails:
                task = email_service.send_email(
                    receiver_email=email,
                    subject=final_subject,
                    html_content=email_content["html"],
                    attachments=attachments_to_send,
                    embedded_images=embedded_images_to_send,
                )
                tasks.append(task)
                
            # 并发执行所有邮件发送任务
            if tasks:
                await asyncio.gather(*tasks)
# ========================== END: MODIFICATION (需求 ①) ============================
        
        # ========================== START: MODIFICATION (Logging) ==========================
        logger.info(f"Cron job [ID: {job_id}, Name: {job_name}] executed successfully.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in cron job [ID: {job_id}, Name: {job_name}]: {e}", exc_info=True)

# ========================== START: MODIFICATION (Async Job Execution Fix) ==========================
# DESIGNER'S NOTE:
# 上一版方案中的 _run_async_job 同步包装器现在已完全没有必要，
# 因为 AsyncIOScheduler 本身就在正确的事件循环中运行。我们将其彻底移除。
# ========================== END: MODIFICATION (Final Async Fix) ============================


class SchedulerService:
    """管理所有后台定时任务"""
    def __init__(self):
        jobstores = {
            'default': SQLAlchemyJobStore(url=settings.DATABASE_URL)
        }
        # ========================== START: MODIFICATION (Final Async Fix) ==========================
        # DESIGNER'S NOTE:
        # 使用 AsyncIOScheduler 替换 BackgroundScheduler。
        # 它会自动使用当前线程的事件循环，与 FastAPI 完美集成。
        self.scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="Asia/Taipei")
        # ========================== END: MODIFICATION (Final Async Fix) ============================
        logger.info(f"Scheduler initialized with timezone '{self.scheduler.timezone}' and job store '{settings.DATABASE_URL}'.")
        # ========================== END: MODIFICATION (Logging) ============================


    # 【修改点】原有的 _send_scheduled_emails 实例方法已被上面的顶级函数替代，故删除。

    @staticmethod
    # ========================== START: MODIFICATION (Refactor to kwargs) ==========================
    async def send_single_email_task(**kwargs):
        """【重构】这是一个静态方法，专门被 APScheduler 调用来执行一次性任务。"""
        job_id = kwargs.get("job_id", "unknown_id")
        receiver_email = kwargs.get("receiver_email")
        template_type = kwargs.get("template_type")
        data = kwargs.get("template_data", {})
        custom_subject = kwargs.get("custom_subject")
        temp_file_paths = kwargs.get("temp_file_paths", [])
# ========================== START: MODIFICATION (需求 ①) ==========================
        silent_run = kwargs.get("silent_run", False)
# ========================== END: MODIFICATION (需求 ①) ============================

        logger.info(f"Executing one-time job: [ID: {job_id}]. Sending template '{template_type}' to '{receiver_email}'.")
        # ========================== END: MODIFICATION (Logging) ============================
        try:
            if not receiver_email or not template_type:
                logger.error(f"One-time job [ID: {job_id}] failed: Missing receiver_email or template_type.")
                return

            template_func = getattr(template_manager, template_type, None)
            if template_func:
                email_content = await template_func(data)
                final_subject = custom_subject if custom_subject else email_content["subject"]
                
                # 将模板自身生成的附件与用户上传的临时文件附件合并
                final_attachments = email_content.get("attachments", [])
                if temp_file_paths:
                    for temp_path in temp_file_paths:
                        if os.path.exists(temp_path):
                            final_attachments.append(temp_path)
                
# ========================== START: MODIFICATION (需求 ①) ==========================
                if silent_run:
                    logger.info(f"Silent run for one-time job [ID: {job_id}]. Email sending was suppressed.")
                else:
                    await email_service.send_email(
                        receiver_email,
                        final_subject,
                        email_content["html"],
                        attachments=final_attachments,
                        embedded_images=email_content.get("embedded_images", [])
                    )
# ========================== END: MODIFICATION (需求 ①) ============================
                logger.info(f"One-time job [ID: {job_id}] executed successfully.")
            else:
                logger.error(f"One-time job [ID: {job_id}] failed: Template '{template_type}' not found.")
        except Exception as e:
            logger.error(f"An unexpected error occurred in one-time job [ID: {job_id}]: {e}", exc_info=True)
        finally:
            if temp_file_paths:
                for temp_path in temp_file_paths:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                            logger.info(f"Job [ID: {job_id}]: Successfully cleaned up temporary file: {temp_path}")
                        except Exception as e:
                            logger.warning(f"Job [ID: {job_id}]: Failed to clean up temporary file {temp_path}: {e}")
    
    def add_cron_job(self, job_id: str, name: str, cron_string: str, task_kwargs: dict):
        """【重构】添加一个由 Cron 表达式定义的周期性任务，使用 kwargs 传递参数。"""
        if not croniter.is_valid(cron_string):
            logger.error(f"Failed to add cron job '{name}'. Invalid cron string: '{cron_string}'")
            raise ValueError(f"无效的 Cron 表达式: '{cron_string}'")

        parts = cron_string.split()
        if len(parts) != 5:
            logger.error(f"Failed to add cron job '{name}'. Cron string must have 5 parts: '{cron_string}'")
            raise ValueError("Cron 表达式必须包含5个部分 (分 时 日 月 周)。")
        
        task_kwargs['job_id'] = job_id
        task_kwargs['job_name'] = name

        # ========================== START: MODIFICATION (Final Async Fix) ==========================
        # DESIGNER'S NOTE:
        # 因为我们现在处于一个纯粹的异步环境中，我们可以直接将异步任务函数 `_send_custom_cron_email_task`
        # 添加到调度器。不再需要任何包装器或技巧。APScheduler 会自动 await 它。
        job = self.scheduler.add_job(
            _send_custom_cron_email_task,
            'cron',
            id=job_id,
            name=name,
            kwargs=task_kwargs,
            replace_existing=True,
            # 直接将 cron 的各个部分作为关键字参数传递
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4]
        )
        logger.info(f"Successfully added/updated cron job: [ID: {job.id}, Name: {name}, Cron: '{cron_string}']")
        return job
            
    def start(self):
        """添加任务并启动调度器"""
        # ========================== START: 修改区域 (需求 ②) ==========================
        # DESIGNER'S NOTE:
        # 在服务启动时（这个方法被 FastAPI 的 startup 事件调用），
        # 我们安全地获取当前正在运行的 asyncio 事件循环，并将其存储在实例中。
        # 这是让后台线程能够与主线程通信的关键一步。
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            # 这是一个备用方案，以防在非asyncio上下文中意外启动此服务。
            logger.warning("No running event loop found. Creating a new one for the scheduler.")
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        # ========================== END: MODIFICATION (Async Job Execution Fix) ============================
        
        # 根据用户需求，注释掉在后端启动时自动添加的“每日总结”周期性任务。
        # 用户现在可以通过前端UI来添加所有周期性任务，这样更加灵活。
        # 如果未来需要恢复此功能，只需取消下面的注释即可。
        
        # self.scheduler.add_job(
        #     _send_recurring_emails_task,
        #     'cron',
        #     id="recurring_daily_summary",
        #     name="每日总结 (周期性)",
        #     year=settings.DAILY_SUMMARY_CRON.split(' ')[4],
        #     month=settings.DAILY_SUMMARY_CRON.split(' ')[3],
        #     day=settings.DAILY_SUMMARY_CRON.split(' ')[2],
        #     hour=settings.DAILY_SUMMARY_CRON.split(' ')[1],
        #     minute=settings.DAILY_SUMMARY_CRON.split(' ')[0],
        #     replace_existing=True
        # )
        # ========================== END: 修改区域 (需求 ②) ============================
        
        self.scheduler.start()
        # 更新日志消息以反映新的调度器类型
        logger.info(f"AsyncIO scheduler started successfully. Jobs are persisted to the database.")

    def shutdown(self):
        """安全关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("AsyncIO scheduler has been shut down.")

# 创建一个全局调度服务实例
scheduler_service = SchedulerService()