# backend/app/storage/sqlite_store.py (由 memory_store.py 修改并重命名)
import sqlite3
import os
import threading
from ..core.config import settings

# --- 数据库文件路径处理 ---
# 从 ".env" 文件中的 "sqlite:///./backend/eminder.db" 提取相对路径
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///"):
    # 去掉 "sqlite:///" 前缀
    relative_path = db_url[len("sqlite///"):]
    # 构建一个基于此文件位置的绝对路径，确保路径的准确性
    # __file__ -> .../backend/app/storage/memory_store.py
    # 我们需要回到 backend 目录来创建 eminder.db
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    DB_FILE = os.path.join(base_dir, os.path.basename(relative_path)) # 使用 eminder.db 作为文件名
    
    # 确保数据库文件所在的目录存在
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
else:
    raise ValueError("DATABASE_URL in .env 必须是 'sqlite:///./path/to/your.db' 格式")

print(f"数据持久化已启用，数据库文件位于: {DB_FILE}")

# 使用线程锁来确保在多线程环境下的数据安全
lock = threading.Lock()

class SQLiteStore:
    """
    一个基于 SQLite 的、线程安全的持久化数据存储。
    表结构 (subscribers):
    {
        "email": TEXT (PRIMARY KEY),
        "remark_name": TEXT,
        "subscribed": BOOLEAN, (始终为 True)
        "template_type": TEXT,
        "data_source": TEXT
    }
    """
    def __init__(self, db_path=DB_FILE):
        self._db_path = db_path
        self._init_db()

    def _get_connection(self):
        """获取数据库连接, 并允许多线程访问"""
        return sqlite3.connect(self._db_path, check_same_thread=False)

    def _init_db(self):
        """初始化数据库，如果 subscribers 表不存在则创建它"""
        with lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS subscribers (
                        email TEXT PRIMARY KEY,
                        remark_name TEXT,
                        subscribed BOOLEAN NOT NULL DEFAULT 1,
                        template_type TEXT,
                        data_source TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # 【修改点】检查并添加 remark_name 列，以兼容旧数据库
                cursor.execute("PRAGMA table_info(subscribers)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'remark_name' not in columns:
                    cursor.execute("ALTER TABLE subscribers ADD COLUMN remark_name TEXT")
                    print("数据库表 'subscribers' 已成功添加 'remark_name' 字段。")
                

                conn.commit()
                print("数据库表 'subscribers' 初始化或验证成功。")
            finally:
                conn.close()

    def add_subscriber(self, email: str, remark_name: str, template_type: str = "daily_summary") -> bool:
        """【修改】直接添加一个活跃的订阅者，无需确认"""
        with lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                # 使用 INSERT OR REPLACE (UPSERT) 插入或更新记录
                cursor.execute("""
                    INSERT OR REPLACE INTO subscribers (email, remark_name, subscribed, template_type, data_source)
                    VALUES (?, ?, 1, ?, ?)
                """, (email, remark_name, template_type, email))
                conn.commit()
                print(f"持久化存储区：已添加或更新订阅者 {email} (备注: {remark_name})")
                return True
            except sqlite3.IntegrityError:
                # 理论上 INSERT OR REPLACE 不会触发此错误，但作为保险
                return False
            finally:
                conn.close()

    def update_subscriber(self, email: str, new_remark_name: str) -> bool:
        """【新增】更新指定邮箱的备注名"""
        with lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE subscribers SET remark_name = ? WHERE email = ?", (new_remark_name, email))
                conn.commit()
                # rowcount 会返回受影响的行数，如果大于0则说明更新成功
                if cursor.rowcount > 0:
                    print(f"持久化存储区：已更新 {email} 的备注为 {new_remark_name}")
                    return True
                return False # 没有找到对应的 email
            finally:
                conn.close()

    def delete_subscriber(self, email: str) -> bool:
        """【新增】根据邮箱删除一个订阅者"""
        with lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM subscribers WHERE email = ?", (email,))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"持久化存储区：已删除订阅者 {email}")
                    return True
                return False # 没有找到要删除的 email
            finally:
                conn.close()

    def get_active_subscribers(self) -> list[dict]:
        """【修改】获取所有已激活的订阅者信息，包含备注名"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row # 让查询结果以字典形式返回
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT email, remark_name, template_type, data_source FROM subscribers WHERE subscribed = 1 ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def email_exists(self, email: str) -> bool:
        """检查邮箱是否已存在（无论是否已确认）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM subscribers WHERE email = ?", (email,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

# 创建一个全局存储实例
# 虽然文件名仍为 memory_store.py，但其内部实现已是 SQLiteStore
store = SQLiteStore()