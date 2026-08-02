# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划
- 更多来源：Hacker News、Reddit、即刻
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
