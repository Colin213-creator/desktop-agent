# 桌面智能体

用一句自然语言驱动 Windows 完成跨应用任务：拆解步骤、调用工具、看屏幕核对结果、失败重试，
并留下可回放的运行轨迹。

## 它和普通脚本的区别

| 对象 | 差别 |
| --- | --- |
| RPA | RPA 走固定流程；本项目每步看结果再决定下一步 |
| 聊天机器人 | 聊天机器人只回答；本项目真的操作桌面 |
| 普通 GUI 自动化 | 本项目用自然语言入口，能拆任务、能重试、能沉淀经验 |

## 快速开始

```powershell
cd 'E:\智能体大作业   远程桌面共享'
pip install -r requirements.txt
```

检查模型（需要 Ollama 在线，主模型为 `gemma4:31b-cloud`）：

```powershell
python -m desktop_agent --health
```

演练模式（只规划、截图、选动作、验证，**不操作桌面**）：

```powershell
python -m desktop_agent "打开计算器，算一下 1234 乘以 5678"
```

真正执行（会操作鼠标键盘，高危动作会要求确认）：

```powershell
python -m desktop_agent "打开计算器，算一下 1234 乘以 5678" --live
```

启动本地网页（默认演练模式；加 `--live` 才真正执行）：

```powershell
python -m desktop_agent --serve
```

浏览器打开 <http://127.0.0.1:8000>。

## 运行产物

每次运行生成 `runs/<时间戳>/`：

| 文件 | 内容 |
| --- | --- |
| `task.json` | 任务、模型、开始时间 |
| `trace.json` | 每步的工具、参数、风险级别、验证结论、耗时 |
| `shot_*.png` | 每步执行前后的截图 |

## 架构

```
感知  —— 截图 / 活动窗口 / 光标 / 控件树
  ↓
决策  —— Planner / Operator / Verifier / Recoverer
  ↑↓
记忆  —— 轨迹 / 技能库 RAG / SOP 知识库 RAG
  ↓
执行  —— 鼠标键盘 / 启动程序 / 文件读写
  ↓
安全  —— 风险分级 / 人工确认 / 预算 / 脱敏
```

主循环：**规划 → 执行一步 → 截图 → 验证 → 继续 / 重试 / 重规划**。

详见 [架构说明](docs/架构说明.md) 与[设计文档](docs/superpowers/specs/2026-10-28-desktop-agent-design.md)。

## 安全设计

- 动作分三级：只读、界面操作、破坏性。
- 破坏性动作（覆盖已有文件、删除、关机）**执行前**必须确认，确认门包住执行入口。
- 未知工具默认按高危处理。
- 步数、时长、模型调用次数三个硬上限。

## 隐私设计

主模型是云端的，截图会上传。因此：

- 默认只截活动窗口（`PrivacyPolicy.window_only`）。
- 上传前对密码框、证件、通知等矩形涂黑（`redact`）。
- 敏感任务可切到本地模型（`route_model` 返回 `local`）。

## 评估

```powershell
python -m eval.run_eval --config multi
```

四组配置：`vision` / `hybrid` / `rag` / `multi`，统计成功率、平均步数、耗时、误判完成率。

## 当前状态

已完成并且有测试覆盖：

- 配置与模型联通、截图与 DPI 换算、预算、轨迹落盘
- 工具注册表（文件/系统/磁盘/端口/鼠标/键盘/程序）、参数校验
- 风险分级与破坏性动作确认门
- 控件树定位、规划器、独立验证器、主循环、四角色路由
- 技能库 RAG、SOP 知识库 RAG、截图脱敏与模型路由
- 本地网页、远程被控端、示范录制、评估统计

尚未接线（独立模块可用，但主循环未自动调用）：

- 截图脱敏已在 `safety/privacy.py` 实现，尚未接入 `capture`
- 远程层是旁路，未与主循环联调
- `--live` 的完整跨应用任务尚未完成端到端验证

已接线：主循环在规划前会检索技能库与 SOP 知识库（`use_rag=True`），
检索失败自动退化为现场规划。

这些缺口在 [实施计划](docs/superpowers/plans/2026-10-28-desktop-agent.md) 的后续任务中收口。

## 测试

```powershell
python -m pytest -q
```

## 目录

```
desktop_agent/     核心代码（core / perception / actions / safety / memory / ui / remote）
tests/             单元测试
eval/              评估任务集与统计脚本
knowledge/demo/    示例 SOP
docs/              设计文档、实施计划、架构说明、演示脚本
runs/              运行产物（不入库）
```
