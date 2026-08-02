# 拾贝 · 项目状态

## [2026-08-01] analyzer 改为单一入口（自动爬取）

### 现状
- **P0 / P1 已完成**：来源抽象层、统一数据结构、crawler.py、analyzer.py（4 分类分析 + 链接还原 + run_id 缓存 + 层级合并）。
- **单一入口**：`analyzer.py` 一个命令完成「自动爬取 → 自动分析 → 打印报告绝对路径」。数据为空时自动全量；`--full` 强制全量；`crawler.py` 降级为可选独立工具。
- **URL 与 Key 均必填**：`OPENAI_BASE_URL`（env 或 config）缺失即退出，无 OpenAI 兜底。
- **LLM 错误透传**：4xx 立即报服务端原因（如 model not found），不空重试；`max_tokens` 可配置。
- 45 个单元测试通过，ruff / pyright 全绿。
- 技术栈：Python 3.10 / uv / 零运行时依赖（stdlib urllib）。
- 注意：大量爬取后 V2EX API 可能临时 403/不可达（限流 ~600 次/小时），需等待重置。

### 计划
1. P3：Docker 部署。

### 计划
1. P2：分析侧缓存与层级合并已在 P1 内实现；剩余可选优化。
2. P3：Docker 部署。

### 待办
- [x] 重写 design.md，落实多来源抽象 — P0
- [x] crawler.py 基础抓取 — P0
- [x] 帖子 JSON 统一数据结构 — P0
- [x] 来源抽象层（base/v2ex/注册表）— P0
- [x] analyzer.py 单批次分析（4 分类 + prompt + 链接还原）— P1
- [x] 增量模式（分析侧 since 过滤 + last_analysis 更新）— P1
- [x] 分析侧 run_id 缓存 + 层级合并 — P2（顺带完成）
- [ ] Docker 部署 — P3
- [ ] list_nodes / 节点浏览增强 — P4
