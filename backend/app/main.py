# backend/app/main.py (已修改)

from fastapi import FastAPI
from .api import subscribers, templates, jobs  # 导入新的 templates 模块

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
    """应用启动时，启动后台调度器"""
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