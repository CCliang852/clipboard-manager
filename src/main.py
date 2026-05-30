"""
历史粘贴板 — 应用入口

启动流程：
1. 初始化数据库
2. 创建系统托盘图标（最小化到托盘）
3. 创建主窗口（点击托盘打开）
4. 启动剪贴板监听
5. 捕获内容时弹出轻提示
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

try:
    from . import database as db
    from .clipboard_monitor import ClipboardMonitor
    from .ui.main_window import MainWindow
    from .ui.toast import Toast
    from .utils.config import ConfigManager
    from .utils.cleanup import CleanupScheduler
except ImportError:
    import database as db
    from clipboard_monitor import ClipboardMonitor
    from ui.main_window import MainWindow
    from ui.toast import Toast
    from utils.config import ConfigManager
    from utils.cleanup import CleanupScheduler


# ---- 资源路径 ----
def _get_resource(name: str) -> str:
    """获取资源文件的绝对路径。兼容源码运行和 PyInstaller 打包。"""
    # PyInstaller 打包后 sys._MEIPASS 指向临时目录
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    path = base / "resources" / name
    return str(path) if path.exists() else str(Path(__file__).parent.parent / "resources" / name)


def main():
    # 1. 初始化数据库
    db.init_db()

    # 2. 创建 Qt 应用
    app = QApplication(sys.argv)
    app.setApplicationName("历史粘贴板")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口 = 隐藏到托盘

    # 3. 加载样式表
    qss_path = _get_resource("style.qss")
    if Path(qss_path).exists():
        with open(qss_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # 4. 检查系统托盘是否可用
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("[错误] 当前系统不支持系统托盘")
        sys.exit(1)

    # 5. 创建剪贴板监听器
    monitor = ClipboardMonitor(app.clipboard())

    # 6. 加载用户配置
    config = ConfigManager()

    # 7. 创建 Toast 轻提示
    toast = Toast()

    # 8. 启动过期清理调度器
    cleanup_scheduler = CleanupScheduler(config)
    cleanup_scheduler.start()

    # 9. 创建主窗口（延迟创建，避免启动时闪屏）
    window: MainWindow | None = None

    # 10. 定义所有内部函数（必须在引用它们之前定义）

    def get_window() -> MainWindow:
        """懒加载主窗口：首次打开时才创建。"""
        nonlocal window
        if window is None:
            window = MainWindow(monitor, config)
            window.window_closed.connect(lambda: _update_tray_menu())
        return window

    def _show_window():
        """显示主窗口并置顶。"""
        w = get_window()
        w.show()
        w.raise_()
        w.activateWindow()

    def _on_tray_activated(reason):
        """托盘图标点击事件。"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # 单击：切换显示/隐藏
            if window and window.isVisible():
                window.hide()
            else:
                _show_window()

    def _update_tray_menu():
        """窗口关闭时更新托盘菜单（不需要额外操作）。"""
        pass

    def _quit_app():
        """完全退出程序。"""
        tray.hide()
        app.quit()

    def on_captured(content_type: str, item_id: int):
        """剪贴板捕获 → Toast 提示 + 刷新列表。"""
        if config.get("copy_notification", True):
            toast.show_toast()
        if window and window.isVisible():
            window.refresh_list()

    # 11. 创建系统托盘
    tray = QSystemTrayIcon()
    icon_path = _get_resource("icon.ico")
    if Path(icon_path).exists():
        tray.setIcon(QIcon(icon_path))
    else:
        tray.setIcon(app.style().standardIcon(app.style().SP_ComputerIcon))

    tray.setToolTip("历史粘贴板 — 正在监听")

    # 托盘菜单
    tray_menu = QMenu()

    open_action = QAction("📋 打开历史面板", tray_menu)
    open_action.triggered.connect(lambda: _show_window())
    tray_menu.addAction(open_action)

    tray_menu.addSeparator()

    quit_action = QAction("❌ 退出", tray_menu)
    quit_action.triggered.connect(_quit_app)
    tray_menu.addAction(quit_action)

    tray.setContextMenu(tray_menu)

    # 单击托盘图标 = 打开/关闭窗口
    tray.activated.connect(lambda reason: _on_tray_activated(reason))

    tray.show()

    # 12. 剪贴板捕获 → Toast 提示
    monitor.content_captured.connect(on_captured)

    # 13. 启动
    print("[历史粘贴板] 已启动")
    print(f"[历史粘贴板] 数据库: {db.DB_PATH}")
    print(f"[历史粘贴板] 图片目录: {db.IMAGES_DIR}")
    print("[历史粘贴板] 点击右下角托盘图标打开面板")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
