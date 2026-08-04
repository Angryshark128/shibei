# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- **多来源接入**（sources/ 新增 5 个实现 + 注册 + config 配置节）
  - Hacker News：Firebase JSON API，列表端点二次请求详情，评论 BFS 递归展平，deleted/dead 跳过。
  - Lobste.rs：JSON API，按标签分页；`submitter_user`/`commenting_user` 为字符串用户名，评论扁平列表。
  - Dev.to (Forem)：JSON API + 自定义 `Accept: application/vnd.forem.api-v1+json`，评论树递归展平。
  - 少数派：RSS 2.0 feed，无评论接口。
  - Product Hunt：RSS feed，无评论接口。
- **base.py 通用助手**：`http_get_json` 支持 `extra_headers`；新增 `http_get_xml` / `parse_atom_feed`（Atom 与 RSS 2.0 兼容）/ `strip_html` / `iso_to_unix`（ISO 8601 与 RFC 2822）。
- **行为调整**：`get_sources` 改为来源必须出现在 config 配置节且 `enabled: true` 才启用（缺失配置节不再默认启用）。
- **并行爬取**：`run_crawl` 的来源间并行（`ThreadPoolExecutor`）。不同来源限流互不影响，`request_delay` 各自保护；state 写入加锁防丢键。分析本就并发（批次 × 类别，`max_workers=4`）。
- **爬取日志带来源标识**：进度行 `[v2ex 10/10] id - title`，并行下可区分来源。
- **Ctrl+C 优雅退出**：`os._exit(130)` 立即结束并打印提示，不再抛 traceback / 等待工作线程；帖子与列表缓存改原子写，中断不产生损坏文件，下次运行自动断点续传。
- **分析结论强制中文**：批次 / 合并 prompt 规则强化为「一律用中文回答；即使原文是英文，也要用中文输出」（英文源接入后保证报告仍为中文）。

### 计划
- 更多来源：Reddit（OAuth 商用授权）、即刻（逆向）等门槛更高的社区
- Docker 镜像与 cron 定时部署
- 报告增强：分类标签、历史对比、导出其它格式

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
