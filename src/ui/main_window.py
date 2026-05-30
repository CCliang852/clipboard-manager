"""
主窗口 — 历史粘贴板的主界面。

布局结构：
┌──────────────────────────┐
│  🔍 搜索框               │  ← 搜索栏（固定顶部）
├──────────────────────────┤
│                          │
│  卡片列表（滚动区域）      │  ← 可滚动
│                          │
│                          │
├──────────────────────────┤
│  共 N 条记录    ⚙ 设置   │  ← 底部状态栏
└──────────────────────────┘

阶段 4：使用 CardWidget 组件，支持文字/图片卡片、右键菜单、删除确认。
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from .. import database as db
    from ..clipboard_monitor import ClipboardMonitor
    from ..utils.config import ConfigManager
    from .card_widget import CardWidget
    from .settings_dialog import SettingsDialog
except ImportError:
    import database as db
    from clipboard_monitor import ClipboardMonitor
    from utils.config import ConfigManager
    from ui.card_widget import CardWidget
    from ui.settings_dialog import SettingsDialog


class MainWindow(QWidget):
    """历史粘贴板主窗口。"""

    # 信号：通知外部（托盘）窗口已关闭
    window_closed = Signal()

    def __init__(self, monitor: ClipboardMonitor | None = None, config: ConfigManager | None = None):
        super().__init__()
        self._monitor = monitor
        self._config = config
        self._all_items: list[dict] = []
        self._search_timer: QTimer | None = None

        self._setup_ui()
        self._apply_styles()
        self._connect_signals()

        # 初始加载数据
        self.refresh_list()

    # ---- UI 搭建 ----

    def _setup_ui(self):
        """搭建界面组件。"""
        self.setWindowTitle("历史粘贴板")
        self.setObjectName("mainWindow")
        self.resize(440, 620)
        self.setMinimumSize(340, 400)

        # 窗口居中
        screen = self.screen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # 根布局
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- 搜索栏 ----
        root_layout.addWidget(self._create_search_bar())

        # ---- 卡片滚动区域 ----
        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("cardArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.NoFrame)

        self._card_container = QWidget()
        self._card_container.setObjectName("cardContainer")
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(12, 8, 12, 8)
        self._card_layout.setSpacing(6)
        self._card_layout.addStretch()  # 底部弹簧，把卡片推到顶部

        self._scroll_area.setWidget(self._card_container)
        root_layout.addWidget(self._scroll_area)

        # ---- 空状态提示 ----
        self._empty_hint = QLabel("还没有剪贴板记录\n试着复制一些文字或图片吧 ✨")
        self._empty_hint.setObjectName("emptyHint")
        self._empty_hint.setAlignment(Qt.AlignCenter)
        self._empty_hint.setWordWrap(True)
        self._card_layout.insertWidget(0, self._empty_hint)
        self._empty_hint.hide()  # 默认隐藏

        # ---- 底部状态栏 ----
        root_layout.addWidget(self._create_status_bar())

    def _create_search_bar(self) -> QWidget:
        """创建搜索栏。"""
        bar = QWidget()
        bar.setObjectName("searchBar")
        bar.setFixedHeight(52)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)

        # 搜索图标 + 输入框
        icon_label = QLabel("🔍")
        icon_label.setFont(QFont("Microsoft YaHei", 14))

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText("搜索剪贴板历史…")
        self._search_input.setClearButtonEnabled(True)

        layout.addWidget(icon_label)
        layout.addWidget(self._search_input)
        return bar

    def _create_status_bar(self) -> QWidget:
        """创建底部状态栏。"""
        bar = QWidget()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(36)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 12, 0)

        self._status_label = QLabel("共 0 条记录")
        self._status_label.setObjectName("statusLabel")

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setObjectName("settingsButton")
        self._settings_btn.setToolTip("设置")
        self._settings_btn.setFixedSize(32, 28)

        layout.addWidget(self._status_label)
        layout.addStretch()
        layout.addWidget(self._settings_btn)
        return bar

    def _apply_styles(self):
        """加载 QSS 样式表。"""
        try:
            from pathlib import Path
            qss_path = Path(__file__).parent.parent.parent / "resources" / "style.qss"
            if qss_path.exists():
                with open(qss_path, encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
        except Exception:
            pass  # 样式加载失败不影响功能

    # ---- 信号连接 ----

    def _connect_signals(self):
        """连接内部信号。"""
        # 搜索防抖定时器
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)

        # 搜索框输入 → 启动防抖定时器
        self._search_input.textChanged.connect(lambda: self._search_timer.start())

        # 设置按钮（阶段 5 实现设置面板）
        self._settings_btn.clicked.connect(self._on_settings_clicked)

    # ---- 数据刷新 ----

    def refresh_list(self):
        """从数据库重新加载并刷新卡片列表。"""
        # 清空现有卡片（保留 empty_hint 和 stretch）
        while self._card_layout.count() > 0:
            item = self._card_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                if w is not self._empty_hint:
                    w.deleteLater()

        # 重新加回 empty_hint 和 stretch
        self._card_layout.addWidget(self._empty_hint)
        self._card_layout.addStretch()

        # 从数据库加载
        query = self._search_input.text().strip()
        if query:
            self._all_items = db.search_items(query)
        else:
            self._all_items = db.get_all_items()

        # 插入卡片（在 stretch 之前）
        stretch_index = self._card_layout.count() - 1
        hint_index = stretch_index - 1  # empty_hint 在 stretch 之前

        # 移出 empty_hint，插入卡片后再决定是否显示
        self._card_layout.takeAt(hint_index)

        if not self._all_items:
            self._card_layout.insertWidget(0, self._empty_hint)
            self._empty_hint.show()
        else:
            self._empty_hint.hide()
            for i, item in enumerate(self._all_items):
                card = self._create_card(item)
                self._card_layout.insertWidget(i, card)

        # 更新状态栏
        count = db.get_count()
        self._status_label.setText(f"共 {count} 条记录")

    def _do_search(self):
        """执行搜索（防抖后调用）。"""
        self.refresh_list()

    # ---- 卡片创建 ----

    def _create_card(self, item: dict) -> CardWidget:
        """使用 CardWidget 组件创建卡片。"""
        card = CardWidget(item, self._monitor)

        # 连接信号
        card.clicked.connect(lambda iid: None)  # 复制由 CardWidget 自己处理
        card.pin_toggled.connect(self._on_pin_toggled)
        card.deleted.connect(self._on_delete_requested)

        return card

    def _on_pin_toggled(self, item_id: int, new_pinned: bool):
        """置顶状态切换后刷新列表。"""
        self.refresh_list()

    def _on_delete_requested(self, item_id: int):
        """弹出确认对话框，确认后删除。"""
        item = db.get_item_by_id(item_id)
        if item is None:
            return

        # 确认对话框
        msg = QMessageBox(self)
        msg.setWindowTitle("确认删除")
        msg.setIcon(QMessageBox.Question)

        if item["type"] == "text" and item["content"]:
            preview = item["content"][:40] + "…" if len(item["content"]) > 40 else item["content"]
            msg.setText(f"确定删除这条记录吗？\n\n「{preview}」")
        else:
            msg.setText("确定删除这张图片记录吗？")

        msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        msg.button(QMessageBox.Yes).setText("删除")
        msg.button(QMessageBox.Cancel).setText("取消")
        msg.setDefaultButton(QMessageBox.Cancel)

        # 样式
        msg.setStyleSheet("""
            QMessageBox { background-color: #FFFAFB; }
            QPushButton {
                background-color: #FFB6C1; color: white;
                border: none; border-radius: 4px; padding: 6px 18px;
            }
            QPushButton:hover { background-color: #FF9AAE; }
        """)

        if msg.exec() == QMessageBox.Yes:
            db.delete_item(item_id)
            self.refresh_list()

    # ---- 事件处理 ----

    def showEvent(self, event):
        """窗口首次显示后，延迟同步卡片宽度（等布局完成）。"""
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_card_width)

    def resizeEvent(self, event):
        """窗口大小变化时同步卡片宽度。"""
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_card_width)

    def _sync_card_width(self):
        """同步卡片容器宽度到滚动区域视口宽度。"""
        if not hasattr(self, "_scroll_area"):
            return
        vp = self._scroll_area.viewport()
        if vp and vp.width() > 0:
            self._card_container.setFixedWidth(vp.width())

    def _on_settings_clicked(self):
        """打开设置面板。"""
        if self._config is None:
            return
        dialog = SettingsDialog(self._config, self)
        dialog.exec()
        # 设置关闭后刷新列表（保留天数或通知设置可能已变）
        self.refresh_list()

    def closeEvent(self, event):
        """关闭窗口时隐藏到托盘，而非退出。"""
        event.ignore()
        self.hide()
        self.window_closed.emit()
