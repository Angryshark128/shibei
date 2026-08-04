# 拾贝 · 决策记录

## [2026-08-03] Ctrl+C 用 os._exit 优雅退出 + 数据原子写

**背景**  
并行爬取后，Ctrl+C 若用 `sys.exit` / 返回退出码，解释器退出时 `concurrent.futures.thread._python_exit` 会 join 所有**非守护**工作线程——即使已 `shutdown(wait=False)`，进程仍会阻塞到最慢来源爬完（实测 3s 的 sleep 阻塞了 3.06s）。这不是「优雅关闭」。

**决策**  
- 两个入口（`crawler.py` / `analyzer.py`）捕获 `KeyboardInterrupt`，打印提示后 `os._exit(130)` 立即终止（绕过 `_python_exit` 的 join）。
- `save_topic` 与列表缓存改为**原子写**（先写 `.tmp` 再 `os.replace`）：`os._exit` 中断不产生半截 JSON，帖子要么完整要么不存在，下次运行断点续传。

**理由**  
爬虫数据以文件为单位持久化，`os._exit` 不丢已完成内容；原子写消除唯一的数据损坏窗口（worker 写到一半被杀）。测试通过 monkeypatch `os._exit` 验证退出码与提示。

**备选方案**  
- `sys.exit(130)` — 否，被 `_python_exit` join 阻塞，爬取期间 Ctrl+C 等于没反应。
- 等 worker 跑完再退 — 否，可能等数分钟，违背「优雅」。
- 仅 os._exit 不做原子写 — 否，worker 写帖中途被杀会留损坏文件，且该 id 因「已存在」被永久跳过。

## [2026-08-03] 来源间并行爬取

**背景**  
多来源后 `run_crawl` 仍逐来源串行。用户指出不同来源限流互不影响，应可并行。

**决策**  
`run_crawl` 用 `ThreadPoolExecutor(max_workers=len(sources))` 并行爬取来源；state 读写用 `threading.Lock` 保护（`save_state` 本身原子替换，锁防止并行时读到半更新状态 / 丢键）。单来源失败仍不影响其他。分析侧保持现状（批次 × 类别并发，`max_workers=4`），因 LLM 调用共享同一 API Key，按来源再并行不增加吞吐。

**理由**  
爬取是 I/O + sleep 密集（`request_delay` 保护各自来源），串行是纯等待浪费；并行墙钟 ≈ 最慢来源。分析是 LLM 单 key 限流，已有批次并发即可饱和。

**备选方案**  
- 来源流水线化（A 分析时 B 爬取）— 否，分析共用 LLM key 是真正瓶颈，收益趋零且复杂度高。
- 不并行 — 否，等待浪费明显。

## [2026-08-03] 分析结论强制中文（即使数据源是英文）

**背景**  
接入 HN / Lobste.rs / Dev.to / Product Hunt 等英文源后，用户明确要求：不管数据源是英文还是中文，最终分析文档结论都必须是中文。

**决策**  
批次与合并 prompt 的规则统一强化为「一律用中文回答；即使原文是英文，也要用中文输出」，并用测试锁定（`test_build_batch_prompt_forces_chinese_even_for_english` / `test_build_merge_prompt_forces_chinese_even_for_english`）。

**理由**  
模型可能照源语言输出（源是英文就回英文）。措辞显式覆盖「原文为英文」场景，比泛泛的「用中文回答」更稳。

**备选方案**  
- 不做修改，沿用「用中文回答」— 否，用户明确要求，且英文源占比高，值得写死。
- 分析后再做语言归一 — 否，让 LLM 一步到位最省 token，且归一不可靠。

## [2026-08-03] 来源必须在 config 配置节且 enabled 才启用

**背景**  
`get_sources` 原逻辑是 `conf.get("enabled", True)`——来源未在 config 出现时默认启用。单来源时代无感；接入 5 个新来源后，用户若只保留 v2ex 配置节，其余 5 个来源会全部默认启用并对外发请求，属意外行为。同时与设计文档「新增来源需在 config 加一节」的描述不符。

**决策**  
`get_sources` 改为：来源必须出现在 config 的 `sources` 节且 `enabled` 为真才启用（缺失配置节即不启用）。config.json 已为 5 个新来源显式配置 `enabled: true`，行为不变。

**理由**  
「配置驱动」更可预期：源码注册 ≠ 已接入，接入 = 实现 + 注册 + 配置节。避免仅注册实现类就静默爬取外部 API。

**备选方案**  
- 保持缺失即启用，改测试适配 — 否，多来源下是真实隐患，且与文档意图冲突。
- 默认 `enabled: false` — 需在每节显式开，改动面更大，与现有「opt-out」习惯不符。

## [2026-08-03] 新来源字段按真实 API 适配（不止照抄接入指南）

**背景**  
接入指南部分字段假设与真实 API 不符，经实测确认：Lobste.rs 的 `submitter_user` / `commenting_user` 是字符串用户名（指南写对象）；评论为扁平列表且 `children` 多为 null（指南写嵌套树）；少数派 feed 实为 RSS 2.0 且 `pubDate` 为 RFC 2822（指南写 Atom + ISO 8601）；Dev.to 评论 id 是 `id_code`。

**决策**  
实现按真实响应适配并做防御：用户名兼容字符串/对象两种形态；评论展平兼容扁平与嵌套；`parse_atom_feed` 同时解析 Atom 与 RSS 2.0；`iso_to_unix` 兼容 ISO 8601 与 RFC 2822。

**理由**  
字段名以实测为准，否则抓下来就是脏数据（或直接崩溃，如 `children=None` 进入递归）。防御性处理保证不同 API 版本都能归一。

**备选方案**  
- 严格照指南实现 — 否，Lobste.rs 真实数据会让 `_flatten_comments` 对 `None` 迭代抛 TypeError。


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
