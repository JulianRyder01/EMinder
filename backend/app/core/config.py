# backend/app/core/config.py (已修正)
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
# 该路径是相对于 run.py 文件的位置，所以它会加载 backend/.env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', '.env')
load_dotenv(dotenv_path=env_path)

class Settings:
    """
    应用配置类，从环境变量中读取配置。
    不使用 Pydantic，手动进行类型转换和默认值设置。
    """
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
    
    # --- 【修正点】 ---
    # 新增对 DATABASE_URL 的读取，并提供一个安全的默认值
    # 这将确保程序即使在 .env 文件中未配置此项时也能正常启动
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./eminder.db")
    
    # SMTP 配置
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.qq.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 465))
    
    # 发件人账户解析
    _sender_accounts_str = os.getenv("SENDER_ACCOUNTS")
    if not _sender_accounts_str:
        raise ValueError("环境变量 SENDER_ACCOUNTS 未设置，请在 .env 文件中配置发信源！")
    
    SENDER_ACCOUNTS: list[dict] = [
        {"email": acc.split('|')[0], "password": acc.split('|')[1]}
        for acc in _sender_accounts_str.split(',')
    ]

    # 定时任务配置
    DAILY_SUMMARY_CRON: str = os.getenv("DAILY_SUMMARY_CRON", "0 8 * * *")

    # --- 【新增】大模型工作流配置 ---
    # 从环境变量中读取 DeepSeek API 的 Key 和 Endpoint
    # 如果 API Key 未设置，其值为 None
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_ENDPOINT: str = os.getenv("DEEPSEEK_API_ENDPOINT", "https://api.deepseek.com")

    # ========================== START: MODIFICATION (需求 ①) ==========================
    # DESIGNER'S NOTE:
    # 新增对每日总结文件夹路径的读取。
    # 如果用户没有在 .env 文件中配置此项，其值将为 None。
    # 相关的模板函数会处理此情况，并返回友好的错误提示。
    DAILY_SUMMARY_PATH: str = os.getenv("DAILY_SUMMARY_PATH")
    # ========================== END: MODIFICATION (需求 ①) ============================


# 创建一个全局配置实例
settings = Settings()