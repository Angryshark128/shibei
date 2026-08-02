# 拾贝 · 设计文档

> 从社区抓取帖子，调用 LLM 提炼创意、痛点、独立开发者机会、趋势洞察。
> 当前接入 V2EX，架构按多来源可扩展设计。本文档与当前代码实现保持一致。

---

## 1. 项目概览

**用途**：抓取社区论坛指定节点下的帖子及回复，存为本地 JSON，再调用 LLM 提炼四类洞察，输出 Markdown 报告。

**运行方式**：`analyzer.py` 是**单一分析入口**——自动爬取所需数据 → 自动分析 → 打印报告绝对路径，用户无需手动干预是否爬取。

**语言与技术**：Python 3.10+，零第三方运行时依赖（标准库 `urllib`），可用 uv 管理。Docker 镜像可选。

**核心原则**：

- **来源可插拔**：新增社区 = 新增一个来源实现 + 注册 + 配置节，主流程与分析模块不动。
- **数据结构统一**：所有来源输出同一结构的帖子 JSON，分析模块不感知来源差异。
- **LLM 只支持 OpenAI 协议**：`POST {base_url}/chat/completions`，兼容 DeepSeek、OpenRouter、Ollama、vLLM 等。URL 与 Key 均由用户自带。
- **单一入口**：`analyzer.py` 自动决定是否爬取（有数据→增量，无数据→全量），报告写入后打印绝对路径。

---

## 2. 项目结构

```
.
├── config.json          # 来源列表 + 爬取参数 + LLM 配置
├── analyzer.py          # 单一入口：自动爬取 → 分析 → 报告
├── crawler.py           # 爬虫（独立工具 + run_crawl 复用）
├── models.py            # 统一数据结构 Post/Reply
├── sources/             # 来源抽象层
│   ├── __init__.py      # 来源注册表 SOURCES
│   ├── base.py          # Source 抽象基类 + http_get_json 通用助手
│   └── v2ex.py          # V2EX 来源实现
├── data/                # 运行时数据（gitignored，不入库）
│   ├── state.json       # 运行状态（按来源记录时间戳）
│   ├── analysis/        # 分析报告（analysis.md / analysis_today.md）
│   ├── .cache/          # 中间缓存
│   └── v2ex/{node}/{id}.json   # 每个来源一个子目录
├── tests/               # pytest 测试
├── pyproject.toml       # uv 工程配置（零运行时依赖）
└── README.md
```

关键约定：

- `data/{source_id}/{node}/{id}.json` —— 三层结构：来源 → 节点 → 帖子。多来源不撞名，便于单独删某来源数据。
- `state.json` 按来源记录 `last_crawl` / `last_analysis`，各来源独立增量。
- 缓存全放 `data/.cache/` 下，按来源 / run_id 区分。
- 所有数据与缓存不入 git 仓库。

---

## 3. 配置文件

### 3.1 config.json 结构

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

设计要点：

- **按来源分节**：节点、页数、请求延迟、重试次数都属于来源自身特征，不同社区节点体系与限流策略不同。
- `request_delay` / `max_retries` 由爬虫按来源读取并使用，分析模块不读。
- 新增来源只需在 `sources` 加一节 + 注册实现类。
- 所有硬编码参数抽象到配置文件。

### 3.2 环境变量与 LLM 配置（用户自带 URL + Key）

| 变量 | 必填 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 是 | LLM API Key（仅环境变量，不入库） |
| `OPENAI_BASE_URL` | 是 | OpenAI 兼容 API 地址（环境变量或 config.json `llm.base_url` 二选一） |
| `ANALYZE_MODEL` | 否 | 模型名（config.json `llm.model` → 默认 `gpt-4o-mini`） |
| `ANALYZE_MAX_TOKENS` | 否 | 单次输出上限（config.json `llm.max_tokens` → 默认 `4096`；个别厂商上限更低需调小） |

设计要点：

- **优先级：环境变量 > config.json > 内置默认**（Key/URL 无默认，缺失即退出）。
- **URL 与 Key 均必填**：缺失时打印配置说明并退出，避免用户忘了配 URL 误发到 OpenAI 官方端点。
- API Key 不写入配置文件、不硬编码、不提交仓库。
- 兼容任何 OpenAI 协议的 API：DeepSeek、OpenRouter、Ollama、vLLM 等。

---

## 4. 数据结构

### 4.1 统一帖子 JSON（来源无关）

所有来源的输出最终归一为同一结构：

```json
{
  "id": "1229217",
  "source": "v2ex",
  "node": "programmer",
  "title": "...",
  "content": "...",
  "author": "用户名",
  "created": 1784774167,
  "replies_count": 5,
  "url": "https://www.v2ex.com/t/1229217",
  "reply_list": [
    {
      "id": "123456",
      "author": "回复人",
      "content": "...",
      "created": 1784775000
    }
  ]
}
```

关键约束：

- `id` 统一为**字符串**（不同来源 id 形态不同：V2EX 整数、HN 自增整数、Reddit 字母数字）。
- 字段名来源无关：`member` → `author`，发帖人/回复人统一为 `author`。
- `source` 标记来源，`node` 标记来源内节点。
- `content` 与 `reply.content` 都可能为空字符串（V2EX API 实际行为），`post_from_dict` 对缺失/`null` 字段做空值兜底。
- `reply_list` 最多存 10 条回复（控制文件大小与分析 token）。
- `replies_count` 是原始回复总数，不等于 `len(reply_list)`。
- `created` 是 unix timestamp，用于增量过滤和排序。

### 4.2 state.json 结构

```json
{
  "v2ex": {
    "last_crawl": 1785299416,
    "last_analysis": 1784793852
  }
}
```

- 按来源各记一份，互不干扰，允许某个来源只爬不分析。
- `last_crawl`：爬虫增量模式过滤此时间之后的帖子；爬完更新。
- `last_analysis`：分析增量模式过滤此时间之后的帖子；分析完更新。
- 两时间戳独立。分析增量兜底逻辑：`last_analysis` 缺失时用 `last_crawl`。

### 4.3 缓存结构

爬虫帖子列表缓存：`data/.cache/topic_lists/{source}_{node}_{YYYY-MM-DD}.json`

- 存 `collect_topics` 的去重后完整返回（帖子列表数组）。
- 同一天内重复运行直接读缓存，不重复请求 API。
- 校验条件：缓存条数 ≥ `pages_per_node × 5`（确保覆盖足够；不满足则重抓）。

分析中间缓存：`data/.cache/{run_id}_b{batch_idx}_{key}.json`

- `run_id = md5(所有帖子ID拼接).hexdigest()[:12]`，同一批帖子复用同一缓存。
- `key` 为分类 key（`ideas`/`pain`/`indie`/`trend`）。
- 存 `{"key": "...", "result": "LLM 原始返回文本"}`。
- **分析完成后清除**（`cleanup_cache`），用于中断恢复而非跨次复用。

---

## 5. 来源抽象层（sources/）

### 5.1 Source 抽象基类（base.py）

```python
class Source(ABC):
    name: str  # 唯一标识，如 "v2ex"，也是 data/{name} 目录名
    display_name: str  # 显示名，如 "V2EX"

    def __init__(self, *, request_delay=1.2, max_retries=3): ...

    @abstractmethod
    def fetch_topics(self, node: str, page: int) -> list[Post]:
        """抓取某节点第 page 页的帖子元数据（统一结构，不含 reply_list）。"""

    @abstractmethod
    def fetch_replies(self, topic_id: str) -> list[Reply]:
        """抓取某帖子的回复列表（统一结构）。"""

    def list_nodes(self) -> list[dict]: ...
```

- 主循环（crawler.py）只依赖这三个方法 + 来源配置，不感知具体社区。
- `request_delay` / `max_retries` 挂在来源实例上，抓取时直接使用。
- 通用 HTTP 助手 `http_get_json(url, *, timeout, retries, delay)` 在 base.py，各来源复用：
  - 设置 User-Agent（`ShiBei-Crawler/1.0`）、超时 30 秒。
  - 指数退避重试：`delay * 2^attempt`，上限 60 秒。
  - **HTTP 404/403 直接返回 `[]`，不重试**（帖子被删/权限不足/限流）。
  - 其他错误重试到 `max_retries` 次；全部失败返回 `[]`，不抛异常。
  - 用标准库 `urllib.request`，零第三方依赖。

### 5.2 来源注册表（__init__.py）

```python
SOURCES = {
    "v2ex": V2EXSource,
    # 未来: "hackernews": HNSource, "reddit": RedditSource, ...
}
```

### 5.3 V2EX 实现（v2ex.py）

- `name="v2ex"`，API 根路径 `https://www.v2ex.com/api`，v1 API 无需认证。
- 端点：帖子列表 `topics/show.json?node_name={node}&p={page}`；回复 `replies/show.json?topic_id={id}`；节点列表 `nodes/all.json`。
- 映射：`member.username` → `author`，`replies` → `replies_count`，`node.name` → `node`，`id` 转字符串。
- 对 API 返回做防御：非 list / 非 dict 条目直接跳过。

### 5.4 新增来源三步

1. 新建 `sources/{name}.py`，继承 `Source` 实现 `fetch_topics` / `fetch_replies` / `list_nodes`。
2. 在 `sources/__init__.py` 的 `SOURCES` 注册。
3. 在 config.json `sources` 加一节（enabled / nodes / pages_per_node 等）。

---

## 6. 爬虫模块（crawler.py）

### 6.1 collect_topics（帖子列表抓取）

`collect_topics(source, node, pages)` —— 分页、去重、缓存逻辑在 crawler 中实现，跨来源一致；来源实现只负责单页原始抓取。

1. 先检查今日缓存 `data/.cache/topic_lists/{source}_{node}_{today}.json`。
2. 存在且条数 ≥ `pages × 5` → 直接返回缓存。
3. 否则逐页调用 `source.fetch_topics(node, p)`，用 dict 以 id 去重（分页可能返回重复）。
4. 每页间 `sleep(source.request_delay)`。
5. 按 `created` 降序排序，写回缓存，返回统一 Post 列表（无 reply_list）。

### 6.2 crawl（单来源主循环）

`crawl(source, nodes, pages, since=None)`：

1. 对每个节点创建输出目录 `data/{source.name}/{node}/`。
2. `collect_topics` 获取帖子列表；`since` 传入时过滤 `created >= since`。
3. 遍历帖子：本地已存在对应 JSON → 跳过（断点续传，不重复请求）；否则 `fetch_replies` → `save_topic`（`reply_list` 只存前 10 条）。
4. 打印进度：`[i/总数] id - 标题`。
5. 返回新增帖数。

### 6.3 run_crawl（可复用编排）

`run_crawl(config, source_name=None, today=False)` —— 供 CLI 与 analyzer 复用：

- `today=True`：按 state 的 `last_crawl` 增量爬取并更新 `last_crawl`。
- `today=False`：全量爬取、不更新时间戳。
- 遍历所有 enabled 来源；**单来源失败不影响其他来源**（try/except 包裹）。

### 6.4 CLI

```
python3 crawler.py                   # 全量爬取所有 enabled 来源
python3 crawler.py --source v2ex     # 只爬指定来源
python3 crawler.py --today           # 增量爬取
python3 crawler.py list [关键词]      # 列出节点
```

crawler.py 是**可选独立工具**（手动爬取 / 调试 / 列节点），不是分析的前置步骤。

---

## 7. 分析模块（analyzer.py）

### 7.1 分类体系

四个分析维度，每个维度独立分析 + 独立合并：

| key | 标题 | 定义 |
|---|---|---|
| `ideas` | 好的创意/产品点子 | 帖子中提到或暗示的有价值的想法、工具需求、产品方向 |
| `pain` | 用户痛点 | 用户反复抱怨、求助、表达不满的问题 |
| `indie` | 个人开发者机会 | 对独立开发者/小团队友好的方向，侧重低门槛、可快速验证 |
| `trend` | 趋势洞察 | 社区关注的技术趋势或话题走向 |

### 7.2 Prompt 设计

单批次分析 prompt（每批只分析一个类别，不混合）：

```
分析以下社区帖子，只提炼「{title}」类信息。

定义：{desc}

要求：
- 只输出这一类，不要输出其他类别
- 不要限制条数，尽可能多地提炼有价值的信息
- 每条用 `[#帖子ID]` 标注来源帖子，ID 必须与上文的帖子标注完全一致，不得改写
- 用中文回答

---（第 {idx+1}/{total} 批）

{帖子文本}
```

帖子文本格式（`format_post`）：

```
## [#{id}] {标题}
来源: {source} | 节点: {node} | 作者: {author} | 回复数: {N}
{正文前 500 字符}
  - {回复人}: {回复内容前 200 字符}
---
```

- 正文截断 500 字符，每帖最多 10 条回复，每条回复截断 200 字符。
- **每帖用 `[#{id}]` 做稳定锚点**：与 LLM 输出格式、链接还原正则三者一致。
- **URL 不注入 prompt**——最终输出由代码还原为可点击链接，避免 LLM 杜撰/截断 URL。

合并 prompt：要求去重、保留 `[#帖子ID]` 标注、按价值排序、中文回答；增量模式注明「今日新增分析」。

### 7.3 analyze 流程

`analyze(topics, incremental=False)` → `{类别标题: 合并后文本}`：

- 参数：`BATCH_SIZE = 15`（每批 15 帖），`MERGE_SIZE = 3`（每 3 个结果合并一次），并发 `max_workers = 4`。
- 计算 `run_id`，`id2link` 映射（id → title,url）。
- 分批，每个「批次 × 类别」并行调 LLM，带 run_id 缓存（命中直接用）。
- 按类别独立**层级合并**：N ≤ 3 一次合并；N > 3 每 3 个一组合并、递归到剩 1 个；合并 timeout=300。
- **链接还原**（代码层、确定性）：正则 `\[#([^\]]+)\]` 把锚点替换为 `[帖子标题](原帖URL)`，URL 取自帖子 JSON，不经过 LLM；未知 ID 保留原文并告警。
- `cleanup_cache(run_id)` 清理本次缓存。

### 7.4 call_api（OpenAI 协议调用）

- `POST {base_url}/chat/completions`，Body `{"model", "messages", "temperature": 0.3, "max_tokens"}`，Header `Authorization: Bearer {key}`。
- 超时：单次分析 120 秒，合并 300 秒。
- 重试：指数退避 `5 * 2^attempt`，上限 60 秒。
- **错误透传**：`_http_error_detail` 解析服务端 `{"error": {"message"}}`；**4xx（除 429）立即报原因终止**（如 `model not found`），不空重试；429/5xx/网络错误重试后仍失败则 raise。

### 7.5 报告

- 报告格式：标题「拾贝 · 多来源分析」+ 来源摘要 + 帖子数 + 四个分类小节。
- 每条来源是**可点击链接** `[帖子标题](原帖URL)`（代码还原，见 7.3）。
- 写入 `data/analysis/analysis.md`（全量）或 `analysis_today.md`（增量），结束**打印绝对路径**。

### 7.6 CLI（单一入口）

```
python3 analyzer.py          # 默认：自动增量爬取 + 增量分析（数据为空时自动全量）
python3 analyzer.py --full   # 强制全量：自动爬取 + 重分析全部帖子
```

环境变量检查：`OPENAI_API_KEY` 缺失 → `exit(1)` 并打印配置说明（含 URL 必填提示）。

---

## 8. 单一入口流程与每日工作流

### 8.1 单一入口逻辑

`main()` 流程：

1. 校验 `OPENAI_API_KEY`（缺失退出）；解析 LLM 配置（URL 缺失退出）。
2. **自动爬取**：若 enabled 来源下无任何帖子数据（首次运行或数据被清空），重置这些来源的 state（使增量退化为全量）；随后调用 `crawler.run_crawl(config, today=True)`。
3. 加载待分析帖子：默认增量（按来源取 `last_analysis` 或 `last_crawl` 作 since）；`--full` 时 since=None。
4. `analyze` → 写报告 → 打印绝对路径 → 按来源更新 `last_analysis`。

### 8.2 状态流转

```
首次运行 / 数据为空:
  自动检测无数据 → 重置该来源 state → run_crawl(today=True) 退化为全量（since=None）→ 写 last_crawl
  分析 since=None → 全量分析 → 写 last_analysis

日常运行:
  run_crawl(today=True) → 增量爬取（since=last_crawl）→ 更新 last_crawl
  分析增量（since=last_analysis）→ 更新 last_analysis
```

边界情况：

- 无新增帖子：打印「没有新增帖子，无需分析」并给出最近一次报告的绝对路径（若有）。
- 无数据且爬取未获取到：提示可能是来源 API 限流/暂时不可用（如 V2EX 403），稍后重试。
- 只有 `last_crawl` 没有 `last_analysis`：分析时兜底用 `last_crawl`。

### 8.3 每日用法

每天跑一条命令即可：

```bash
export OPENAI_API_KEY=sk-xxx
uv run python analyzer.py
```

无需手动先爬取。

---

## 9. 关键边界情况 & 健壮性

### 9.1 API 限流

- V2EX v1 API 限制约 600 次/小时/IP；`request_delay` 按来源配置（默认 1.2 秒）。
- 爬虫遇到 403/404 直接返回 `[]` 不重试；单来源失败不影响其他来源。
- 分析 4xx 直报原因，429/5xx 指数退避重试。

### 9.2 去重与幂等

- `collect_topics` 按 id 去重（分页可能返回重复）。
- 主循环检查本地文件是否存在，已存在跳过（断点续传）。
- 分析结果按 run_id 缓存，中断可恢复；完成后清理。

### 9.3 大帖子分析

- 每批 15 帖，超过自动分多批；正文/回复截断控制 token。
- 多批次层级合并，避免单次 prompt 过大。

### 9.4 错误处理

- 爬虫 API 失败返回 `[]`，不抛异常、不中断流程。
- 分析重试后仍失败则 raise 终止（附服务端原因）。
- 环境变量缺失 exit(1)，打印配置说明。
- 数据文件损坏跳过（`load_topics` 捕获 JSON 解析错误）。

### 9.5 目录创建

- 所有 `os.makedirs` 带 `exist_ok=True`；输出目录不存在时自动创建。

---

## 10. 工程与开源规范

- **零运行时依赖**：crawler / analyzer / sources 只用标准库 `urllib`。
- **工具链**：uv（依赖管理）、ruff（format + lint）、pyright（类型检查）、pytest（测试，`pythonpath=["."]`）、pre-commit。
- **代码规范**：`~/.claude/docs/python-project.md`，单行 ≤ 120 字符。
- **测试**：`tests/` 覆盖模型、来源归一化、爬虫缓存/去重/增量、分析 prompt/合并/链接还原/缓存、CLI 编排；mock `http_get_json` / `call_api`，不依赖真实网络与 LLM。
- **文档**：README / docs/design.md / .claude/（STATUS/DECISIONS/CONSTITUTION）。

---

## 11. 实现状态与路线图

### 已实现

- P0：来源抽象层（base/v2ex/注册表）、统一数据结构、crawler 主循环。
- P1：analyzer 4 分类分析、增量模式、run_id 缓存、层级合并、链接还原、`--full`。
- 单一入口（analyzer 自动爬取 + 分析 + 打印绝对路径）；LLM URL/Key 必填；错误透传。

### 路线图

- 新来源接入：Hacker News、Reddit、即刻等。
- Docker 镜像与 cron 定时部署。
- 报告增强：分类标签、历史对比、导出其它格式。
- 节点/来源的交互式浏览。
