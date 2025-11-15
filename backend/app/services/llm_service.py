# backend/app/services/llm_service.py (新文件)

import httpx # 导入异步 HTTP 客户端库
from ..core.config import settings

class LLMService:
    """
    处理与大语言模型 (LLM) API 交互的业务逻辑。
    """

    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.api_endpoint = settings.DEEPSEEK_API_ENDPOINT
        self.model_name = "deepseek-chat"
        self.request_timeout = 60  # 设置 API 请求超时时间为60秒

        if not self.api_key:
            # 仅在服务初始化时打印警告，而不是中止整个应用
            print("警告: DEEPSEEK_API_KEY 未在 .env 文件中配置。大模型相关功能将不可用。")

    async def process_text_with_deepseek(self, text_ori: str) -> dict:
        """
        【异步改造】使用 DeepSeek API 处理输入文本。
        使用 httpx 实现非阻塞的 API 请求。

        :param text_ori: 原始输入文本。
        :return: 一个包含处理结果或错误信息的字典。
                 成功: {"success": True, "content": "处理后的文本"}
                 失败: {"success": False, "content": "错误信息详情"}
        """
        # 如果没有配置API Key，直接返回错误信息
        if not self.api_key:
            return {
                "success": False,
                "content": "无法连接到大模型服务：管理员尚未配置 API Key。"
            }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": text_ori}
            ],
            "stream": False
        }

        try:
            # 使用 httpx.AsyncClient 发送异步 POST 请求
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_endpoint}/chat/completions",
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
                    return {"success": True, "content": processed_content}

            # 如果响应结构不符合预期，返回错误
            error_message = f"API 响应格式不正确，缺少有效内容。响应详情: {response_data}"
            print(error_message)
            return {"success": False, "content": error_message}

        except httpx.HTTPStatusError as http_err:
            # 处理 HTTP 错误，例如 401, 429, 500
            error_details = f"HTTP 错误: {http_err.response.status_code} {http_err.response.reason_phrase}"
            try:
                api_error = http_err.response.json().get("error", {}).get("message", "无详细信息")
                error_details += f"\nAPI 错误信息: {api_error}"
            except Exception:
                pass
            print(error_details)
            return {"success": False, "content": error_details}

        except httpx.RequestError as req_err:
            # 处理网络相关的错误，例如连接超时、DNS错误
            error_message = f"网络请求失败: 无法连接到 DeepSeek API。请检查网络连接或 API 端点配置。错误详情: {req_err}"
            print(error_message)
            return {"success": False, "content": error_message}
            
        except Exception as e:
            # 捕获其他所有未知异常
            error_message = f"处理文本时发生未知错误: {e}"
            print(error_message)
            return {"success": False, "content": error_message}


# 创建一个全局的大模型服务实例，供其他模块调用
llm_service = LLMService()