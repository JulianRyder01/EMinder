import uvicorn
import os

if __name__ == "__main__":
    # 获取当前文件所在目录的父目录，即 backend/
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    # 将 app 所在的目录添加到 sys.path
    import sys
    sys.path.insert(0, backend_dir)

    # 这样就可以正确地从 app 模块导入
    from app.main import app
    
    print("EMinder 后端服务即将启动...")
    print(f"访问 http://127.0.0.1:8000/docs 查看 API 文档")
    
    # 在生产环境中，推荐使用 Gunicorn 作为进程管理器
    # 例如: gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 run:app
    uvicorn.run(app, host="0.0.0.0", port=8000)