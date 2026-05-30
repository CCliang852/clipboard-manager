"""
剪贴板监听模块 — 在后台持续监听 Windows 剪贴板变化。

特性：
- 防抖机制：dataChanged 信号触发后等 300ms 才处理，避免截图等信号风暴
- 文字去重：与上一条文字记录比较
- 图片去重：PNG 编码后 MD5 比较（比像素字节更可靠）
- 静默复制：应用自身设置剪贴板时不触发记录
"""

import hashlib
from datetime import datetime

from PySide6.QtCore import QBuffer, QObject, QTimer, Signal
from PySide6.QtGui import QClipboard, QImage, QPixmap

try:
    from . import database as db
except ImportError:
    import database as db


class ClipboardMonitor(QObject):
    """剪贴板监听器（带防抖）。"""

    content_captured = Signal(str, int)
    DEBOUNCE_MS = 300

    def __init__(self, clipboard: QClipboard):
        super().__init__()
        self._clipboard = clipboard
        self._last_text: str | None = None
        self._last_image_hash: str | None = None
        self._paused: bool = False

        self._init_last_state()

        # 防抖定时器
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._process_clipboard)

        # dataChanged → 重设防抖定时器
        self._clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _init_last_state(self):
        last_text = db.get_last_text()
        if last_text:
            self._last_text = last_text

    def set_text_silently(self, text: str):
        """设置剪贴板文字但不触发记录。用于点击卡片复制回剪贴板。"""
        self._paused = True
        self._last_text = text
        self._clipboard.setText(text)
        self._paused = False

    # ---- 信号处理 ----

    def _on_clipboard_changed(self):
        """剪贴板变化 → 重置防抖定时器（不是立刻处理）。"""
        if self._paused:
            return
        self._debounce_timer.start(self.DEBOUNCE_MS)

    def _process_clipboard(self):
        """防抖定时器到期，真正处理剪贴板内容。"""
        mime_data = self._clipboard.mimeData()

        if mime_data.hasImage():
            self._handle_image(mime_data)
        elif mime_data.hasText():
            text = mime_data.text()
            if text and text.strip():
                self._handle_text(text.strip())

    def _handle_text(self, text: str):
        if text == self._last_text:
            return
        self._last_text = text
        try:
            item_id = db.insert_text(text)
            self.content_captured.emit("text", item_id)
        except Exception:
            pass

    def _handle_image(self, mime_data):
        """处理图片：兼容 QImage 和 QPixmap 两种返回类型。"""
        data = mime_data.imageData()

        # 兼容不同 Qt 版本/平台返回的类型
        image: QImage
        if isinstance(data, QPixmap):
            image = data.toImage()
        elif isinstance(data, QImage):
            image = data
        else:
            return

        if image.isNull():
            return

        # PNG 编码后 MD5 去重
        image_hash = self._compute_png_hash(image)
        if image_hash is None or image_hash == self._last_image_hash:
            return
        self._last_image_hash = image_hash

        # 保存到本地
        try:
            db.get_data_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"img_{timestamp}.png"
            image_path = str(db.IMAGES_DIR / filename)

            if image.save(image_path, "PNG"):
                item_id = db.insert_image(image_path)
                self.content_captured.emit("image", item_id)
        except Exception:
            pass

    @staticmethod
    def _compute_png_hash(image: QImage) -> str | None:
        """将 QImage 编码为 PNG 后计算 MD5（可靠去重）。"""
        buffer = QBuffer()
        buffer.open(QBuffer.WriteOnly)
        if not image.save(buffer, "PNG"):
            return None
        return hashlib.md5(buffer.data().data()).hexdigest()
