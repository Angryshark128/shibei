# 拾贝 · 项目状态

## [2026-08-02] 定位明确 + v0.1.0 发布

### 现状
- **定位**：面向独立开发者的社区情报工具（README / design / pyproject 已统一）。
- **环境声明**：README 新增「环境要求」（Python 3.10+ 零运行时依赖 / uv 仅开发 / 网络与 LLM 配置要求）。
- **已发布**：GitHub 仓库 `Angryshark128/shibei`（Public），main 分支已推送，tag `v0.1.0`。
- 注：本环境 github.com HTTPS 不通，push 走 SSH over 443（`ssh.github.com:443`）。
- 45 测试 / ruff / pyright 全绿；pre-commit 钩子全过。

## [2026-08-02] 开源标准完善

### 现状
- **设计文档重写**：docs/design.md 已按当前实现完全对齐（单一入口、run_crawl、URL/Key 必填、max_tokens、错误透传、[#id] 锚点链接还原）。
- **开源标准文件**：LICENSE(MIT)、README 重写（特性/快速开始/配置/扩展/路线图）、CONTRIBUTING.md、CHANGELOG.md。
- **工程配置**：pyproject 元数据（license/classifiers/URLs）、.pre-commit-config.yaml（local 钩子：ruff/pyright/pytest，离线可用）、.editorconfig、.github（CI + issue/PR 模板）。
- **已 git init 并提交基线**：27 个文件入库。
- 注意：pyproject `[project.urls]` 用 `<your-org>` 占位，发布前替换为真实仓库地址；README 徽章同理。
- 注意：V2EX API 大量爬取后可能临时 403/不可达（限流 ~600 次/小时），需等待重置。

### 计划
1. Docker 部署。
2. 更多来源接入。
3. 发布到真实 GitHub 仓库（替换占位 URL）。

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
