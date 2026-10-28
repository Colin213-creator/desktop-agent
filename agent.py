# -*- coding: utf-8 -*-
"""
通用智能体：什么问题都能问

它按三种情况处理问题：
    1. 自己就会的（数学、写代码、常识、翻译）  -> 直接回答，不调工具
    2. 有工具覆盖的（天气、时间、磁盘、端口、系统状态、文件）-> 调工具拿真实数据
    3. 没有工具能查的实时信息（股价、新闻）     -> 如实说查不到，绝不编造

用法：
    python agent.py "帮我查看C盘空间"
    python agent.py "现在几点了"
    python agent.py            （不带参数进对话模式，可连续追问）

多轮对话：同一个 Agent 实例里的 messages 会一直保留，
所以你可以先问「D盘最大的文件是什么」，接着问「它有多大」。
"""

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime

import requests

OLLAMA = "http://127.0.0.1:11434"
MODEL = "qwen2.5:3b"
MAX_ROUNDS = 6          # 最多来回几轮，防止模型卡在工具循环里


# ==================== 1. 工具的真实实现 ====================
# 模型看不到这些代码，它只能"请求"调用；真正执行的是这里。

def get_time() -> dict:
    """当前日期和时间。"""
    now = datetime.now()
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": "周" + "一二三四五六日"[now.weekday()],
    }


def get_system_info() -> dict:
    """本机基本信息：主机名、系统、CPU、内存。"""
    import ctypes

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
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    gb = 1024 ** 3

    return {
        "hostname": socket.gethostname(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
        "os": f"{platform.system()} {platform.release()}",
        "cpu_cores": os.cpu_count(),
        "memory_total_gb": round(mem.ullTotalPhys / gb, 1),
        "memory_free_gb": round(mem.ullAvailPhys / gb, 1),
        "python": platform.python_version(),
    }


def get_disk_usage(drive: str = "C:") -> dict:
    """查看指定磁盘的总容量、已用和剩余空间。"""
    # 容错：模型可能给 "C:"、"C"、"C盘"、"c 盘"，统一取出盘符字母
    letter = "".join(ch for ch in drive if ch.isalpha())
    if not letter:
        return {"error": f"无法识别的盘符：{drive}"}
    root = letter[0].upper() + ":\\"

    try:
        total, used, free = shutil.disk_usage(root)
    except OSError as e:
        return {"error": f"读取 {root} 失败：{e}"}

    gb = 1024 ** 3
    return {
        "drive": root[:2],
        "total_gb": round(total / gb, 1),
        "used_gb": round(used / gb, 1),
        "free_gb": round(free / gb, 1),
        "used_percent": round(used / total * 100, 1),
    }


def check_port(port: int) -> dict:
    """检查本机某个端口是否在监听。"""
    try:
        port = int(port)
    except (TypeError, ValueError):
        return {"error": f"端口号不合法：{port}"}

    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                         encoding="gbk", errors="ignore").stdout
    listening = any(f":{port} " in line and "LISTENING" in line
                    for line in out.splitlines())
    return {"port": port, "listening": listening}


def get_weather(city: str) -> dict:
    """查询指定城市当前的实时天气和气温。"""
    text = ""
    for _ in range(3):                 # 免费接口偶尔掐连接或返空，重试 3 次
        try:
            resp = requests.get(f"https://wttr.in/{city}",
                                params={"format": "3"}, timeout=20)
            resp.raise_for_status()
            text = resp.text.strip()
            if text:
                break
        except requests.RequestException:
            pass

    if not text:
        return {"city": city, "error": "天气服务暂时不可用，请稍后重试"}

    m = re.search(r"([+-]?\d+)\s*°C", text)
    return {
        "city": city,
        "temp_c": int(m.group(1)) if m else None,
        "raw": text,
        "source": "wttr.in",
    }


def list_dir(path: str = ".") -> dict:
    """列出目录下的文件（只读）。"""
    try:
        names = sorted(os.listdir(path))[:50]
    except OSError as e:
        return {"error": f"读取目录失败：{e}"}

    entries = []
    for name in names:
        full = os.path.join(path, name)
        is_dir = os.path.isdir(full)
        entries.append({
            "name": name,
            "type": "目录" if is_dir else "文件",
            "size_kb": None if is_dir else round(os.path.getsize(full) / 1024, 1),
        })
    return {"path": os.path.abspath(path), "count": len(entries), "entries": entries}


def read_file(path: str, max_chars: int = 2000) -> dict:
    """读取一个文本文件的内容（只读，最多 max_chars 个字符）。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(max_chars)
    except OSError as e:
        return {"error": f"读取文件失败：{e}"}
    return {
        "path": os.path.abspath(path),
        "content": text,
        "truncated": len(text) >= max_chars,
    }


def find_largest_files(drive: str = "D:", top_n: int = 10,
                       time_budget: int = 60) -> dict:
    """扫描整个磁盘，找出最大的若干个文件。

    两个关键设计：
      1. 用最小堆，只保留最大的 top_n 个，不去把所有文件都存进内存
      2. 设时间预算，扫不完就先返回已有的结果，并标记 complete=False
    """
    import heapq
    import time

    letter = "".join(ch for ch in drive if ch.isalpha())
    if not letter:
        return {"error": f"无法识别的盘符：{drive}"}
    root = letter[0].upper() + ":\\"

    try:
        top_n = max(1, min(int(top_n), 50))
    except (TypeError, ValueError):
        top_n = 10
    try:
        budget = max(5, int(time_budget))
    except (TypeError, ValueError):
        budget = 60

    heap = []                       # 堆里始终只留最大的 top_n 个
    scanned = 0
    deadline = time.time() + budget

    for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda e: None):
        if time.time() > deadline:
            break
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue            # 没权限、被占用、路径过长，统统跳过
            scanned += 1
            if len(heap) < top_n:
                heapq.heappush(heap, (size, full))
            elif size > heap[0][0]:
                heapq.heapreplace(heap, (size, full))

    files = [{"path": p, "size_mb": round(s / 1024 / 1024, 1)}
             for s, p in sorted(heap, reverse=True)]
    return {
        "drive": root[:2],
        "scanned_files": scanned,
        "complete": time.time() <= deadline,   # False 表示时间到了没扫完
        "top": files,
    }


# 工具名 -> 函数。模型说要调哪个，代码就来这张表里找。
TOOLS_IMPL = {
    "get_time": get_time,
    "get_system_info": get_system_info,
    "get_disk_usage": get_disk_usage,
    "check_port": check_port,
    "get_weather": get_weather,
    "list_dir": list_dir,
    "read_file": read_file,
    "find_largest_files": find_largest_files,
}


# ==================== 2. 工具说明书（给模型看的） ====================

def _fn(name, description, properties, required):
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


TOOLS_SPEC = [
    _fn("get_time", "获取当前日期和时间。用户问现在几点、今天几号时调用。", {}, []),
    _fn("get_system_info", "获取这台电脑的基本信息：主机名、操作系统、CPU 核数、内存大小。",
        {}, []),
    _fn("get_disk_usage", "查看磁盘的总容量、已用空间和剩余空间。用户问磁盘还剩多少、C盘够不够用时调用。",
        {"drive": {"type": "string", "description": "盘符，例如 C: 或 D:"}}, ["drive"]),
    _fn("check_port", "检查本机某个端口是否被程序占用/正在监听。用于判断远程桌面、数据库等服务有没有启动。",
        {"port": {"type": "integer", "description": "端口号，例如 3389 是远程桌面，11434 是 Ollama"}}, ["port"]),
    _fn("get_weather", "查询指定城市当前的实时天气和气温。",
        {"city": {"type": "string", "description": "城市名称，例如 上海、哈尔滨"}}, ["city"]),
    _fn("list_dir", "列出某个目录下的文件和子目录。",
        {"path": {"type": "string", "description": "目录路径，例如 E:\\ 或 C:\\Users"}}, ["path"]),
    _fn("read_file", "读取一个文本文件的内容。",
        {"path": {"type": "string", "description": "文件的完整路径"}}, ["path"]),
    _fn("find_largest_files",
        "扫描整个磁盘，找出占用空间最大的文件。用户问某个盘上最大的文件是什么、谁占空间最多时调用。",
        {
            "drive": {"type": "string", "description": "盘符，例如 D: 或 C:"},
            "top_n": {"type": "integer", "description": "要返回几个文件，默认 10"},
        },
        ["drive"]),
]


# ==================== 3. 系统提示词：决定它是不是一个合格的智能体 ====================

SYSTEM_PROMPT = """你是一个运行在用户 Windows 笔记本上的智能体。请严格遵守：

1. 数学计算、写代码、常识、翻译、写作这类你本来就会的问题，直接回答，不要调用工具。
2. 涉及实时信息（天气、时间）或这台电脑的状态（磁盘、端口、系统配置、文件），
   必须先调用工具拿到真实数据，再根据数据回答，禁止凭记忆编造。
3. 如果问题需要实时信息，而现有工具都查不到（例如股价、新闻、别人的电脑），
   必须如实回答"这个我查不到"，绝对不允许编造任何数字或事实。
4. 用中文回答，简洁直接，不要啰嗦。"""


# ==================== 4. 与模型通信 ====================

def chat(messages: list) -> dict:
    """把整段对话发给模型，返回 assistant 的 message。"""
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS_SPEC,
        "stream": False,
    }
    resp = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["message"]


def execute_tool(name: str, args: dict) -> dict:
    """执行工具。失败也返回一个正常的结果，不要把整个程序炸掉。"""
    func = TOOLS_IMPL.get(name)
    if not func:
        return {"error": f"没有名为 {name} 的工具"}
    try:
        return func(**args)
    except Exception as e:
        return {"error": f"{name} 执行失败：{type(e).__name__}: {e}"}


# ==================== 5. 智能体（带记忆） ====================

class Agent:
    """带记忆的智能体。

    关键：messages 挂在实例上，不随每次提问重建，
    所以同一个 Agent 连续问好几轮，模型都记得前面说过什么。
    """

    def __init__(self, keep_turns: int = 8):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.keep_turns = keep_turns     # 最多保留最近几轮，防止上下文无限膨胀

    def ask(self, question: str, verbose: bool = True) -> str:
        """问一个问题，返回最终答复文本。多轮共享同一份 messages。"""
        self.messages.append({"role": "user", "content": question})

        for step in range(1, MAX_ROUNDS + 1):
            msg = chat(self.messages)
            self.messages.append(msg)

            calls = msg.get("tool_calls")
            if not calls:                # 模型不再要工具 => 这就是最终答复
                answer = (msg.get("content") or "").strip()
                if verbose:
                    print("\n最终答复：", answer)
                self._trim()             # 答完再裁剪历史，避免中途破坏消息结构
                return answer

            for call in calls:
                name = call["function"]["name"]
                args = call["function"]["arguments"]
                if verbose:
                    print(f"[第{step}轮] 调用工具： {name}({args})")

                result = execute_tool(name, args)
                if verbose:
                    print(f"          返回结果： {result}")

                self.messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return "（超过了最大轮数，模型仍在请求工具）"

    def _trim(self):
        """只保留最近的若干轮，避免 messages 越滚越长把上下文撑爆。

        从 user 消息的位置切开，这样 tool_calls 和对应的 tool 结果不会被拆散。
        """
        user_idx = [i for i, m in enumerate(self.messages) if m.get("role") == "user"]
        if len(user_idx) > self.keep_turns:
            cut = user_idx[-self.keep_turns]
            self.messages = [self.messages[0]] + self.messages[cut:]

    def reset(self):
        """清空记忆，重新开始。"""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]


def main():
    agent = Agent()

    if len(sys.argv) > 1:                # 一次性提问：python agent.py "问题"
        agent.ask(" ".join(sys.argv[1:]))
        return

    print("进入对话模式，可以连续追问，上下文会保留。")
    print("输入 清空 可以重置记忆，输入 exit 退出。\n")

    while True:
        try:
            q = input("你： ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if q.lower() in ("exit", "quit", "退出"):
            break
        if q in ("清空", "reset", "重来"):
            agent.reset()
            print("（记忆已清空）\n")
            continue
        if q:
            agent.ask(q)
            print()


if __name__ == "__main__":
    main()
