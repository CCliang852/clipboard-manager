"""
过期清理调度器 — 定时删除超过保留天数的旧记录。

启动时立即执行一次清理，之后每小时执行一次。
只清理非置顶的过期记录，并同步删除图片文件。
"""

from PySide6.QtCore import QObject, QTimer

try:
    from .. import database as db
    from ..utils.config import ConfigManager
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import database as db
    from utils.config import ConfigManager


class CleanupScheduler(QObject):
    """定时清理过期记录。"""

    # 清理间隔：每小时检查一次
    INTERVAL_MS = 60 * 60 * 1000  # 1 小时

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._timer = QTimer()
        self._timer.timeout.connect(self._do_cleanup)
        self._timer.setSingleShot(False)  # 周期性触发

    def start(self):
        """启动调度器：先立即执行一次，然后每小时执行。"""
        # 启动后 5 秒执行首次清理（等应用完全启动）
        QTimer.singleShot(5000, self._do_cleanup)
        # 之后每小时执行
        self._timer.start(self.INTERVAL_MS)

    def stop(self):
        """停止调度器。"""
        self._timer.stop()

    def _do_cleanup(self):
        """执行一次过期清理。"""
        days = self._config.get("retention_days", 3)
        try:
            deleted = db.cleanup_old(days)
            if deleted > 0:
                print(f"[清理] 已删除 {deleted} 条过期记录（保留 {days} 天）")
        except Exception as e:
            print(f"[清理] 清理出错: {e}")
