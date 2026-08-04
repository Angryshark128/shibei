# 拾贝 · 项目状态

## [2026-08-03] 多来源接入（5 个新来源）

### 现状
- **新增来源**：Hacker News、Lobste.rs、Dev.to (Forem)、少数派 (SSPai)、Product Hunt 已实现并在 `sources/__init__.py` 注册，config.json 增加对应配置节（均 enabled）。
- **通用助手**：base.py 新增 `http_get_xml` / `parse_atom_feed`（Atom 与 RSS 2.0 兼容）/ `strip_html` / `iso_to_unix`（ISO 8601 与 RFC 2822）；`http_get_json` 支持 `extra_headers`（Dev.to 用 Forem header）。
- **按真实 API 适配**（指南与实测不符处）：
  - Lobste.rs 的 `submitter_user` / `commenting_user` 是**字符串用户名**而非对象；评论为扁平列表（children 多为 null），`comment_plain` 优先于 `comment`(HTML)。
  - 少数派 feed 实为 **RSS 2.0**（指南称 Atom），`pubDate` 为 RFC 2822 → `iso_to_unix` 同时支持两种格式。
  - Dev.to 评论 id 字段为 `id_code`（非 `id`），且带 `children` 嵌套。
  - Product Hunt 未实测（尊重用户拒绝），解析器兼容 Atom / RSS 2.0 两种形态。
- **行为调整**：`get_sources` 改为来源必须出现在 config 配置节且 `enabled: true` 才启用（此前缺失配置节默认启用，多来源后是隐患）。详见 DECISIONS。
- **测试**：101 用例全绿（新增 56 个：base 助手 + 5 来源归一化/分页/回复展平），ruff / pyright 全绿。
- 注：lobsters 配置节点比指南多加了 `hottest`（热门首页，代码本就支持该路径）。

### 计划
1. 更多来源：Reddit（OAuth）、即刻（逆向）等。
2. Docker 部署。

### 待办
- [x] 多来源接入（HN / Lobste.rs / Dev.to / 少数派 / Product Hunt）— P0
- [x] base.py 通用助手（extra_headers / RSS 解析 / HTML 去标签 / 时间戳）— P0
- [ ] Docker 部署 — P3
- [ ] list_nodes 增强（SSPai / Product Hunt 无节点概念）— P4

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
