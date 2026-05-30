"""
数据库模块 — SQLite 数据库的初始化与 CRUD 操作。

数据库位置：%APPDATA%/ClipboardManager/clipboard.db
图片存储位置：%APPDATA%/ClipboardManager/images/
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


# ---- 路径常量 ----
APP_DATA = Path(os.environ.get("APPDATA", "")) / "ClipboardManager"
DB_PATH = APP_DATA / "clipboard.db"
IMAGES_DIR = APP_DATA / "images"


def get_data_dir() -> Path:
    """获取数据目录，如果不存在则创建。"""
    APP_DATA.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DATA


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（自动创建目录和数据库文件）。"""
    get_data_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")  # 提高并发读写性能
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库：创建表结构和索引（如果不存在）。"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clipboard_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            type            TEXT    NOT NULL,
            content         TEXT,
            image_path      TEXT,
            thumbnail_path  TEXT,
            pinned          INTEGER DEFAULT 0,
            created_at      TEXT    NOT NULL,
            source_app      TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_created_at
        ON clipboard_items(created_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pinned
        ON clipboard_items(pinned)
    """)

    conn.commit()
    conn.close()


# ---- 写入操作 ----

def insert_text(content: str, source_app: str = "") -> int:
    """插入一条文字记录，返回新记录的 ID。"""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO clipboard_items (type, content, created_at, source_app) VALUES (?, ?, ?, ?)",
        ("text", content, now, source_app),
    )
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id


def insert_image(image_path: str, thumbnail_path: str = "", source_app: str = "") -> int:
    """插入一条图片记录，返回新记录的 ID。"""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO clipboard_items (type, image_path, thumbnail_path, created_at, source_app) VALUES (?, ?, ?, ?, ?)",
        ("image", image_path, thumbnail_path, now, source_app),
    )
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id


# ---- 查询操作 ----

def get_all_items(limit: int = 200) -> list[dict]:
    """获取所有记录：置顶优先，时间降序。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, content, image_path, thumbnail_path, pinned, created_at, source_app "
        "FROM clipboard_items ORDER BY pinned DESC, created_at DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


def search_items(query: str, limit: int = 200) -> list[dict]:
    """搜索文字记录（忽略大小写）。图片记录不参与文本搜索。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, content, image_path, thumbnail_path, pinned, created_at, source_app "
        "FROM clipboard_items "
        "WHERE type='text' AND content LIKE ? "
        "ORDER BY pinned DESC, created_at DESC LIMIT ?",
        (f"%{query}%", limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


def get_last_text() -> str | None:
    """获取最近一条文字记录的内容（用于去重）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content FROM clipboard_items WHERE type='text' ORDER BY created_at DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_item_by_id(item_id: int) -> dict | None:
    """根据 ID 获取单条记录。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, content, image_path, thumbnail_path, pinned, created_at, source_app "
        "FROM clipboard_items WHERE id=?",
        (item_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


# ---- 更新操作 ----

def toggle_pin(item_id: int) -> bool:
    """切换置顶状态，返回新的 pinned 值。"""
    item = get_item_by_id(item_id)
    if item is None:
        return False
    new_pinned = 0 if item["pinned"] else 1
    conn = get_connection()
    conn.execute("UPDATE clipboard_items SET pinned=? WHERE id=?", (new_pinned, item_id))
    conn.commit()
    conn.close()
    return bool(new_pinned)


# ---- 删除操作 ----

def delete_item(item_id: int) -> dict | None:
    """删除一条记录。如果是图片记录，同时删除本地图片文件。"""
    item = get_item_by_id(item_id)
    if item is None:
        return None

    # 如果是图片，删除本地文件
    if item["type"] == "image":
        for path_key in ("image_path", "thumbnail_path"):
            path = item.get(path_key)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass  # 文件被占用或不存在，忽略

    conn = get_connection()
    conn.execute("DELETE FROM clipboard_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return item


def cleanup_old(days: int) -> int:
    """删除超过指定天数的非置顶记录。返回删除条数。"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    # 先查出要删的图片记录，删除物理文件
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, image_path, thumbnail_path FROM clipboard_items "
        "WHERE type='image' AND pinned=0 AND created_at < ?",
        (cutoff,),
    )
    image_rows = cursor.fetchall()
    for row in image_rows:
        for path in (row[1], row[2]):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # 删除数据库记录
    cursor.execute(
        "DELETE FROM clipboard_items WHERE pinned=0 AND created_at < ?",
        (cutoff,),
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


# ---- 统计 ----

def get_count() -> int:
    """获取总记录数。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM clipboard_items")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ---- 内部工具 ----

def _row_to_dict(row: tuple) -> dict:
    """将数据库行转换为字典。"""
    return {
        "id": row[0],
        "type": row[1],
        "content": row[2],
        "image_path": row[3],
        "thumbnail_path": row[4],
        "pinned": bool(row[5]),
        "created_at": row[6],
        "source_app": row[7],
    }
