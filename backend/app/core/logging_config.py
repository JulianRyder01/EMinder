# backend/app/core/logging_config.py (新文件)

import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    配置应用程序的日志记录系统。
    DESIGNER'S NOTE:
    这是一个集中的日志配置函数，旨在提供标准化、生产就绪的日志记录。
    - 日志将被发送到两个地方：控制台（便于开发调试）和文件（便于生产环境问题追溯）。
    - 使用 RotatingFileHandler 来自动管理日志文件大小，防止其无限增长。
    - 确保日志目录存在，避免因目录不存在而导致的启动错误。
    """
    # 确定日志文件的存放目录 (backend/logs/)
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, 'eminder_backend.log')

    # 定义日志配置字典
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': 'INFO',
                'stream': 'ext://sys.stdout',  # 默认输出到标准输出
            },
            'rotating_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'default',
                'level': 'INFO',
                'filename': log_file_path,
                'maxBytes': 1024 * 1024 * 5,  # 5 MB
                'backupCount': 5,
                'encoding': 'utf-8',
            },
        },
        'loggers': {
            '': {  # Root logger
                'handlers': ['console', 'rotating_file'],
                'level': 'INFO',
            },
            'uvicorn.error': {
                'handlers': ['console', 'rotating_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'uvicorn.access': {
                'handlers': ['console', 'rotating_file'],
                'level': 'WARNING', # 减少访问日志的噪音
                'propagate': False,
            },
        }
    }

    logging.config.dictConfig(LOGGING_CONFIG)
    # 获取根 logger 并记录一条初始化信息
    root_logger = logging.getLogger()
    root_logger.info("Logging system initialized successfully.")
    root_logger.info(f"Log files will be saved to: {log_file_path}")