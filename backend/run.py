import uvicorn
import os
import sys
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EMinder Backend Launcher")
    parser.add_argument("--port",type=int,default=8421,help="Port to run the backend server on (default: 8421)")
    args = parser.parse_args()

    # 获取当前文件所在目录的父目录，即 backend/
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    # 将 app 所在的目录添加到 sys.path

    sys.path.insert(0, backend_dir)

    # 这样就可以正确地从 app 模块导入
    from app.main import app
    port = getattr(args,'port')
    print(f"EMinder 后端服务即将启动于端口 {port} ...")
    print(f"若在本机运行，可访问 http://127.0.0.1:{port}/docs 查看 API 文档")
    
    # 在生产环境中，推荐使用 Gunicorn 作为进程管理器
    # 例如: gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 run:app
    uvicorn.run(app, host="0.0.0.0", port=port)