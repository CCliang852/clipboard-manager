"""
设置面板 — 用户可调整保留天数、开机自启、复制提示等设置。

布局结构：
┌──────────────────────────────────┐
│          ⚙️  设置                 │
├──────────────────────────────────┤
│  历史记录保留时长                 │
│  ○ 1天   ● 3天   ○ 5天          │
│  ──────────────────────────────  │
│  开机自启                        │
│  [========●========]  已开启     │
│  ──────────────────────────────  │
│  复制提示                        │
│  [========●========]  已开启     │
├──────────────────────────────────┤
│              [关闭]              │
└──────────────────────────────────┘
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

try:
    from ..utils.config import ConfigManager
    from ..utils import autostart
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.config import ConfigManager
    from utils import autostart


class SettingsDialog(QDialog):
    """设置对话框。"""

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config

        self.setWindowTitle("⚙️  设置")
        self.setObjectName("settingsDialog")
        self.setFixedSize(360, 340)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowCloseButtonHint
        )

        self._setup_ui()
        self._load_config()
        self._apply_styles()

    def _setup_ui(self):
        """搭建设置面板 UI。"""
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(0)

        # ---- 标题 ----
        title = QLabel("⚙️  设置")
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #4A4A4A; padding-bottom: 16px;"
        )
        root.addWidget(title)

        # ---- 保留天数 ----
        root.addWidget(self._create_section_label("历史记录保留时长"))
        root.addLayout(self._create_retention_row())
        root.addWidget(self._create_divider())

        # ---- 开机自启 ----
        root.addWidget(self._create_toggle_row(
            "开机自启",
            "启动电脑时自动运行历史粘贴板",
            "auto_start",
        ))
        root.addWidget(self._create_divider())

        # ---- 复制提示 ----
        root.addWidget(self._create_toggle_row(
            "复制提示",
            "复制内容后右下角弹出轻提示",
            "copy_notification",
        ))

        # ---- 底部弹簧 + 关闭按钮 ----
        root.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setObjectName("settingsCloseBtn")
        close_btn.setFixedHeight(36)
        close_btn.clicked.connect(self._on_close)
        root.addWidget(close_btn, alignment=Qt.AlignCenter)

    def _create_section_label(self, text: str) -> QLabel:
        """创建段落标题。"""
        label = QLabel(text)
        label.setStyleSheet(
            "color: #9B9B9B; font-size: 12px; padding: 12px 0 8px 0;"
        )
        return label

    def _create_retention_row(self) -> QHBoxLayout:
        """创建保留天数单选按钮行。"""
        row = QHBoxLayout()
        row.setSpacing(24)
        row.setContentsMargins(0, 0, 0, 8)

        self._radio_1 = QRadioButton("1 天")
        self._radio_3 = QRadioButton("3 天")
        self._radio_5 = QRadioButton("5 天")

        for radio in (self._radio_1, self._radio_3, self._radio_5):
            radio.setStyleSheet("font-size: 13px; color: #4A4A4A;")
            row.addWidget(radio)

        row.addStretch()
        return row

    def _create_toggle_row(
        self, title: str, desc: str, config_key: str
    ) -> QWidget:
        """创建带开关的设置行。"""
        container = QWidget()
        container.setFixedHeight(52)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        # 左侧文字
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 13px; color: #4A4A4A; font-weight: bold;")

        desc_label = QLabel(desc)
        desc_label.setStyleSheet("font-size: 11px; color: #C4A0A8;")

        text_col.addWidget(title_label)
        text_col.addWidget(desc_label)
        layout.addLayout(text_col)
        layout.addStretch()

        # 右侧开关
        toggle = QCheckBox()
        toggle.setObjectName(f"toggle_{config_key}")
        toggle.setFixedSize(44, 24)
        toggle.stateChanged.connect(
            lambda state, k=config_key: self._on_toggle_changed(k, state)
        )

        # 保存引用以便后续读写
        if config_key == "auto_start":
            self._toggle_auto_start = toggle
        elif config_key == "copy_notification":
            self._toggle_notification = toggle

        layout.addWidget(toggle)
        return container

    def _create_divider(self) -> QWidget:
        """创建分割线。"""
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #F5E6E8; margin: 0 0 0 0;")
        return line

    def _apply_styles(self):
        """加载对话框专用样式。"""
        self.setStyleSheet("""
            QDialog#settingsDialog {
                background-color: #FFFAFB;
            }
            QRadioButton {
                spacing: 8px;
                font-size: 13px;
                color: #4A4A4A;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #FFD4DC;
                background-color: #FFFFFF;
            }
            QRadioButton::indicator:checked {
                background-color: #FFB6C1;
                border: 2px solid #FFB6C1;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #FFB6C1;
            }
            /* 开关样式（QCheckBox 模拟） */
            QCheckBox::indicator {
                width: 42px;
                height: 22px;
                border-radius: 11px;
                border: 2px solid #E0E0E0;
                background-color: #E0E0E0;
            }
            QCheckBox::indicator:checked {
                background-color: #FFB6C1;
                border: 2px solid #FFB6C1;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #FFD4DC;
            }
            QPushButton#settingsCloseBtn {
                background-color: #FFB6C1;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 40px;
            }
            QPushButton#settingsCloseBtn:hover {
                background-color: #FF9AAE;
            }
        """)

    # ---- 配置读写 ----

    def _load_config(self):
        """从配置管理器加载当前值到 UI。"""
        # 保留天数
        days = self._config.get("retention_days", 3)
        if days == 1:
            self._radio_1.setChecked(True)
        elif days == 5:
            self._radio_5.setChecked(True)
        else:
            self._radio_3.setChecked(True)

        # 开机自启（以注册表实际状态为准）
        actual_auto = autostart.is_enabled()
        self._toggle_auto_start.setChecked(actual_auto)
        self._config.set("auto_start", actual_auto)
        # 复制提示
        self._toggle_notification.setChecked(
            self._config.get("copy_notification", True)
        )

    def _on_toggle_changed(self, key: str, state: int):
        """开关状态变化 → 立即保存并执行对应操作。"""
        checked = state == Qt.Checked.value
        self._config.set_and_save(key, checked)

        # 开机自启开关 → 实际操作注册表
        if key == "auto_start":
            if checked:
                success = autostart.enable()
                if not success:
                    # 注册表操作失败，回弹开关
                    self._toggle_auto_start.setChecked(False)
                    self._config.set_and_save("auto_start", False)
            else:
                autostart.disable()

    def _on_close(self):
        """关闭对话框前保存保留天数。"""
        # 读取保留天数
        if self._radio_1.isChecked():
            days = 1
        elif self._radio_5.isChecked():
            days = 5
        else:
            days = 3
        self._config.set_and_save("retention_days", days)

        self.accept()
