# backend/app/services/script_runner_service.py (新文件)
import asyncio
import datetime
import os

class ScriptRunnerService:
    """
    一个用于在后台异步执行 shell 命令的服务。
    """
    async def run_script(self, command: str, working_directory: str = None) -> dict:
        """
        异步执行一个脚本命令，并捕获其标准输出和标准错误。

        :param command: 要执行的完整 shell 命令 (例如 "python my_script.py --arg 1")。
        :param working_directory: 命令执行时的工作目录。
        :return: 一个包含执行结果的字典。
        """
        start_time = datetime.datetime.now()
        print(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行命令: '{command}' 于目录 '{working_directory}'")

        try:
            # 使用 asyncio.create_subprocess_shell 来执行完整的命令字符串
            # 这比 threading + Popen 更适合在 asyncio 环境下进行非阻塞I/O
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_directory
            )

            # 等待命令执行完成并异步读取输出
            stdout, stderr = await process.communicate()

            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()

            result = {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='ignore'),
                "stderr": stderr.decode('utf-8', errors='ignore'),
                "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                "end_time": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                "duration_seconds": round(duration, 2)
            }
            print(f"命令执行完毕。耗时: {result['duration_seconds']}s, 返回码: {result['return_code']}")
            return result

        except FileNotFoundError:
            # 如果命令中的可执行文件不存在
            error_msg = f"错误：命令 '{command.split()[0]}' 未找到。请确保它在系统的 PATH 中，或者提供了正确的路径。"
            print(error_msg)
            return {"success": False, "stderr": error_msg, "return_code": -1, "stdout": ""}
        except Exception as e:
            # 捕获其他所有可能的异常
            error_msg = f"执行命令时发生未知错误: {e}"
            print(error_msg)
            return {"success": False, "stderr": error_msg, "return_code": -1, "stdout": ""}

# 创建一个全局的脚本运行服务实例，供其他模块调用
script_runner_service = ScriptRunnerService()