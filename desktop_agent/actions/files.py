"""文件、磁盘、端口、系统信息类工具。"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path

FORBIDDEN_PREFIXES = (
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
)


def get_disk_usage(drive: str = "C:") -> dict:
    """查看磁盘的总容量、已用与剩余空间。容错 "C:"/"C"/"C盘" 等写法。"""
    letter = "".join(ch for ch in str(drive) if ch.isalpha())
    if not letter:
        return {"error": f"无法识别的盘符：{drive}"}
    root = letter[0].upper() + ":\\"

    try:
        total, used, free = shutil.disk_usage(root)
    except OSError as exc:
        return {"error": f"读取 {root} 失败：{exc}"}

    gb = 1024 ** 3
    return {
        "drive": root[:2],
        "total_gb": round(total / gb, 1),
        "used_gb": round(used / gb, 1),
        "free_gb": round(free / gb, 1),
        "used_percent": round(used / total * 100, 1),
    }


def check_port(port: int) -> dict:
    """检查本机端口是否处于 LISTENING。"""
    try:
        port = int(port)
    except (TypeError, ValueError):
        return {"error": f"端口号不合法：{port}"}

    out = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="ignore",
    ).stdout
    listening = any(
        f":{port} " in line and "LISTENING" in line for line in out.splitlines()
    )
    return {"port": port, "listening": listening}


def get_system_info() -> dict:
    """主机名、系统版本、CPU 核数、内存。"""

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    mem = MEMORYSTATUSEX()
    mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    try:
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
        total_gb = round(mem.ullTotalPhys / (1024 ** 3), 1)
        free_gb = round(mem.ullAvailPhys / (1024 ** 3), 1)
    except Exception:
        total_gb = free_gb = None

    return {
        "hostname": socket.gethostname(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
        "os": f"{platform.system()} {platform.release()}",
        "cpu_cores": os.cpu_count(),
        "memory_total_gb": total_gb,
        "memory_free_gb": free_gb,
        "python": platform.python_version(),
    }


def list_dir(path: str = ".") -> dict:
    """列出目录下最多 50 个条目。"""
    try:
        names = sorted(os.listdir(path))[:50]
    except OSError as exc:
        return {"error": f"读取目录失败：{exc}"}

    entries = []
    for name in names:
        full = os.path.join(path, name)
        is_dir = os.path.isdir(full)
        entries.append(
            {
                "name": name,
                "type": "目录" if is_dir else "文件",
                "size_kb": None if is_dir else round(os.path.getsize(full) / 1024, 1),
            }
        )
    return {"path": os.path.abspath(path), "count": len(entries), "entries": entries}


def read_file(path: str, max_chars: int = 2000) -> dict:
    """读取文本文件，最多 max_chars 个字符。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read(int(max_chars))
    except (OSError, ValueError) as exc:
        return {"error": f"读取文件失败：{exc}"}
    return {
        "path": os.path.abspath(path),
        "content": text,
        "truncated": len(text) >= int(max_chars),
    }


def write_file(path: str, content: str) -> dict:
    """写文本文件。父目录必须已存在，且拒绝写入系统目录。"""
    target = Path(path)
    if not target.parent.exists():
        return {"error": f"父目录不存在：{target.parent}"}

    lowered = str(target).lower()
    if any(lowered.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        return {"error": f"拒绝写入系统目录：{target}"}

    try:
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return {"error": f"写入失败：{exc}"}

    return {"ok": True, "path": str(target), "bytes": len(content.encode("utf-8"))}
