# backend/app/storage/sqlite_store.py (由 memory_store.py 修改并重命名)
import sqlite3
import os
import threading
import logging # 新增日志
from ..core.config import settings

# --- 数据库文件路径处理 ---
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///"):
    relative_path = db_url[len("sqlite///"):]
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    DB_FILE = os.path.join(base_dir, os.path.basename(relative_path))
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
else:
    raise ValueError("DATABASE_URL in .env 必须是 'sqlite:///./path/to/your.db' 格式")

logger = logging.getLogger(__name__)
logger.info(f"数据持久化已启用，数据库文件位于: {DB_FILE}")

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
                    logger.info("数据库表 'subscribers' 已成功添加 'remark_name' 字段。")
                
                # ========================== START: MODIFICATION ==========================
                # DESIGNER'S NOTE:
                # 新增 LLM 配置表的初始化逻辑。
                # 包含 ID、服务商名、API URL、API Key、模型名 和 是否激活的标志。
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS llm_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider_name TEXT NOT NULL,
                        api_url TEXT NOT NULL,
                        api_key TEXT NOT NULL,
                        model_name TEXT NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("数据库表 'llm_configs' 初始化或验证成功。")

                conn.commit()
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
                logger.info(f"持久化存储区：已添加或更新订阅者 {email} (备注: {remark_name})")
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
                    logger.info(f"持久化存储区：已更新 {email} 的备注为 {new_remark_name}")
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
                    logger.info(f"持久化存储区：已删除订阅者 {email}")
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
            
    # ========================== START: MODIFICATION ==========================
    # DESIGNER'S NOTE:
    # 以下是为 LLM 配置管理新增的一整套数据库操作方法。
    
    def get_all_llm_configs(self) -> list[dict]:
        """获取所有已保存的LLM配置。"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, provider_name, api_url, api_key, model_name, is_active FROM llm_configs ORDER BY created_at DESC")
            rows = cursor.fetchall()
            # 为了安全，不在返回给API的列表中包含完整的API Key
            configs = []
            for row in rows:
                config = dict(row)
                config['api_key'] = f"***{config['api_key'][-4:]}" if config['api_key'] and len(config['api_key']) > 4 else "***"
                configs.append(config)
            return configs
        finally:
            conn.close()

    def add_llm_config(self, provider_name: str, api_url: str, api_key: str, model_name: str) -> bool:
        """添加一个新的LLM配置。"""
        with lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO llm_configs (provider_name, api_url, api_key, model_name)
                    VALUES (?, ?, ?, ?)
                """, (provider_name, api_url, api_key, model_name))
                conn.commit()
                return True
            finally:
                conn.close()

    def update_llm_config(self, config_id: int, provider_name: str, api_url: str, api_key: str, model_name: str) -> bool:
        """更新一个已存在的LLM配置。如果api_key为空字符串或None，则不更新它。"""
        with lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                if api_key: # 只有在提供了新的key时才更新
                    cursor.execute("""
                        UPDATE llm_configs SET provider_name=?, api_url=?, api_key=?, model_name=?
                        WHERE id=?
                    """, (provider_name, api_url, api_key, model_name, config_id))
                else: # 不更新key
                     cursor.execute("""
                        UPDATE llm_configs SET provider_name=?, api_url=?, model_name=?
                        WHERE id=?
                    """, (provider_name, api_url, model_name, config_id))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def delete_llm_config(self, config_id: int) -> bool:
        """删除一个LLM配置。"""
        with lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM llm_configs WHERE id=?", (config_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def set_active_llm_config(self, config_id: int) -> bool:
        """设置一个LLM配置为激活状态，并取消其他所有配置的激活状态（事务性操作）。"""
        with lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                # 开启一个事务
                conn.execute("BEGIN")
                # 1. 将所有配置设为不激活
                cursor.execute("UPDATE llm_configs SET is_active = 0")
                # 2. 将指定ID的配置设为激活
                cursor.execute("UPDATE llm_configs SET is_active = 1 WHERE id=?", (config_id,))
                # 提交事务
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.Error as e:
                logger.error(f"设置激活LLM配置时发生数据库事务错误: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()

    def get_active_llm_config(self):
        """获取当前激活的LLM配置的完整信息。"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, provider_name, api_url, api_key, model_name FROM llm_configs WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    # ========================== END: MODIFICATION ============================


# 创建一个全局存储实例
store = SQLiteStore()