"""
轻提示 (Toast) 组件 — 屏幕右下角短暂弹出提示"已复制到历史记录"。

特性：
- 无边框半透明窗口
- 从底部滑入 → 停留 1.5 秒 → 淡出
- 粉色背景 + 白色文字
"""

from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout


class Toast(QWidget):
    """轻提示弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toast")
        self._setup_ui()
        self._anim_in: QPropertyAnimation | None = None
        self._anim_out: QPropertyAnimation | None = None
        self._showing: bool = False  # 防止短时间重复弹出

    def _setup_ui(self):
        """搭建 Toast UI。"""
        # 无边框 + 置顶 + 透明背景
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.setFixedSize(260, 48)

        # 内容
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("已复制到历史记录 ✓")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFont(QFont("Microsoft YaHei", 12))
        self._label.setStyleSheet(
            "color: #FFFFFF;"
            "background-color: #FFB6C1;"
            "border-radius: 10px;"
            "padding: 10px 20px;"
        )
        layout.addWidget(self._label)

    def show_toast(self, duration_ms: int = 1500):
        """显示 Toast，默认 1.5 秒后自动消失。正在显示时忽略重复调用。"""
        if self._showing:
            return  # 冷却中，跳过
        self._showing = True

        # 定位到屏幕右下角
        screen = self.screen().availableGeometry()
        x = screen.right() - self.width() - 20
        y = screen.bottom() - self.height() - 40
        self.move(x, screen.bottom() + 50)  # 初始位置在屏幕下方

        self.show()
        self.raise_()

        # 停止之前的动画（如果有）
        if self._anim_in and self._anim_in.state() == QPropertyAnimation.Running:
            self._anim_in.stop()
        if self._anim_out and self._anim_out.state() == QPropertyAnimation.Running:
            self._anim_out.stop()

        # 滑入动画
        self._anim_in = QPropertyAnimation(self, b"pos")
        self._anim_in.setDuration(300)
        self._anim_in.setStartValue(self.pos())
        self._anim_in.setEndValue(QPoint(x, y))
        self._anim_in.finished.connect(lambda: self._start_fadeout(duration_ms))
        self._anim_in.start()

    def _start_fadeout(self, delay_ms: int):
        """延迟后开始淡出动画。"""
        QTimer.singleShot(delay_ms, self._fade_out)

    def _fade_out(self):
        """淡出并关闭。"""
        self._anim_out = QPropertyAnimation(self, b"windowOpacity")
        self._anim_out.setDuration(200)
        self._anim_out.setStartValue(1.0)
        self._anim_out.setEndValue(0.0)
        self._anim_out.finished.connect(self._on_hidden)
        self._anim_out.start()

    def _on_hidden(self):
        """动画结束后隐藏并解除冷却。"""
        self.hide()
        self._showing = False
