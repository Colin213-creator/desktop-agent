# -*- coding: utf-8 -*-
"""
用 Python 库完成一轮完整的大模型工具调用（Tool Calling）

对比手工 curl：不用拼 JSON 字符串，不用手动复制 id 和结果，
整个过程是一个循环，代码自己判断模型要不要调工具。

流程（对应你之前手工做的 4 步）：
    1. 把「用户问题 + 工具说明书」发给模型        <- 第 1 次 curl
    2. 模型回 tool_calls，说明它要调用某个工具     <- 你在响应里看到的 tool_calls
    3. 我们在本地真的执行这个工具（查天气）        <- 你手动敲的 wttr.in
    4. 把执行结果追加进对话，再发一次              <- 第 2 次 curl
    5. 模型这才用自然语言回答

关键点：模型只会「要求」调用工具，真正干活的是你的代码。
"""

import json
import re
import sys

import requests

# Ollama 的 OpenAI 兼容端点也能用：http://127.0.0.1:11434/v1
OLLAMA = "http://127.0.0.1:11434"
MODEL = "qwen2.5:3b"


# ============ 1. 工具的真实实现（模型看不到这段代码） ============

def get_weather(city: str) -> dict:
    """真的去查天气。返回结构化数据，方便模型理解。"""
    text = ""
    for _ in range(3):                            # wttr.in 是免费接口，偶尔掐连接或返回空，重试 3 次
        try:
            resp = requests.get(f"https://wttr.in/{city}",
                                params={"format": "3"}, timeout=20)
            resp.raise_for_status()
            text = resp.text.strip()              # 例如 "上海: ☁️  +26°C"
            if text:
                break
        except requests.RequestException:
            pass

    if not text:
        # 注意：工具失败也要返回一个正常的结果，不要抛异常
        return {"city": city, "error": "天气服务暂时不可用，请稍后重试"}

    m = re.search(r"([+-]?\d+)\s*°C", text)
    return {
        "city": city,
        "temp_c": int(m.group(1)) if m else None,
        "raw": text,
        "source": "wttr.in",
    }


def get_disk_usage(drive: str = "C:") -> dict:
    """查看指定磁盘的总容量、已用空间和剩余空间。"""
    import shutil

    # 容错：模型可能给 "C:"、"C"、"C盘"、"c 盘"，统一取出盘符字母
    letter = "".join(ch for ch in drive if ch.isalpha())
    if not letter:
        return {"error": f"无法识别的盘符：{drive}"}
    root = letter[0].upper() + ":\\"          # 拼成 "C:\"

    try:
        total, used, free = shutil.disk_usage(root)
    except OSError as e:
        return {"error": f"读取 {root} 失败：{e}"}

    gb = 1024 ** 3
    return {
        "drive": root[:2],                    # "C:"
        "total_gb": round(total / gb, 1),
        "used_gb": round(used / gb, 1),
        "free_gb": round(free / gb, 1),
        "used_percent": round(used / total * 100, 1),
    }


# 工具名 -> 函数。模型说要调哪个，我们就查这张表
TOOLS_IMPL = {
    "get_weather": get_weather,
    "get_disk_usage": get_disk_usage,
}


# ============ 2. 工具说明书（这部分是给模型看的） ============

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市当前的实时天气和气温。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，中文或拼音均可，例如 上海。",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_disk_usage",
            "description": "查看本机指定磁盘的总容量、已用空间和剩余空间。用户问磁盘还剩多少、C盘空间够不够时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "drive": {
                        "type": "string",
                        "description": "盘符，例如 C: 或 D:，不传默认查 C 盘。",
                    }
                },
                "required": ["drive"],
            },
        },
    },
]


# ============ 3. 调一次模型 ============

def chat(messages: list) -> dict:
    """发一次请求，返回 assistant 的 message 字典。"""
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS_SPEC,
        "stream": False,
    }
    resp = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["message"]


# ============ 4. 主循环 ============

def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "上海现在天气怎么样？多少度？"

    messages = [
        {"role": "system",
         "content": "涉及天气、气温、端口状态、磁盘容量这类实时事实时必须调用工具获取，禁止凭记忆编造。"},
        {"role": "user", "content": question},
    ]

    for step in range(1, 6):                  # 最多来回 5 次，防止无限循环
        msg = chat(messages)
        messages.append(msg)

        calls = msg.get("tool_calls")
        if not calls:                          # 没有工具调用 => 模型给出最终答案
            print("\n最终答复：", msg.get("content"))
            return

        for call in calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            print(f"[第{step}轮] 模型要求调用： {name}({args})")

            func = TOOLS_IMPL.get(name)
            try:
                result = func(**args) if func else {"error": f"没有名为 {name} 的工具"}
            except Exception as e:
                # 工具执行失败，也要把失败原因回灌给模型，
                # 让它能回答「查不到」而不是整个程序崩掉
                result = {"error": f"{name} 执行失败：{type(e).__name__}: {e}"}
            print(f"          真实执行结果： {result}")

            # 把结果以 role=tool 追加回去。注意 content 必须是字符串
            messages.append({
                "role": "tool",
                "tool_name": name,
                "content": json.dumps(result, ensure_ascii=False),
            })

    print("\n超过了最大轮数，仍然没有最终答复。")


if __name__ == "__main__":
    main()
