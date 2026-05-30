"""
开机自启管理 — 通过 Windows 注册表实现开机自动运行。

注册表路径：HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
项名称：历史粘贴板

兼容两种运行模式：
- 源码运行：注册 pythonw.exe + 脚本路径（无命令行窗口）
- 打包后 exe：注册 exe 文件路径
"""

import sys
import os
from pathlib import Path

# 注册表中的键名
_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "ClipboardManager"  # 内部用英文名，避免编码问题


def _get_target_path() -> str:
    """获取要注册的启动路径。"""
    if getattr(sys, "frozen", False):
        # 打包后的 exe 模式
        return f'"{sys.executable}"'
    else:
        # 源码运行模式：使用 pythonw.exe 避免弹出命令行窗口
        python_dir = Path(sys.executable).parent
        pythonw = python_dir / "pythonw.exe"
        if not pythonw.exists():
            pythonw = python_dir / "python.exe"  # 降级

        main_script = Path(__file__).parent.parent / "main.py"
        # 设置工作目录到 src/ 的父目录（项目根）
        work_dir = main_script.parent.parent
        return f'"{pythonw}" "{main_script}" --workdir "{work_dir}"'


def is_enabled() -> bool:
    """检查当前是否已设置为开机自启。"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ
        )
        try:
            value, _ = winreg.QueryValueEx(key, _REG_NAME)
            return bool(value)
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


def enable():
    """开启开机自启。"""
    try:
        import winreg
        target = _get_target_path()
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, target)
        winreg.CloseKey(key)
        return True
    except OSError as e:
        print(f"[开机自启] 设置失败: {e}")
        return False


def disable():
    """关闭开机自启。"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
        )
        try:
            winreg.QueryValueEx(key, _REG_NAME)
            winreg.DeleteValue(key, _REG_NAME)
        except FileNotFoundError:
            pass  # 本来就没注册，不需要删
        winreg.CloseKey(key)
        return True
    except OSError as e:
        print(f"[开机自启] 取消失败: {e}")
        return False
