# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.4.0] - 2026-09-10

报告结构收敛为「产品创意 / 用户痛点 / 潜在机会」三个文档（移除趋势洞察，来源不再显示标题、改为可点击链接）；报告页改为三级导航；修复 favicon 与悬浮组调色板问题。

### 变更

- **分析类别重组为三类**：`ideas`（产品创意）、`pain`（用户痛点）、`indie`（潜在机会）；移除「趋势洞察」。报告内仍按分类（H3）分组整理；来源条目改为不显示标题的可点击链接（`[来源](url)`）。
- **公开页改侧边栏布局**：品牌区（logo +「拾贝」+ slogan）与树状导航（日期可折叠展开 → 文档 → 分类）收进左侧固定侧边栏（窄屏为顶部区域），右侧为报告正文，左下角回到顶部悬浮按钮。移除页标题、「每日报告 / 全量总览」tab 与页内「管理」入口（管理页由 `/admin` URL 直接进入）。
- **报告标题改为日期**：正文首行由「拾贝 · 多来源分析」改为生成日期（如 `# 2026-09-09`）；一级标题为文档（产品创意 / 用户痛点 / 潜在机会），二级标题为分类。
- **生成逻辑省 token**：批次分析从「每批 × 每类各调一次」改为「每批一次输出全部类别」（帖子正文只发一次），合并与分类分组合并为每类一次调用，`BATCH_SIZE` 15→20；输入 token 约降 2/3、调用次数约降 60%+，并保留按类回退路径。

### 修复

- **favicon 在 SPA 深链下不显示**：`index.html` 用 `./favicon.ico` 相对路径，在 `/reports/<日期>` 等深链下会请求 `/reports/favicon.ico`（落 SPA 回退返回 HTML，浏览器拿不到图标）；改为根绝对路径，由 Vite 按部署 base 重写。
- **悬浮组调色板「点开即灭」无法选色**：鼠标移出组时 `relatedTarget` 为 null（触屏、窗口失焦、快速移动）会立即收起气泡；气泡打开期间不再因移出收起，仅点色块 / 再点调色板 / 点外部 / Esc 关闭。

## [0.3.0] - 2026-09-09

报告按日归档与按日导航、favicon 服务、抓取超时收敛；默认停用 Hacker News 来源。

### 新增

- **每日报告归档**：增量报告从覆盖式 `analysis_today.md` 改为按日归档 `data/analysis/YYYY-MM-DD.md`（每天一份、同日多次运行刷新），历史可回溯。
- **报告页按日导航**：Web 报告页新增「每日报告」视图——默认定位最新一天，支持 ◀▶ 逐日与日期胶囊切换；「全量总览」为独立 tab。API 报告列表区分 `daily`/`full` 并按日期倒序（`latest_daily` 供默认定位），详情接口白名单校验日期格式。
- **favicon.ico**：16/32/48 多尺寸 favicon（ICO 内嵌 PNG）；新增 `/favicon.ico`、`/favicon.svg` 静态服务路由（此前 svg 从未被 Flask 托管，浏览器一直无图标）。
- **部署参数化补登**：docker-compose / docker/nginx.Dockerfile 前缀参数化（`SHIBEI_BASE_PATH` / `SHIBEI_TAG`，09-08 生产环境已使用）；Dockerfile 与 compose 支持 `PIP_INDEX_URL` 自定义 pip 源（国内主机可用镜像站，如腾讯云）。

### 修复

- **运行历史开始时间错乱（显示 1970-01-22）**：任务时间戳为秒级 epoch，前端按毫秒解析导致；`time.ts` 统一做秒→毫秒归一化。
- 「没有新增帖子」的提示改为指向最近一份每日归档。

### 变更

- **默认停用 Hacker News 来源**（`config.json` `enabled=false`，设置页可随时重新启用）：增量任务曾因 HN 逐条评论串行抓取 + 30s 超时 × 3 重试，单源耗时约 141 分钟（一次增量任务总时长 211m）。
- **抓取超时收敛防黑洞**：全局网络超时 30s → 10s；HN 评论抓取单帖上限 25 条、失败降为重试 1 次；V2EX `max_retries` 降为 1。

## [0.2.0] - 2026-09-07

从「V2EX 单源 CLI」到「多来源 + Web 界面 + Docker 部署」的完整发布。

### 新增

- **多来源接入**（sources/ 新增 5 个实现 + 注册 + config 配置节）
  - Hacker News：Firebase JSON API，列表端点二次请求详情，评论 BFS 递归展平，deleted/dead 跳过。
  - Lobste.rs：JSON API，按标签分页；`submitter_user`/`commenting_user` 为字符串用户名，评论扁平列表。
  - Dev.to (Forem)：JSON API + 自定义 `Accept: application/vnd.forem.api-v1+json`，评论树递归展平。
  - 少数派：RSS 2.0 feed，无评论接口。
  - Product Hunt：RSS feed，无评论接口。
- **base.py 通用助手**：`http_get_json` 支持 `extra_headers`；新增 `http_get_xml` / `parse_atom_feed`（Atom 与 RSS 2.0 兼容）/ `strip_html` / `iso_to_unix`（ISO 8601 与 RFC 2822）。
- **爬取与 CLI 增强**：来源必须出现在 config 且 enabled 才启用；`run_crawl` 来源间并行（`ThreadPoolExecutor`）；进度日志带来源标识；Ctrl+C 优雅退出（原子写 + 断点续传）；分析结论强制中文。
- **Web 界面与 Docker 部署**（`web/` + `frontend/` + Dockerfile + docker-compose + nginx `/shibei/` 子路径反代）
  - 浏览器查看/触发：报告页（全量/今日报告 Markdown 渲染、数据概览）、运行历史（状态 + 实时日志弹窗）、设置页。
  - 主动触发：增量 / 全量分析按钮；analyzer 子进程运行（`web/runner.py`），单任务并发（运行中触发 409），状态索引 + 日志落盘 `data/tasks/`，重启容器自动标中断。
  - 停止任务：运行中任务可随时停止（SIGTERM → `interrupted`，已抓数据保留续传）。
  - 登录保护：scrypt 密码哈希 + 签名会话 cookie；初始账号 `SHIBEI_USERNAME` / `SHIBEI_PASSWORD`。
  - AI 配置：base_url / model / max_tokens / API Key 界面可存（Key 存 `data/web_secrets.json` 0600）；**连通性测试按钮**（一次最小对话，展示服务商错误）。
  - 每日定时调度（`web/scheduler.py`）：**默认每天 00:00 增量分析**，可开关、可设时间（5 分钟步进），同天只触发一次（last_fired 落盘）。
  - Webhook 通知（`web/webhook.py`）：任务完成（成功/失败）时 POST JSON 到配置地址，支持自定义 Header Key + Token，设置页可发测试。
  - 前端（React 18 + Vite + Tailwind，遵循前端约束规范）：5 主题色 × 明暗、中英双语、悬浮控制按钮组（默认折叠）、favicon；时区仅上海/UTC。
  - nginx 配置内嵌镜像（`docker/nginx.Dockerfile`），`SHIBEI_BASE_PATH` 可配置子路径。
- **运行时依赖**：pyproject 声明 flask + waitress（仅 Web 部署需要；CLI 仍零第三方依赖）。

### 修复

- 悬浮按钮组：鼠标移向主题色气泡不再误收起（relatedTarget 判定）；展开/折叠位移 + 透明度动画。
- 报告任务结束状态区分：`interrupted`（停止/中断）不再误报失败。

### 计划（见 [Unreleased]）

## [Unreleased]

- 更多来源：Reddit（OAuth 商用授权）、即刻（逆向）等门槛更高的社区
- 报告增强：分类标签、历史对比、导出其它格式
- list_nodes 增强（SSPai / Product Hunt 无节点概念）

## [0.1.0] - 2026-08-02

初始版本：V2EX 单一来源、命令行工具、多来源可扩展架构。

### 新增

- **爬虫**（crawler.py + sources/）
  - 来源抽象层：`Source` 基类、`http_get_json` 通用助手、`SOURCES` 注册表。
  - V2EX 来源：帖子/回复/节点抓取，归一为统一帖子结构。
  - 今日列表缓存 + 分页去重 + 断点续传（已存在跳过）。
  - 增量爬取（`--today`，按 `last_crawl`）。
  - `crawler.py list` 列节点。
- **分析**（analyzer.py）
  - 单一入口：自动爬取 → 自动分析 → 打印报告绝对路径。
  - 四个分析维度（创意/痛点/独立开发/趋势），批次 × 类别并行，run_id 缓存。
  - 层级合并、`[#id]` 锚点 → 可点击原帖链接还原。
  - 增量 / 全量模式（`--full`）。
  - OpenAI 协议 `call_api`：错误透传、4xx 直报、429/5xx 指数退避重试。
- **配置**：config.json 按来源分节 + `llm` 节；`OPENAI_API_KEY` / `OPENAI_BASE_URL` 必填，无内置默认。
- **工程**：uv、ruff、pyright、pytest（45 用例）、零运行时依赖、MIT 许可。

### 修复
- 无。
