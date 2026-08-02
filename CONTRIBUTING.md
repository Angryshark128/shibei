# 贡献指南

感谢你愿意为拾贝做贡献！本指南说明如何参与开发。

## 开发环境

```bash
git clone <repo-url> && cd shibei
uv sync                  # 创建 .venv 并安装 dev 依赖
uv run pre-commit install
```

要求：Python 3.10+，[uv](https://docs.astral.sh/uv/) 管理依赖。

## 代码规范

提交前必须通过以下全部检查：

```bash
uv run ruff format .           # 格式化
uv run ruff check .            # Lint（单行 ≤ 120 字符）
uv run pyright .               # 类型检查
uv run pytest                  # 测试
```

pre-commit 钩子已配置好 `ruff format` / `ruff check --fix` 与基础格式校验，推送到前请执行 `uv run pre-commit run --all-files`。

设计约束（见 `docs/design.md` 与 `.claude/CONSTITUTION.md`）：

- **零运行时依赖**：核心逻辑只用标准库 `urllib`，不引入第三方运行时包。
- **统一数据结构**：所有来源输出同一结构的帖子 JSON（`models.py`）。
- **来源可插拔**：社区差异隔离在 `sources/` 内，主流程与分析模块不感知具体来源。
- **API Key 安全**：不写入代码、配置或仓库，只走环境变量。

## 如何新增一个来源

1. 新建 `sources/{name}.py`，继承 `sources/base.py` 的 `Source`：
   - `fetch_topics(node, page) -> list[Post]`
   - `fetch_replies(topic_id) -> list[Reply]`
   - `list_nodes() -> list[dict]`（可选）
2. 在 `sources/__init__.py` 的 `SOURCES` 注册。
3. 在 config.json `sources` 加一节（enabled / nodes / pages_per_node 等）。
4. 在 `tests/` 补测试：mock `http_get_json`，验证字段映射与边界（缺失字段、非 list 返回等）。

## 提交规范

- 提交信息用中文或英文皆可，说明「做了什么 + 为什么」。
- 一个提交只做一个逻辑变更。
- 相关设计/决策变化请同步更新 `docs/design.md` 与 `.claude/DECISIONS.md`。

## 提 PR

1. 从 main 分支开新分支（`feat/...`、`fix/...`、`docs/...`）。
2. 在本地通过全部检查与测试。
3. 描述变更动机、实现方式、影响范围；若有 UI/输出变化附示例。
4. 维护者 review 后合并。

## 报告问题

提交 issue 时请包含：

- 复现步骤与运行环境（Python 版本、uv 版本）
- 相关命令输出（脱敏掉 API Key）
- 期望行为与实际行为的差异

## 行为准则

保持友善与建设性；讨论聚焦于代码与设计，不针对个人。
