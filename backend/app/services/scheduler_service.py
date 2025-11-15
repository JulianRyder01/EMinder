# backend/app/services/scheduler_service.py (已修正序列化错误)
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from ..core.config import settings
from .email_service import email_service
from ..templates.email_templates import template_manager
from ..storage.sqlite_store import store

# --- 【核心修正点】 ---
# 将执行周期性任务的逻辑移到一个独立的、顶级的函数中。
# 这样做是为了解决 APScheduler 的序列化问题。当任务被持久化到数据库时，
# APScheduler 无法序列化一个包含调度器实例的对象 (self)。
# 将其作为普通函数，就不再有关联的 self 对象，问题迎刃而解。
def _send_recurring_emails_task():
    """扫描订阅者并发送相应模板的邮件。这是一个独立的函数，用于周期性任务。"""
    print(f"\n[{datetime.datetime.now()}] --- 开始执行定时邮件发送任务 ---")
    active_subscribers = store.get_active_subscribers()

    if not active_subscribers:
        print("没有活跃的订阅者，本次任务结束。")
        return

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
            email_content = template_func(mock_data)
            email_service.send_email(
                receiver_email=email,
                subject=email_content["subject"],
                html_content=email_content["html"]
            )
        else:
            print(f"警告：未找到名为 '{template_type}' 的邮件模板，无法为 {email} 发送。")
    
    print("--- 定时邮件发送任务执行完毕 ---\n")


class SchedulerService:
    """管理所有后台定时任务"""
    def __init__(self):
        jobstores = {
            'default': SQLAlchemyJobStore(url=settings.DATABASE_URL)
        }
        self.scheduler = BackgroundScheduler(jobstores=jobstores, timezone="Asia/Taipei")

    # 【修改点】原有的 _send_scheduled_emails 实例方法已被上面的顶级函数替代，故删除。

    @staticmethod
    def send_single_email_task(receiver_email: str, template_type: str, data: dict):
        """
        这是一个静态方法，专门被 APScheduler 调用来执行一次性任务。
        它不依赖 SchedulerService 实例的状态，因此可以被安全地序列化。
        """
        print(f"执行一次性任务：向 {receiver_email} 发送 '{template_type}' 模板邮件。")
        template_func = getattr(template_manager, template_type, None)
        if template_func:
            email_content = template_func(data)
            email_service.send_email(
                receiver_email,
                email_content["subject"],
                email_content["html"]
            )
        else:
            print(f"错误：在执行一次性任务时，未找到模板 '{template_type}'。")
            
    def start(self):
        """添加任务并启动调度器"""
        self.scheduler.add_job(
            # 【核心修正点】这里调用的目标是上面定义的顶级函数，而不是 self._send_scheduled_emails
            _send_recurring_emails_task,
            'cron',
            id="recurring_daily_summary",
            name="每日总结 (周期性)",
            year=settings.DAILY_SUMMARY_CRON.split(' ')[4],
            month=settings.DAILY_SUMMARY_CRON.split(' ')[3],
            day=settings.DAILY_SUMMARY_CRON.split(' ')[2],
            hour=settings.DAILY_SUMMARY_CRON.split(' ')[1],
            minute=settings.DAILY_SUMMARY_CRON.split(' ')[0],
            replace_existing=True
        )
        self.scheduler.start()
        print(f"后台调度器已启动。所有任务将持久化到数据库: {settings.DATABASE_URL}")
        print(f"每日邮件任务将按 CRON 表达式 '{settings.DAILY_SUMMARY_CRON}' 执行。")

    def shutdown(self):
        """安全关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("后台调度器已关闭。")

# 创建一个全局调度服务实例
scheduler_service = SchedulerService()