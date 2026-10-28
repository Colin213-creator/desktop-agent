"""各角色的提示词。Verifier 的提示词放在 verifier 模块内，保持上下文隔离。"""

PLANNER_PROMPT = """你是桌面智能体的规划者。把用户的任务拆成可逐步执行的步骤。

要求：
1. 每步只做一件事，总共不超过 15 步。
2. 每步给出 intent（要做什么）和 expected（完成后应该看到什么，必须能从截图判断）。
3. tool_hint 可选，从这些里取：open_app / click / type_text / press_keys /
   write_file / read_file / list_dir / get_disk_usage / check_port / screenshot。
   不确定就填 null。
4. 只输出 JSON，不要解释，不要 markdown 代码块。格式：
{"steps":[{"intent":"打开记事本","expected":"记事本窗口出现","tool_hint":"open_app"}]}
"""
