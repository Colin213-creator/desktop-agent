"""急停信号。

继承 BaseException 是故意的：工具执行层的 `except Exception`
不能把它吞成一条错误信息，否则急停就失效了。
"""

from __future__ import annotations


class AgentAborted(BaseException):
    """用户主动中断。只能由急停路径抛出。"""
