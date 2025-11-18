# frontend/app/config.py
# ========================== START: MODIFICATION (Code Addition) ==========================
# DESIGNER'S NOTE:
# This new file centralizes all configuration, making it easier to manage backend API endpoints.
# It removes hardcoded URLs from the application logic by parsing command-line arguments,
# which is a best practice for creating flexible and configurable applications.

import argparse

class AppConfig:
    """
    Parses command-line arguments and constructs all necessary API endpoint URLs.
    """
    def __init__(self):
        parser = argparse.ArgumentParser(description="EMinder Frontend Launcher")
        parser.add_argument(
            "--port", 
            type=int, 
            default=10101, 
            help="Port to run the frontend server on (default: 10101)"
        )
        parser.add_argument(
            "--bnport", 
            type=int, 
            default=8421, 
            help="Port of the backend server (default: 8421)"
        )
        parser.add_argument(
            "--bnserver", 
            type=str, 
            default="http://127.0.0.1", 
            help="Backend server address (default: http://127.0.0.1)"
        )
        
        # 使用 parse_known_args 避免 Gradio 在 reload 模式下传入额外参数导致出错
        args, _ = parser.parse_known_args()

        self.run_port = args.port
        backend_base_url = f"{args.bnserver}:{args.bnport}"
        
        # --- API Endpoints ---
        self.API_BASE_URL = f"{backend_base_url}/api"
        self.ROOT_URL = backend_base_url
        
        self.TEMPLATES_INFO_URL = f"{self.API_BASE_URL}/templates/info"
        self.SUBSCRIBERS_URL = f"{self.API_BASE_URL}/subscribers"
        self.SEND_NOW_URL = f"{self.API_BASE_URL}/send-now"
        self.SCHEDULE_ONCE_URL = f"{self.API_BASE_URL}/schedule-once"
        self.SCHEDULE_CRON_URL = f"{self.API_BASE_URL}/schedule-cron"
        self.JOBS_URL = f"{self.API_BASE_URL}/jobs"
        # ========================== START: MODIFICATION ==========================
        # DESIGNER'S NOTE: 新增LLM配置管理的API端点
        self.LLM_CONFIGS_URL = f"{self.API_BASE_URL}/llm/configs"
        # ========================== END: MODIFICATION ============================

# Create a single, globally accessible configuration instance.
config = AppConfig()

# ========================== END: MODIFICATION (Code Addition) ============================