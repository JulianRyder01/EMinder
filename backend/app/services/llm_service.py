# backend/app/services/llm_service.py (重构后)
import httpx
import logging
from ..storage.sqlite_store import store # 导入 store 实例

# ========================== START: MODIFICATION ==========================
# DESIGNER'S NOTE:
# 整个 LLMService 被重构，使其成为一个动态的、数据驱动的服务。
# 它不再从环境变量读取配置，而是从数据库中查询当前被标记为 "active" 的配置来执行 API 调用。

class LLMService:
    """
    处理与大语言模型 (LLM) API 交互的业务逻辑。
    这是一个动态服务，它会使用数据库中标记为“激活”的配置。
    """

    def __init__(self):
        self.request_timeout = 60  # 设置 API 请求超时时间为60秒
        self.logger = logging.getLogger(__name__)

    async def generate_text(self, prompt: str) -> dict:
        """
        使用当前激活的 LLM 配置处理输入文本。

        :param prompt: 发送给大模型的提示词。
        :return: 一个包含处理结果或错误信息的字典。
                 成功: {"success": True, "content": "处理后的文本"}
                 失败: {"success": False, "content": "错误信息详情"}
        """
        # 1. 从数据库获取当前激活的配置
        active_config = store.get_active_llm_config()

        if not active_config:
            self.logger.warning("LLM调用失败：数据库中没有设置任何激活的大模型服务。")
            return {
                "success": False,
                "content": "无法连接到大模型服务：管理员尚未在设置页面中指定一个当前服务。"
            }

        api_url = active_config.get("api_url")
        api_key = active_config.get("api_key")
        model_name = active_config.get("model_name")
        provider_name = active_config.get("provider_name")

        if not all([api_url, api_key, model_name]):
            self.logger.error(f"LLM配置不完整 (ID: {active_config.get('id')})。缺少 URL、Key 或模型名称。")
            return {
                "success": False,
                "content": f"配置错误：名为 '{provider_name}' 的服务配置不完整。"
            }

        # 2. 准备请求（兼容OpenAI的格式）
        #    适用于 DeepSeek, SiliconFlow 等绝大多数厂商
        full_endpoint = f"{api_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }

        self.logger.info(f"正在通过 '{provider_name}' (模型: {model_name}) 发送请求至 '{full_endpoint}'...")

        # 3. 发送异步HTTP请求
        try:
            # 使用 httpx.AsyncClient 发送异步 POST 请求
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    full_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.request_timeout
                )
            
            # 检查 HTTP 响应状态码，如果不是 2xx 则抛出异常
            response.raise_for_status()

            response_data = response.json()
            
            # 健壮地解析响应内容
            if "choices" in response_data and response_data["choices"]:
                first_choice = response_data["choices"][0]
                if "message" in first_choice and "content" in first_choice["message"]:
                    processed_content = first_choice["message"]["content"]
                    self.logger.info("成功从LLM服务获取到响应。")
                    return {"success": True, "content": processed_content}

            error_message = f"API 响应格式不正确，缺少有效内容。服务商: {provider_name}, 响应: {response_data}"
            self.logger.error(error_message)
            return {"success": False, "content": error_message}

        except httpx.HTTPStatusError as http_err:
            # 处理 HTTP 错误，例如 401, 429, 500
            error_details = f"HTTP 错误: {http_err.response.status_code} {http_err.response.reason_phrase}"
            try:
                # 尝试解析API返回的具体错误信息
                api_error_body = http_err.response.json()
                api_error = api_error_body.get("error", {}).get("message", str(api_error_body))
                error_details += f"\nAPI 错误信息: {api_error}"
            except Exception:
                error_details += f"\n原始响应: {http_err.response.text}"
            self.logger.error(f"调用 '{provider_name}' 时发生HTTP错误: {error_details}")
            return {"success": False, "content": error_details}

        except httpx.RequestError as req_err:
            error_message = f"网络请求失败: 无法连接到 '{provider_name}' 的API地址 ({api_url})。请检查网络或配置。错误详情: {req_err}"
            self.logger.error(error_message)
            return {"success": False, "content": error_message}
            
        except Exception as e:
            error_message = f"处理文本时发生未知错误: {e}"
            self.logger.error(error_message, exc_info=True)
            return {"success": False, "content": error_message}


# 创建一个全局的大模型服务实例，供其他模块调用
llm_service = LLMService()