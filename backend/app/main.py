# backend/app/main.py (已修改)

from fastapi import FastAPI
from .api import subscribers, templates, jobs  # 导入新的 templates 模块
# ========================== START: 修改区域 (需求 ①) ==========================
import os
# ========================== END: 修改区域 (需求 ①) ============================

app = FastAPI(
    title="EMinder Service",
    description="一款定时向指定邮箱发送指定消息的软件后端服务。",
    version="1.0.0"
)

# 挂载 API 路由
app.include_router(subscribers.router, prefix="/api", tags=["Subscribers"])
app.include_router(templates.router, prefix="/api", tags=["Templates"]) # 挂载新的模板路由
app.include_router(jobs.router, prefix="/api", tags=["Scheduled Jobs"]) 

@app.on_event("startup")
def startup_event():
    """应用启动时，启动后台调度器并创建临时目录"""
    # ========================== START: 修改区域 (需求 ①) ==========================
    # DESIGNER'S NOTE:
    # 在应用启动时，检查并创建用于存放临时上传文件的目录。
    # 这是一个良好的实践，可以避免在运行时因目录不存在而引发错误。
    temp_upload_dir = os.path.join(os.path.dirname(__file__), '..', 'temp_uploads')
    os.makedirs(temp_upload_dir, exist_ok=True)
    print(f"临时文件上传目录已准备就绪: {temp_upload_dir}")
    # ========================== END: 修改区域 (需求 ①) ============================
    
    from .services.scheduler_service import scheduler_service
    scheduler_service.start()

@app.on_event("shutdown")
def shutdown_event():
    """应用关闭时，关闭后台调度器"""
    from .services.scheduler_service import scheduler_service
    scheduler_service.shutdown()

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to EMinder Backend API. Visit /docs for API documentation."}