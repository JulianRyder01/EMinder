# backend/app/api/llm.py

from fastapi import APIRouter, HTTPException, Body, Path
from typing import Dict, Any, List
import logging
from ..storage.sqlite_store import store

# ========================== START: MODIFICATION ==========================
# DESIGNER'S NOTE:
# 这是一个全新的API模块，专门用于管理大模型（LLM）的配置。
# 它提供了完整的CRUD（创建、读取、更新、删除）以及激活配置的功能。

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/configs", response_model=List[Dict[str, Any]])
def get_llm_configurations():
    """获取所有已保存的LLM服务配置。"""
    try:
        configs = store.get_all_llm_configs()
        return configs
    except Exception as e:
        logger.error(f"获取LLM配置列表时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取LLM配置列表时发生内部错误。")

@router.post("/configs")
def add_llm_configuration(payload: Dict[str, Any] = Body(...)):
    """添加一个新的LLM服务配置。"""
    try:
        provider_name = payload.get("provider_name")
        api_url = payload.get("api_url")
        api_key = payload.get("api_key")
        model_name = payload.get("model_name")
        
        if not all([provider_name, api_url, api_key, model_name]):
            raise HTTPException(status_code=422, detail="缺少必要字段：provider_name, api_url, api_key, model_name。")
        
        success = store.add_llm_config(provider_name, api_url, api_key, model_name)
        if success:
            return {"status": "success", "message": f"已成功添加配置: {provider_name}"}
        else:
            raise HTTPException(status_code=500, detail="添加LLM配置时发生数据库错误。")
    except Exception as e:
        logger.error(f"添加LLM配置时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"添加LLM配置时发生错误: {str(e)}")


@router.put("/configs/{config_id}")
def update_llm_configuration(config_id: int = Path(...), payload: Dict[str, Any] = Body(...)):
    """更新一个已存在的LLM配置。"""
    try:
        provider_name = payload.get("provider_name")
        api_url = payload.get("api_url")
        api_key = payload.get("api_key")  # 可以为空或None，表示不更新密钥
        model_name = payload.get("model_name")

        if not all([provider_name, api_url, model_name]):
            raise HTTPException(status_code=422, detail="缺少必要字段：provider_name, api_url, model_name。")

        success = store.update_llm_config(config_id, provider_name, api_url, api_key, model_name)
        if success:
            return {"status": "success", "message": f"已成功更新配置ID: {config_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {config_id} 的LLM配置。")
    except Exception as e:
        logger.error(f"更新LLM配置 (ID: {config_id}) 时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新LLM配置时发生错误: {str(e)}")


@router.delete("/configs/{config_id}")
def delete_llm_configuration(config_id: int = Path(...)):
    """删除一个LLM配置。"""
    try:
        success = store.delete_llm_config(config_id)
        if success:
            return {"status": "success", "message": f"已成功删除配置ID: {config_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {config_id} 的LLM配置。")
    except Exception as e:
        logger.error(f"删除LLM配置 (ID: {config_id}) 时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除LLM配置时发生错误: {str(e)}")

@router.post("/configs/active/{config_id}")
def set_active_llm_configuration(config_id: int = Path(...)):
    """将一个LLM配置设置为当前激活的服务。"""
    try:
        success = store.set_active_llm_config(config_id)
        if success:
            return {"status": "success", "message": f"已成功将配置ID: {config_id} 设为当前服务。"}
        else:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {config_id} 的LLM配置以设为激活。")
    except Exception as e:
        logger.error(f"设置激活LLM配置 (ID: {config_id}) 时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"设置激活LLM配置时发生错误: {str(e)}")

# ========================== END: MODIFICATION ============================