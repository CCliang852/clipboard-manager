# 技术规范 — 历史粘贴板

> 版本：v1.0  
> 更新日期：2026-05-31  

---

## 1. 技术栈选型

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 语言 | Python | 3.11+ | 生态丰富，开发效率高，小白友好 |
| GUI | PySide6 | 6.5+ | Qt 官方绑定，系统托盘/剪贴板 API 完善 |
| 数据库 | SQLite | 内置 | 零配置，轻量，适合本地单机存储 |
| 打包 | PyInstaller | 6.x | 将 Python 项目打包为单个 .exe |
| 图片处理 | Pillow | 10.x | 缩略图生成、格式转换 |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────┐
│                  用户交互层                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ 系统托盘  │  │ 主窗口    │  │ 设置面板   │  │
│  │ (Tray)   │  │ (Window) │  │ (Settings)│  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       │              │              │         │
├───────┴──────────────┴──────────────┴─────────┤
│                  业务逻辑层                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ 剪贴板   │  │ 搜索过滤  │  │ 保留清理   │  │
│  │ 监听器   │  │ 引擎     │  │ 调度器     │  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       │              │              │         │
├───────┴──────────────┴──────────────┴─────────┤
│                  数据存储层                    │
│  ┌──────────────────────────────────────┐    │
│  │           SQLite 数据库               │    │
│  │      clipboard_items 表              │    │
│  └──────────────────────────────────────┘    │
│  ┌──────────────────────────────────────┐    │
│  │        本地文件系统（图片存储）         │    │
│  │      %AppData%/ClipboardManager/      │    │
│  └──────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 3. 模块划分

```
src/
├── main.py                  # 入口：初始化应用、启动托盘
├── clipboard_monitor.py     # 剪贴板监听线程
├── database.py              # 数据库初始化、CRUD 操作
├── ui/
│   ├── main_window.py       # 主窗口（卡片列表 + 搜索栏）
│   ├── card_widget.py       # 单张卡片组件
│   ├── settings_dialog.py   # 设置对话框
│   └── toast.py             # 轻提示弹窗
├── utils/
│   ├── config.py            # 配置管理（保留天数、自启等）
│   ├── autostart.py         # 开机自启管理
│   └── cleanup.py           # 过期记录清理
└── resources/
    ├── icon.ico             # 应用图标
    └── style.qss            # Qt 样式表
```

---

## 4. 数据库设计

### 4.1 数据库位置
`%APPDATA%/ClipboardManager/clipboard.db`

### 4.2 表结构

```sql
CREATE TABLE IF NOT EXISTS clipboard_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type          TEXT    NOT NULL,   -- 'text' 或 'image'
    content       TEXT,               -- 文字内容（type='text'时使用）
    image_path    TEXT,               -- 图片文件路径（type='image'时使用）
    thumbnail_path TEXT,              -- 缩略图路径
    pinned        INTEGER DEFAULT 0,  -- 0=未置顶, 1=已置顶
    created_at    TEXT    NOT NULL,   -- ISO 格式时间戳
    source_app    TEXT                -- 复制来源窗口标题（可选）
);

CREATE INDEX IF NOT EXISTS idx_created_at ON clipboard_items(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pinned ON clipboard_items(pinned);
```

### 4.3 图片存储路径
`%APPDATA%/ClipboardManager/images/`  
文件命名：`{id}_{timestamp}.png`

---

## 5. 剪贴板监听方案

### 5.1 方案选择
使用 PySide6 的 `QClipboard.dataChanged` 信号（事件驱动），而非轮询。

### 5.2 工作流程
```
1. 应用启动 → 连接 QClipboard.dataChanged 信号
2. 信号触发 → 读取剪贴板内容
3. 判断类型：
   - 有文本 → 与上一条文本比较，不同则存入 DB
   - 有图片 → 与上一条图片 MD5 比较，不同则保存图片+存 DB
4. 显示轻提示（可选）
```

### 5.3 去重策略
- **文字**：与最近一条文字记录直接字符串比较
- **图片**：计算 MD5 哈希，与最近一条图片记录比较

---

## 6. 打包方案

### 6.1 工具
PyInstaller

### 6.2 打包命令
```bash
pyinstaller --onefile --windowed --icon=resources/icon.ico --name="历史粘贴板" src/main.py
```

### 6.3 参数说明
- `--onefile`：打包为单个 .exe 文件
- `--windowed`：不显示控制台窗口
- `--icon`：指定应用图标
- `--name`：输出文件名

---

## 7. 关键依赖

```txt
PySide6>=6.5.0
Pillow>=10.0.0
pyinstaller>=6.0.0
```
