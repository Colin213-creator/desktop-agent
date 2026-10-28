"""工具注册表：模型看到说明书，代码查表执行。"""

from __future__ import annotations

from .files import (
    check_port,
    get_disk_usage,
    get_system_info,
    list_dir,
    read_file,
    write_file,
)


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOLS: list[dict] = [
    _fn(
        "get_disk_usage",
        "查看磁盘的总容量、已用与剩余空间。用户问磁盘还剩多少、C盘够不够用时调用。",
        {"drive": {"type": "string", "description": "盘符，例如 C: 或 D:"}},
        ["drive"],
    ),
    _fn(
        "check_port",
        "检查本机端口是否被程序监听。用于判断远程桌面、数据库等服务有没有启动。",
        {"port": {"type": "integer", "description": "端口号，例如 3389 是远程桌面"}},
        ["port"],
    ),
    _fn("get_system_info", "获取主机名、系统版本、CPU 核数与内存大小。", {}, []),
    _fn(
        "list_dir",
        "列出某个目录下的文件和子目录。",
        {"path": {"type": "string", "description": "目录路径，例如 E:\\"}},
        ["path"],
    ),
    _fn(
        "read_file",
        "读取一个文本文件的内容。",
        {"path": {"type": "string", "description": "文件完整路径"}},
        ["path"],
    ),
    _fn(
        "write_file",
        "把文本写入指定文件。父目录必须存在；属于破坏性操作，覆盖已有文件前需确认。",
        {
            "path": {"type": "string", "description": "目标文件完整路径"},
            "content": {"type": "string", "description": "要写入的文本"},
        },
        ["path", "content"],
    ),
]


_IMPL = {
    "get_disk_usage": get_disk_usage,
    "check_port": check_port,
    "get_system_info": get_system_info,
    "list_dir": list_dir,
    "read_file": read_file,
    "write_file": write_file,
}


def tool_names() -> list[str]:
    return list(_IMPL)


def execute(name: str, args: dict) -> dict:
    """执行工具。任何异常都转成 {"error": ...}，绝不让 Agent 崩掉。"""
    func = _IMPL.get(name)
    if func is None:
        return {"error": f"没有名为 {name} 的工具"}
    try:
        return func(**(args or {}))
    except Exception as exc:
        return {"error": f"{name} 执行失败：{type(exc).__name__}: {exc}"}
