"""
卡片组件 — 历史粘贴板的单条记录卡片。

支持两种类型：
- 文字卡片：显示文字内容（不超过3行，超出显示省略号）
- 图片卡片：显示缩略图（120px 高度，保持比例裁剪）

交互：
- 左键点击：复制到剪贴板
- 右键点击：弹出菜单（复制 / 置顶/取消置顶 / 删除）
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from .. import database as db
    from ..clipboard_monitor import ClipboardMonitor
except ImportError:
    import database as db
    from clipboard_monitor import ClipboardMonitor


class CardWidget(QFrame):
    """
    单张历史记录卡片。

    信号：
    - clicked: 左键点击，携带 item_id
    - pin_toggled: 置顶状态切换，携带 (item_id, new_pinned)
    - deleted: 删除请求，携带 item_id
    """

    clicked = Signal(int)
    pin_toggled = Signal(int, bool)
    deleted = Signal(int)

    def __init__(self, item: dict, monitor: ClipboardMonitor | None = None):
        super().__init__()
        self._item = item
        self._monitor = monitor  # 用于静默复制

        self.setObjectName("clipboardCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # 置顶卡片特殊样式
        if item["pinned"]:
            self.setProperty("pinned", "true")
            self.style().unpolish(self)
            self.style().polish(self)

        self._setup_ui()
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ---- UI 搭建 ----

    def _setup_ui(self):
        """根据记录类型搭建不同的卡片内容。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 顶部行：置顶图标 + 时间 + 类型
        layout.addLayout(self._create_top_row())

        # 内容区：文字或图片
        if self._item["type"] == "text":
            layout.addWidget(self._create_text_content())
        else:
            layout.addWidget(self._create_image_content())

    def _create_top_row(self) -> QHBoxLayout:
        """创建顶部信息行。"""
        row = QHBoxLayout()
        row.setSpacing(8)

        # 置顶图标
        if self._item["pinned"]:
            pin_label = QLabel("📌")
            pin_label.setFont(QFont("Microsoft YaHei", 10))
            pin_label.setToolTip("已置顶")
            pin_label.setFixedWidth(24)
            row.addWidget(pin_label)

        # 相对时间（设置最小宽度，防止被挤压遮挡）
        time_label = QLabel(self._format_time(self._item["created_at"]))
        time_label.setStyleSheet("color: #9B9B9B; font-size: 11px;")
        time_label.setMinimumWidth(60)
        row.addWidget(time_label)

        row.addStretch()

        # 类型标签（设置最小宽度，防止被挤压遮挡）
        type_text = "🖼️ 图片" if self._item["type"] == "image" else "📝 文字"
        type_label = QLabel(type_text)
        type_label.setStyleSheet("color: #C4A0A8; font-size: 10px;")
        type_label.setMinimumWidth(55)
        row.addWidget(type_label)

        return row

    def _create_text_content(self) -> QWidget:
        """创建文字内容区域（最多3行，超出省略号）。"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        content = self._item.get("content", "")
        label = QLabel(content)
        label.setWordWrap(True)
        label.setMaximumHeight(60)  # 约3行 × 20px
        label.setStyleSheet("color: #4A4A4A; font-size: 13px; line-height: 1.5;")

        # 截断提示
        if len(content) > 150:
            # 截取前150字符作为显示
            truncated = content[:150].rsplit(" ", 1)[0]  # 在单词边界截断
            display = truncated[:150] + "…"
            label.setText(display)
            label.setToolTip(content[:500])  # 悬停显示前500字

        layout.addWidget(label)
        return container

    def _create_image_content(self) -> QWidget:
        """创建图片缩略图区域。"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        image_path = self._item.get("image_path", "")
        thumb_label = QLabel()
        thumb_label.setAlignment(Qt.AlignCenter)
        thumb_label.setFixedHeight(120)
        thumb_label.setStyleSheet(
            "background-color: #F5F0F0; border-radius: 6px;"
        )

        if image_path:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # 缩放填充，保持比例
                scaled = pixmap.scaledToHeight(
                    120, Qt.SmoothTransformation
                )
                if scaled.width() > 340:
                    scaled = scaled.scaledToWidth(340, Qt.SmoothTransformation)
                thumb_label.setPixmap(scaled)
            else:
                thumb_label.setText("🖼️ 图片加载失败")
                thumb_label.setStyleSheet(
                    thumb_label.styleSheet() + "color: #C4A0A8; font-size: 13px;"
                )
        else:
            thumb_label.setText("🖼️ 图片")
            thumb_label.setStyleSheet(
                thumb_label.styleSheet() + "color: #C4A0A8; font-size: 13px;"
            )

        layout.addWidget(thumb_label)
        return container

    # ---- 交互事件 ----

    def mousePressEvent(self, event):
        """左键点击 → 复制到剪贴板。"""
        if event.button() == Qt.LeftButton:
            self._copy_to_clipboard()
            self.clicked.emit(self._item["id"])
        super().mousePressEvent(event)

    def _copy_to_clipboard(self):
        """复制内容到剪贴板。"""
        if self._monitor is None:
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            if self._item["type"] == "text" and self._item["content"]:
                clipboard.setText(self._item["content"])
            return

        if self._item["type"] == "text" and self._item["content"]:
            self._monitor.set_text_silently(self._item["content"])
        elif self._item["type"] == "image" and self._item.get("image_path"):
            # 图片复制：从文件加载 QPixmap 设置到剪贴板
            pixmap = QPixmap(self._item["image_path"])
            if not pixmap.isNull():
                from PySide6.QtWidgets import QApplication
                QApplication.clipboard().setPixmap(pixmap)

    def _show_context_menu(self, pos):
        """右键弹出上下文菜单。"""
        menu = QMenu(self)

        # 复制
        copy_action = QAction("📋 复制", menu)
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_action)

        # 置顶 / 取消置顶
        if self._item["pinned"]:
            pin_action = QAction("📌 取消置顶", menu)
        else:
            pin_action = QAction("📌 置顶", menu)
        pin_action.triggered.connect(self._toggle_pin)
        menu.addAction(pin_action)

        menu.addSeparator()

        # 删除
        delete_action = QAction("🗑️ 删除", menu)
        delete_action.triggered.connect(self._request_delete)
        menu.addAction(delete_action)

        menu.popup(self.mapToGlobal(pos))

    def _toggle_pin(self):
        """切换置顶状态。"""
        new_pinned = db.toggle_pin(self._item["id"])
        self._item["pinned"] = new_pinned
        self.pin_toggled.emit(self._item["id"], new_pinned)

    def _request_delete(self):
        """发出删除请求（由主窗口处理确认对话框）。"""
        self.deleted.emit(self._item["id"])

    # ---- 工具 ----

    @staticmethod
    def _format_time(timestamp: str) -> str:
        """将时间戳转换为相对时间描述。"""
        from datetime import datetime

        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            diff = now - dt

            if diff.days > 0:
                return f"{diff.days}天前"
            hours = diff.seconds // 3600
            if hours > 0:
                return f"{hours}小时前"
            mins = diff.seconds // 60
            if mins > 0:
                return f"{mins}分钟前"
            return "刚刚"
        except ValueError:
            return timestamp
