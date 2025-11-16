# backend/app/services/script_runner_service.py (新文件)
import asyncio
import datetime
import os
# ========================== START: MODIFICATION (Fix Encoding Issue) ==========================
# DESIGNER'S NOTE: 导入 locale 模块，用于安全地获取当前操作系统的默认编码。
import locale
# ========================== END: MODIFICATION (Fix Encoding Issue) ============================

class ScriptRunnerService:
    """
    一个用于在后台异步执行 shell 命令的服务。
    """
    
    # ========================== START: MODIFICATION (Fix Encoding Issue) ==========================
    # DESIGNER'S NOTE:
    # 新增一个私有辅助函数，专门用于健壮地解码子进程的输出。
    # 它会优先尝试使用 UTF-8 解码，如果失败（这通常发生在 Windows 系统输出中文时），
    # 它会自动回退到系统的首选编码（如 GBK），从而完美解决乱码问题。
    def _decode_subprocess_output(self, output_bytes: bytes) -> str:
        """
        健壮地解码子进程的字节流输出。
        """
        try:
            # 优先尝试通用且标准的 UTF-8
            return output_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # 如果 UTF-8 解码失败，则使用系统默认编码再次尝试
            try:
                # locale.getpreferredencoding(False) 在 Windows 上通常返回 'cp936' (GBK)
                system_encoding = locale.getpreferredencoding(False)
                print(f"UTF-8 decoding failed. Falling back to system encoding: {system_encoding}")
                return output_bytes.decode(system_encoding)
            except Exception:
                # 如果所有尝试都失败了，则使用 'replace' 策略强行解码，避免程序崩溃
                return output_bytes.decode('utf-8', errors='replace')
    # ========================== END: MODIFICATION (Fix Encoding Issue) ============================

    async def run_script(self, command: str, working_directory: str = None) -> dict:
        """
        异步执行一个脚本命令，并捕获其标准输出和标准错误。

        :param command: 要执行的完整 shell 命令 (例如 "python my_script.py --arg 1")。
        :param working_directory: 命令执行时的工作目录。
        :return: 一个包含执行结果的字典。
        """
        start_time = datetime.datetime.now()
        
        # ========================== START: MODIFICATION (Fix Dev Mode Issue) ==========================
        # DESIGNER'S NOTE:
        # 核心修正：无论传入的 working_directory 是相对路径还是绝对路径，
        # 我们都使用 os.path.abspath() 将其解析为绝对路径。
        # 这消除了对启动方式（dev模式 vs prod模式）的依赖，确保了路径的一致性和健壮性。
        
        # 如果提供了工作目录，则解析它；否则，默认为 None，让子进程继承父进程的目录。
        abs_working_dir = os.path.abspath(working_directory) if working_directory else None
        
        # 确保目录存在，如果不存在则提供明确的错误信息
        if abs_working_dir and not os.path.isdir(abs_working_dir):
            error_msg = f"错误：指定的工作目录不存在: '{abs_working_dir}'"
            print(error_msg)
            return {"success": False, "stderr": error_msg, "return_code": -1, "stdout": ""}
            
        log_friendly_dir = f"于目录 '{abs_working_dir}'" if abs_working_dir else ""
        print(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行命令: '{command}' {log_friendly_dir}")
        # ========================== END: MODIFICATION (Fix Dev Mode Issue) ============================

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # 使用解析后的绝对路径
                cwd=abs_working_dir 
            )

            # 等待命令执行完成并异步读取输出
            stdout, stderr = await process.communicate()

            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()

            result = {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                # ========================== START: MODIFICATION (Fix Encoding Issue) ==========================
                # 使用新的健壮解码函数来处理 stdout 和 stderr
                "stdout": self._decode_subprocess_output(stdout),
                "stderr": self._decode_subprocess_output(stderr),
                # ========================== END: MODIFICATION (Fix Encoding Issue) ============================
                "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                "end_time": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                "duration_seconds": round(duration, 2)
            }
            print(f"命令执行完毕。耗时: {result['duration_seconds']}s, 返回码: {result['return_code']}")
            return result

        except FileNotFoundError:
            error_msg = f"错误：命令 '{command.split()[0]}' 未找到。请确保它在系统的 PATH 中，或者提供了正确的路径。"
            print(error_msg)
            return {"success": False, "stderr": error_msg, "return_code": -1, "stdout": ""}
        except Exception as e:
            # 捕获其他所有可能的异常，并将其内容记录下来，而不是返回空
            error_msg = f"执行命令时发生未知错误: {str(e)}"
            print(error_msg)
            return {"success": False, "stderr": error_msg, "return_code": -1, "stdout": ""}

# 创建一个全局的脚本运行服务实例，供其他模块调用
script_runner_service = ScriptRunnerService()