# 拾贝

从社区论坛抓取帖子，调用 LLM 提炼**创意 / 痛点 / 独立开发者机会 / 趋势洞察**，输出带可点击原帖链接的 Markdown 报告。

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Dependencies](https://img.shields.io/badge/runtime%20deps-0-brightgreen)

## 特性

- **单一入口**：`analyzer.py` 一个命令自动完成「爬取 → 分析 → 打印报告绝对路径」，无需手动干预是否爬取。
- **自动增量 / 全量**：有数据时只抓新增、只分析新增；首次运行或数据为空时自动全量。
- **来源可插拔**：新增社区只需实现一个来源类并注册，主流程与分析模块不动。
- **零运行时依赖**：只用标准库 `urllib`，开箱即跑。
- **LLM 自带 URL + Key**：只支持 OpenAI 协议（DeepSeek / OpenRouter / Ollama / vLLM 等均兼容），URL 与 Key 缺失即退出，不误发到官方端点。
- **可点击来源**：报告每条洞察的「来源帖子」是代码还原的真实原帖链接，不经过 LLM，杜绝杜撰 URL。
- **省成本**：今日列表缓存 + 分析 run_id 缓存，重跑不重复请求；正文/回复截断控制 token。

## 工作原理

```
V2EX (或其他社区) ──爬取──▶ data/{source}/{node}/{id}.json ──分析──▶ LLM 提炼 4 类洞察
                                                                        │
                                                                        ▼
                                                   data/analysis/analysis.md（可点击原帖链接）
```

1. 爬虫抓取帖子与回复，归一为统一 JSON 结构。
2. 分析模块按 4 个维度（创意/痛点/独立开发/趋势）分批并行调 LLM。
3. 层级合并去重 → 代码还原来源链接 → 输出报告并打印绝对路径。

## 快速开始

```bash
# 1. 安装（零运行时依赖，仅 dev 工具）
uv sync

# 2. 配置 LLM（用户自带 URL + Key）
export OPENAI_API_KEY=sk-xxx
# 可选：OPENAI_BASE_URL 默认取 config.json 的 llm.base_url

# 3. 分析（唯一入口：自动爬取 + 分析 + 打印报告路径）
uv run python analyzer.py

# 强制全量重分析
uv run python analyzer.py --full
```

首次运行会自动全量爬取并全量分析；之后每天跑一条 `analyzer.py` 即可。

## 配置

### config.json

```json
{
  "sources": {
    "v2ex": {
      "enabled": true,
      "nodes": ["programmer", "python"],
      "pages_per_node": 6,
      "request_delay": 1.2,
      "max_retries": 3
    }
  },
  "llm": {
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-v4-flash",
    "max_tokens": 4096
  }
}
```

| 配置项 | 说明 |
|---|---|
| `sources.{来源}.nodes` | 要爬的节点列表（V2EX 节点见 `uv run python crawler.py list`） |
| `sources.{来源}.pages_per_node` | 每个节点往后翻几页 |
| `sources.{来源}.request_delay` | 请求间隔（秒），控制限流 |
| `sources.{来源}.max_retries` | 请求失败重试次数 |
| `llm.base_url` | OpenAI 兼容 API 地址 |
| `llm.model` / `llm.max_tokens` | 模型名 / 单次输出上限 |

### 环境变量（优先级：环境变量 > config.json）

| 变量 | 必填 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | LLM API Key，仅环境变量，不入库 |
| `OPENAI_BASE_URL` | ✅ | API 地址（或用 config.json 的 `llm.base_url`） |
| `ANALYZE_MODEL` | | 模型名（默认取 `llm.model`，兜底 `gpt-4o-mini`） |
| `ANALYZE_MAX_TOKENS` | | 单次输出上限（默认取 `llm.max_tokens`，兜底 4096） |

## 数据与报告

```
data/
├── state.json                 # 各来源 last_crawl / last_analysis
├── analysis/
│   ├── analysis.md            # 全量报告
│   └── analysis_today.md      # 增量报告
├── .cache/                    # 列表缓存 + 分析缓存（分析后自动清理）
└── v2ex/{node}/{id}.json      # 统一结构帖子
```

报告示例（每条来源均可点击跳回原帖）：

```markdown
# 拾贝 · 多来源分析

来源: v2ex(programmer, python)

基于 1234 个帖子自动生成

## 好的创意/产品点子

- {创意描述} — [帖子标题](https://www.v2ex.com/t/1229217)
```

## 多来源扩展

新增社区只需三步（详见 `docs/design.md` §5.4）：

1. 新建 `sources/{name}.py`，继承 `Source` 实现 `fetch_topics` / `fetch_replies` / `list_nodes`。
2. 在 `sources/__init__.py` 注册。
3. 在 config.json 加一节来源配置。

## 命令行参考

```
# analyzer.py（单一入口）
uv run python analyzer.py               # 自动增量爬取 + 增量分析（空数据自动全量）
uv run python analyzer.py --full        # 强制全量

# crawler.py（可选独立工具）
uv run python crawler.py                # 全量爬取
uv run python crawler.py --today        # 增量爬取
uv run python crawler.py list [关键词]   # 列出可用节点
```

## 开发

```bash
uv run ruff format .
uv run ruff check .
uv run pyright .
uv run pytest
uv run pre-commit run --all-files        # 见 .pre-commit-config.yaml
```

## 路线图

- [ ] 更多来源：Hacker News、Reddit、即刻
- [ ] Docker 镜像与 cron 定时部署
- [ ] 报告增强：分类标签、历史对比、导出其它格式

## 贡献

欢迎提交 issue 与 PR，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可

[MIT](LICENSE)
