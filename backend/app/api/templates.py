# backend/app/api/templates.py (新文件)

from fastapi import APIRouter
from ..templates.email_templates import template_manager

router = APIRouter()

@router.get("/templates/info")
def get_templates_info():
    """
    提供所有可用邮件模板的元数据。
    前端将调用此接口来动态构建UI界面。
    """
    return template_manager.get_all_templates_metadata()