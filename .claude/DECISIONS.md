# 拾贝 · 决策记录

## [2026-08-02] 模型名改为必填（去掉 gpt-4o-mini 兜底）

**背景**  
`ANALYZE_MODEL` 原为可选、兜底 `gpt-4o-mini`。但用户用的是第三方厂商，`gpt-4o-mini` 在该厂商不存在，导致 400 `model not found`。模型名与 URL 一样属于「用户自带」，不同厂商各不相同，不该有内置默认。

**决策**  
`ANALYZE_MODEL` 必填（环境变量或 config.json `llm.model` 二选一），缺失即退出并提示。去掉 `gpt-4o-mini` 内置兜底。`max_tokens` 仍可选（兜底 4096）。

**理由**  
与「用户自带 URL + Key」一致；避免用户忘了配模型名而把不存在的模型发给厂商。

**备选方案**  
- 保留 `gpt-4o-mini` 兜底 — 否，对非 OpenAI 用户必然 400，且掩盖真实配置问题。

## [2026-08-01] analyzer 作为唯一入口，自动决定是否爬取

**背景**  
用户要求「只需要一个分析入口，是否需要爬取不应由我主动干预」。原设计要求先跑 `crawler.py` 再跑 `analyzer.py`，用户跑 analyzer 时经常因数据为空而得到「请先运行 crawler.py 抓取」。

**决策**  
`analyzer.py` 成为单一入口：内部先调用 `crawler.run_crawl(config, today=True)` 自动爬取，再分析。数据为空/首次运行时重置该来源 state，使增量爬取与增量分析自动退化为全量。`crawler.py` 保留为可选独立工具（手动爬取 / list 列节点）。报告写入后打印绝对路径。

**理由**  
用户只需一条命令，爬取与否由程序自动判断（有数据→增量，无数据→全量），避免手动两步操作。

**备选方案**  
- 仍保持两步命令，靠文档引导 — 否，用户明确要求单一入口。
- analyzer 每次无条件全量爬+全量分析 — 否，浪费 API 调用，不符合省成本原则。

## [2026-08-01] LLM URL 改为必填

**背景**  
原设计把 `OPENAI_BASE_URL` 设为可选、兜底 OpenAI 官方端点。用户质疑「当前怎么只需设置 key，URL 呢」——与「用户自带 URL + key」的初衷不符，且 key 必填、URL 可选的组合会让人忘了配 URL 而把请求静默发到 OpenAI 官方端点。

**决策**  
URL 与 Key 均必填：`OPENAI_API_KEY`（仅环境变量）与 `OPENAI_BASE_URL`（环境变量或 config.json 的 `llm.base_url` 二选一）缺失即退出。去掉 OpenAI 官方端点的内置兜底。`ANALYZE_MODEL` 仍可选（环境变量 > config.json > 默认 gpt-4o-mini）。

**理由**  
用户自带 URL + key，两者都必须显式提供，避免静默误发到错误端点。

**备选方案**  
- URL 可选、默认 OpenAI 官方 — 否，与「用户自带 URL + key」初衷不符，存在误发风险。

## [2026-08-01] 项目命名：拾贝

**背景**  
项目需要一个正式名称。当前功能是「从社区抓取帖子，再让 LLM 提炼有价值的创意/机会/趋势」，类似在信息流里捡贝壳。

**决策**  
命名为「拾贝」（shi bei）。抓取是捡拾，LLM 提炼是辨贝——从嘈杂社区信息中挑出有价值的内容。

**理由**  
契合产品心智：低成本抓取大量帖子，由 LLM 筛选出「值得捡起来」的洞察。中文名简洁好记。

**备选方案**  
- 直接叫 v2ex-crawler — 否，绑定单一来源，与多来源扩展方向冲突。
- 用英文名 — 否，用户偏好中文命名。

## [2026-08-01] 多来源可扩展架构

**背景**  
当前只支持 V2EX，但后续要接入更多社区（如 Hacker News、Reddit、即刻等）。若把 V2EX 特有的 API 路径写死，扩展时要大改。

**决策**  
引入来源抽象层（sources/ 包）：每个来源实现统一的 Source 接口（fetch_topics / fetch_replies / list_nodes），输出统一结构的帖子 JSON；爬虫主循环与分析模块不感知具体来源。数据目录按 `data/{source_id}/{node}/` 分层，config.json 按来源分节配置。

**理由**  
分析模块只依赖统一数据结构，来源差异被隔离在 sources/ 内。新增来源 = 新增一个实现类 + 配置节，不动主流程。

**备选方案**  
- 配置文件里只加字段判断来源 — 否，逻辑会散落在各处，来源一多就失控。
- 所有来源归一到一个通用爬虫 — 否，各社区 API 形态差异大，通用化成本高且脆弱。

## [2026-08-01] LLM 接口只支持 OpenAI 协议

**背景**  
LLM 调用方式需要定死。生态里有 OpenAI 协议、Anthropic 协议等。用户倾向简单、自带 base_url + api_key。

**决策**  
只实现 OpenAI 协议（POST {base_url}/chat/completions）。base_url、api_key、model 全部由用户提供：api_key 走环境变量（OPENAI_API_KEY），base_url 与 model 走环境变量或 config.json。

**理由**  
OpenAI 协议是事实标准，DeepSeek、OpenRouter、Ollama、vLLM 等均兼容，覆盖面足够。用户自带 URL + key 意味着项目无需内置任何模型账号。

**备选方案**  
- 同时支持 Anthropic 协议 — 否，增加复杂度，当前无需求。
- 项目内置 key — 否，违反安全原则，且用户明确自带。
