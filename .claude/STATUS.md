# 拾贝 · 项目状态

## [2026-09-07] Web 界面 + Docker 部署

### 现状
- **Web 后端**（`web/app.py` + `web/runner.py`，Flask + waitress）
  - 登录保护：scrypt 密码哈希 + 签名会话 cookie（path 随 `SHIBEI_BASE_PATH`）；初始账号 `SHIBEI_USERNAME` / `SHIBEI_PASSWORD`，未设密码自动生成打印日志。
  - AI 配置：base_url / model / max_tokens 落 `data/web_config.json` 并同步仓库 `config.json`（CLI 与 Web 一致）；API Key 存 `data/web_secrets.json`（0600）不进仓库。
  - 来源开关（PUT /api/sources/{name}）、改密、`/api/reports|tasks|run` 等接口。
  - 任务运行：analyzer 子进程，单任务并发（运行中触发 409），状态索引 + 日志落 `data/tasks/`，重启容器标 interrupted。
  - CSRF：JSON 写接口校验 Origin hostname（nginx `$host` 无端口，勿用 netloc 全等比较）。
- **前端**（`frontend/`，React 18 + Vite + Tailwind，遵循 Trilium 前端约束规范）
  - 页面：登录（居中卡片）/ 报告（概览统计 + 全量/今日报告 + 增量/全量触发 + 运行 banner）/ 运行历史（表格 + 日志 Modal）/ 设置（AI/来源开关/改密/时区）/ 帮助。
  - 令牌体系：5 主题色（indigo 默认）× 明暗双轴，CSS 变量 RGB 通道 + `<alpha-value>`；悬浮控制按钮组（默认折叠，hover 展开）；中英双语 i18n；dayjs 6 时区。
  - 构建：`VITE_BASE=/shibei/` 产物进镜像；tsc 全绿、vite build 通过。
- **部署**：Dockerfile（node 多阶段 → python:3.12-slim）+ docker-compose（web + nginx 反代 `/shibei/`）；nginx 配置**内嵌镜像**（docker/nginx.Dockerfile）——本机 daemon 对 `/home/shark` 下单文件 bind 挂载异常（文件被当目录），改 COPY 规避。
- **质量**：ruff / pyright 0 错；pytest 108 全绿（web 冒烟另用 API 脚本 15 项 + docker 内 e2e：子路径页面/静态/登录/cookie path/配置/报告/任务 409/真实 analyzer 子进程日志均过）。
- 注：uv.lock 已含 flask/waitress（pyproject dependencies 更新）；config.json 的运行时同步由 `data/web_config.json` 驱动（本地直接跑 web 会改仓库 config.json → 用后 git checkout 还原）。

### 计划
1. 更多来源：Reddit（OAuth）、即刻（逆向）等。
2. cron 定时部署（Web 触发已就绪）。

### 待办
- [x] Docker 镜像 + Web 界面（查看/触发/配置/登录/子路径）— P0
- [ ] 生产部署（目标机 `docker compose up -d --build` + 外层 HTTPS）
- [ ] list_nodes 增强（SSPai / Product Hunt 无节点概念）— P4
- [ ] 报告增强：分类标签、历史对比、导出其它格式 — P2
- [ ] v0.2.0 发布（README/CHANGELOG 已更新待 tag）

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
