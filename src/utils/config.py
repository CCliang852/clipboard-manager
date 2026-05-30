"""
配置管理模块 — 用户设置的读取与持久化。

配置文件位置：%APPDATA%/ClipboardManager/config.json
"""

import json
from pathlib import Path

try:
    from .. import database as db
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import database as db


# 默认配置
_DEFAULT_CONFIG = {
    "retention_days": 3,       # 保留天数：1 / 3 / 5
    "auto_start": False,       # 开机自启（阶段 6 实现）
    "copy_notification": True, # 复制后右下角轻提示
}


def _get_config_path() -> Path:
    """获取配置文件路径。"""
    return db.APP_DATA / "config.json"


class ConfigManager:
    """用户配置管理器（读写 JSON 文件）。"""

    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        """从文件加载配置。文件不存在时使用默认值。"""
        path = _get_config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        # 补齐缺失的默认值
        for key, value in _DEFAULT_CONFIG.items():
            if key not in self._data:
                self._data[key] = value

    def save(self):
        """保存配置到文件。"""
        db.get_data_dir()  # 确保目录存在
        path = _get_config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default=None):
        """读取配置项。"""
        return self._data.get(key, _DEFAULT_CONFIG.get(key, default))

    def set(self, key: str, value):
        """设置配置项（不立即写入磁盘，需调用 save()）。"""
        self._data[key] = value

    def set_and_save(self, key: str, value):
        """设置并立即保存。"""
        self._data[key] = value
        self.save()
