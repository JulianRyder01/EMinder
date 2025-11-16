# backend/app/services/scheduler_service.py (已修正序列化错误)
import datetime
import asyncio
import os # <-- 新增导入
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from croniter import croniter
from ..core.config import settings
from .email_service import email_service
from ..templates.email_templates import template_manager
from ..storage.sqlite_store import store

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

async def _send_custom_cron_email_task(receiver_emails: list[str], template_type: str, data: dict, custom_subject: str = None):
    """
    【异步改造 & 功能增强】根据指定的参数，向一个邮件列表发送模板邮件。
    这是一个独立的函数，用于用户自定义的周期性任务。
    增加了 custom_subject 参数和附件处理能力。
    """
    print(f"\n[{datetime.datetime.now()}] --- 开始执行自定义周期任务: 发送 '{template_type}' ---")
    
    if not receiver_emails:
        print("邮件接收者列表为空，本次任务结束。")
        return
        
    template_func = getattr(template_manager, template_type, None)
    if not template_func:
        print(f"警告：在执行自定义周期任务时，未找到模板 '{template_type}'。")
        return

    # 检查模板函数是否为异步
    if asyncio.iscoroutinefunction(template_func):
        email_content = await template_func(data)
    else:
        email_content = template_func(data)
    
    # 【修改】如果提供了自定义标题，则使用它；否则，使用模板的默认标题。
    final_subject = custom_subject if custom_subject else email_content["subject"]
    
    # 从模板函数的返回结果中提取附件路径列表 (新)
    attachments_to_send = email_content.get("attachments", [])
    
    print(f"准备向 {len(receiver_emails)} 位接收者发送邮件 (标题: '{final_subject}'): {', '.join(receiver_emails)}")
    
    tasks = []
    for email in receiver_emails:
        task = email_service.send_email(
            receiver_email=email,
            subject=final_subject,
            html_content=email_content["html"],
            attachments=attachments_to_send
        )
        tasks.append(task)
        
    # 并发执行所有邮件发送任务
    if tasks:
        await asyncio.gather(*tasks)
    
    print("--- 自定义周期任务执行完毕 ---\n")


class SchedulerService:
    """管理所有后台定时任务"""
    def __init__(self):
        jobstores = {
            'default': SQLAlchemyJobStore(url=settings.DATABASE_URL)
        }
        # BackgroundScheduler 同样支持调度异步任务
        self.scheduler = BackgroundScheduler(jobstores=jobstores, timezone="Asia/Taipei")

    # 【修改点】原有的 _send_scheduled_emails 实例方法已被上面的顶级函数替代，故删除。

    @staticmethod
    # ========================== START: MODIFICATION (Multi-Attachment Support) ==========================
    # DESIGNER'S NOTE:
    # 修改了此任务函数的签名，将 `temp_file_path: str` 改为 `temp_file_paths: list`。
    # 内部逻辑也相应地修改为遍历这个列表来处理和清理所有临时文件。
    async def send_single_email_task(
        receiver_email: str, 
        template_type: str, 
        data: dict, 
        custom_subject: str = None, 
        temp_file_paths: list = None
    ):
    # ========================== END: MODIFICATION (Multi-Attachment Support) ============================
        """
        【功能增强】这是一个静态方法，专门被 APScheduler 调用来执行一次性任务。
        它现在能处理多个临时上传的附件。
        """
        try:
            print(f"执行一次性任务：向 {receiver_email} 发送 '{template_type}' 模板邮件。")
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
                
                await email_service.send_email(
                    receiver_email,
                    final_subject,
                    email_content["html"],
                    attachments=final_attachments,
                    embedded_images=email_content.get("embedded_images", [])
                )
            else:
                print(f"错误：在执行一次性任务时，未找到模板 '{template_type}'。")
        finally:
            # 关键：确保任务执行完毕后，删除所有临时上传的文件
            if temp_file_paths:
                for temp_path in temp_file_paths:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                            print(f"成功清理临时文件: {temp_path}")
                        except Exception as e:
                            print(f"警告：清理临时文件 {temp_path} 失败: {e}")
    # ========================== END: 修改区域 (需求 ①) ============================
    
    def add_cron_job(self, job_id: str, name: str, cron_string: str, args: list):
        """
        【新增】添加一个由 Cron 表达式定义的周期性任务。
        """
        if not croniter.is_valid(cron_string):
            raise ValueError(f"无效的 Cron 表达式: '{cron_string}'")

        parts = cron_string.split()
        if len(parts) != 5:
            raise ValueError("Cron 表达式必须包含5个部分 (分 时 日 月 周)。")
        
        cron_kwargs = {
            'minute': parts[0],
            'hour': parts[1],
            'day': parts[2],
            'month': parts[3],
            'day_of_week': parts[4]
        }
        
        # add_job 会自动检测到 _send_custom_cron_email_task 是协程并正确地执行它
        job = self.scheduler.add_job(
            _send_custom_cron_email_task,
            'cron',
            id=job_id,
            name=name,
            args=args,
            replace_existing=True,
            **cron_kwargs
        )
        print(f"已成功添加新的周期任务: [ID: {job.id}, Name: {name}, Cron: '{cron_string}']")
        return job
            
    def start(self):
        """添加任务并启动调度器"""
        # ========================== START: 修改区域 (需求 ②) ==========================
        # DESIGNER'S NOTE:
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
        print(f"后台调度器已启动。所有任务将持久化到数据库: {settings.DATABASE_URL}")
        
        # 由于默认任务已移除，此打印信息也不再需要
        # print(f"每日邮件任务将按 CRON 表达式 '{settings.DAILY_SUMMARY_CRON}' 执行。")

    def shutdown(self):
        """安全关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("后台调度器已关闭。")

# 创建一个全局调度服务实例
scheduler_service = SchedulerService()