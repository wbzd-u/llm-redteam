# LLM Red Team Workbench：产品设计（v0.1）

## 1. 产品定义

**LLM Red Team Workbench** 是面向授权靶场、CTF 与安全研究的个人红队 Copilot。它把零散的通关经验和实验记录沉淀为可检索的“机制记忆”，在 LLM 的分析辅助下提出新的、可验证的测试假设，执行受控实验，并把结果转化为可复现证据、数据分析和报告。

它不是单一的提示词生成器，也不是声称能对任意目标“自动通关”的黑盒程序。其价值是把以下闭环做快、做稳、做可积累：

```text
经验与题目 → 机制建模 → 假设/测试计划 → 受控执行 → 成功验证
       ↑                                            ↓
       └───────── 证据、分析、复现与报告 ────────────┘
```

### 1.1 目标用户

第一阶段用户是项目作者本人：同时是 CTF 选手、LLM 红队学习者和研究型作品集建设者。后续可扩展到小型安全研究团队。

### 1.2 关键问题

1. 手工聊天记录会丢失上下文，成功和失败无法系统复用。
2. 通用 LLM 建议常缺少对目标、历史记录和实验变量的理解。
3. 自动化测试若没有预算、状态控制和成功判据，容易低效且无法解释。
4. 已有工具各自解决一小段流程，用户需要在多个 CLI、环境和日志格式之间切换。
5. 通关结果难以自然转化为可重放实验、统计结论和安全报告。

### 1.3 非目标

- 不把模型自称“完成了目标”当作漏洞成立的证据。
- 不把第三方攻击样本自动标成已验证成果。
- 不将 Cookie、令牌、原始敏感内容或本地数据库提交到 Git。
- 不在第一阶段打造不可控、无限轮数的全自主运行器。

## 2. 产品目标与成功标准

### 2.1 北极星指标

在一项授权挑战中，用户能从题目导入到得到**可复现、可解释、带证据的结果**，而不是只留下聊天截图。

### 2.2 可量化指标

| 维度 | 指标 | 第一阶段目标 |
| --- | --- | --- |
| 经验利用 | 新 Case 被关联到历史机制卡的比例 | ≥ 70% |
| 效率 | 有效测试占全部尝试的比例 | 持续上升，可按机制统计 |
| 可复现性 | 确认结果可一键重放的比例 | 100% |
| 证据质量 | `confirmed` 结果包含平台/UI/工具证据的比例 | 100% |
| 研究产出 | 每个完成 Case 能导出结构化报告 | 100% |
| 成本控制 | 每个 Campaign 记录轮数、时间、模型调用成本 | 100% |

## 3. 用户任务与典型场景

### 场景 A：手动打关助手

用户粘贴题目、目标信息和当前对话；系统解析成功条件，检索相似历史案例，给出 3–5 个按优先级排列的测试假设。用户自行发送消息，随后把响应导入，系统更新状态和建议。

**用户需要看到的不是一段泛泛建议，而是：**“此步骤要验证的机制”“预期正/负信号”“为何优先做它”“若失败后切换到哪里”。

### 场景 B：受控自动 Campaign

用户选择已授权目标、测试策略和预算（最大轮数、时间、成本、是否允许新会话）。系统在每一轮记录输入、输出和状态；达到可验证成功条件、预算耗尽或连续无信息增益后停止。完成后生成最小复现和待人工确认项。

### 场景 C：复现与回归

用户选中已确认或待验证的 Case，在相同或不同模型、版本、会话条件下重放。系统对比成功率、响应分类和外部证据，不把单次偶然现象误写为稳定结论。

### 场景 D：研究与作品集

用户按模型、语言、机制、载体、会话长度、结果、轮数等维度筛选实验，导出 CSV/JSON/Markdown，生成图表、实验方法、局限性和安全报告草稿。

## 4. 产品能力地图

```text
┌────────────────────────── 用户工作区 ──────────────────────────┐
│ Challenge Inbox │ Case Workspace │ Campaign │ Replay │ Analytics │
└────────────────────────────────────────────────────────────────┘
             │                 │                 │
             ▼                 ▼                 ▼
┌────────────────────── Red Team Copilot ─────────────────────────┐
│ 题目分析 │ 机制检索 │ 假设规划 │ 实验批评 │ 结果判定 │ 报告生成 │
└────────────────────────────────────────────────────────────────┘
             │                 │                 │
             ▼                 ▼                 ▼
┌──────────────────── 实验与证据核心层 ───────────────────────────┐
│ Case / Mechanism / Experiment / Attempt / Turn / Evidence       │
│ 状态机 │ 预算 │ 会话 │ 成功判据 │ 最小复现 │ 审计日志            │
└────────────────────────────────────────────────────────────────┘
             │                 │                 │
             ▼                 ▼                 ▼
┌──────────────────────── 插件与适配层 ───────────────────────────┐
│ GraySwan │ PyRIT │ Inspect AI │ Promptfoo │ IPI Arena │ Evaluators │
└────────────────────────────────────────────────────────────────┘
```

## 5. 功能需求

### P0：经验、证据与可复现底座

| 编号 | 功能 | 验收标准 |
| --- | --- | --- |
| FR-01 | Challenge Inbox：录入题目、目标、授权范围、成功判据 | 可从文本、JSON 或已有聊天记录创建 Case |
| FR-02 | 机制记忆：记录机制卡、适用条件、失败信号、历史案例 | 新 Case 可按标签和语义检索相似 Case |
| FR-03 | 统一实验记录 | 每次 Attempt 保存版本、会话、轮次、时间、输入、输出和元数据 |
| FR-04 | 证据分级 | 区分模型叙述、Judge、人工确认、平台/UI/工具状态 |
| FR-05 | 最小复现 | 对确认/候选结果生成可人工审阅的最小必要链路 |
| FR-06 | 导出 | 可生成 Markdown、JSON、CSV 与 Inspect/Promptfoo 工件 |

### P1：LLM 红队 Copilot

| 编号 | 功能 | 验收标准 |
| --- | --- | --- |
| FR-10 | 题目分析器 | 输出结构化目标、约束、成功判据、信任边界和待验证假设 |
| FR-11 | 历史检索器 | 每项建议至少关联题目证据或历史机制卡；无依据时标为推测 |
| FR-12 | 测试计划器 | 生成少量、互相可区分的实验步骤，包含变量、预期信号和停止条件 |
| FR-13 | 结果批评器 | 标注混杂变量、重复机制、证据不足和下一步需要的信息 |
| FR-14 | 结果 Judge | 输出结构化分类及理由；不直接升级为 `confirmed` |
| FR-15 | 上下文压缩 | 为每个 Case 生成可追溯摘要，避免聊天上下文不足 |

### P2：受控执行与自动 Campaign

| 编号 | 功能 | 验收标准 |
| --- | --- | --- |
| FR-20 | Target Adapter | 统一 `send / receive / reset / status` 协议，支持 Replay 与授权靶场 |
| FR-21 | Campaign Runner | 支持手动、半自动和自动三种模式 |
| FR-22 | 预算与停止 | 强制最大轮数、时长、成本、会话数；成功或无信息增益时停止 |
| FR-23 | 成功验证器 | 优先读取平台/UI/工具状态；无法确认时标为 `candidate` 或 `unknown` |
| FR-24 | 人工批准点 | 用户可在执行前批准计划，并随时暂停/重置 |

### P3：分析、科研与交付

| 编号 | 功能 | 验收标准 |
| --- | --- | --- |
| FR-30 | 数据看板 | 按机制、模型、语言、载体、轮数和结果筛选 |
| FR-31 | 实验比较 | 可比较 clean/polluted/reset、模型版本和策略版本 |
| FR-32 | 统计导出 | 导出结构化数据、成功率、置信描述及原始样本链接 |
| FR-33 | 自动报告 | 输出通关复盘、漏洞报告与研究实验摘要三种模板 |
| FR-34 | 回归门禁 | 对已确认 Case 运行重放并生成变化报告 |

## 6. 核心数据模型

现有 `Case → Attempt → Turn → Evidence` 模型保留，并补充以下对象：

| 对象 | 作用 |
| --- | --- |
| `Challenge` | 题目、授权范围、成功判据和目标配置的原始入口 |
| `MechanismCard` | 机制定义、适用条件、失败模式、历史证据、策略版本 |
| `Experiment` | 一个可复现的对照实验设计，包含变量与预算 |
| `Campaign` | 对 Experiment 的一次运行实例，包含执行模式和状态 |
| `Hypothesis` | 由用户或 LLM 提出的可证伪猜想，必须标记依据与置信度 |
| `Evaluation` | 规则/Judge/人工/平台验证结果及其来源 |
| `Artifact` | 截图、请求摘要、导出配置、报告和最小复现工件 |

**关键原则：**原始记录不可被 LLM 摘要覆盖；摘要、判断和人工结论都以独立对象保存，并可回链到原始 Turn/Evidence。

## 7. 模块取舍

### 7.1 自研：必须成为产品核心

| 模块 | 原因 |
| --- | --- |
| 工作区/案例模型 | 这是所有功能共享的数据和用户体验，不能交给任一第三方工具决定 |
| 机制记忆与检索 | 承载用户个人经验，是差异化所在 |
| Copilot 编排与结构化输出 | 将题目、记忆、实验和证据连接成闭环 |
| 状态机、预算和成功判据 | 保证自动化可解释、可暂停、可审计 |
| 证据分级、最小复现和报告 | 把通关现象升级为研究与作品集资产 |
| 统一 CLI/API（后续 Web UI） | 用户只面对一个入口，而非多个框架 |

### 7.2 第一批接入：高价值、边界清晰

| 组件 | 产品角色 | 何时调用 |
| --- | --- | --- |
| PyRIT | 多轮执行与会话/日志后端 | Campaign 需要多轮目标交互时 |
| Inspect AI | 可复现实验格式 | 保存或重放正式实验时 |
| Promptfoo | 批量对照与回归执行 | 比较模型/提示/版本时 |
| GraySwan Adapter | 当前授权挑战的目标接入 | 在用户明确选择该靶场时 |
| IPI Arena OS | 间接注入场景、判据和数据结构参考 | 建立或扩展间接注入实验时 |

### 7.3 后续按需接入：不进入主链路

| 组件 | 价值 | 接入条件 |
| --- | --- | --- |
| agentic_safety | 多步 Agent 安全实验参考 | 目标涉及工具调用或环境动作 |
| HarmBench / JailbreakBench | 标准化结果比较 | 开始做跨模型研究或公开评估 |
| garak | 广覆盖基线扫描 | 需要初始风险画像时 |
| llm-guard | 防守侧误报/漏报测量 | 需要研究过滤器或防守回归时 |
| Jailbreaker-CE / EasyJailbreak | 离线研究框架与实验设计参考 | 需要比较公开研究方法时 |

**决策：**第三方项目保留在隔离环境中，只通过明确的适配器和结构化工件连接；不把其依赖、数据格式或内部状态扩散到核心层。

## 8. 分期路线图

### Milestone 0：研究底座（已有基础，补齐设计）

- Case/Attempt/Turn/Evidence、状态机、最小证据、Replay；
- GraySwan、PyRIT、Inspect、Promptfoo 的基础适配；
- 机制卡和 Challenge Inbox 的数据设计。

### Milestone 1：个人红队 Copilot（下一阶段）

- 结构化题目导入；
- Case 摘要与机制检索；
- LLM 生成结构化假设/测试计划/结果批评；
- 人工执行辅助和 Markdown 报告；
- 基础分析表：机制 × 目标 × 结果。

**完成标准：**用户可对一关从题目导入开始，获得有依据的计划、录入实际响应、形成最小复现和一份复盘。

### Milestone 2：受控 Campaign 与回归

- 目标能力声明与统一 Adapter 协议；
- 预算、暂停、批准点、成功验证器；
- Promptfoo 真实执行与回归报告；
- 同一 Case 的跨模型/跨会话对照。

**完成标准：**用户能在授权目标上运行受预算的半自动 Campaign，并一键重放确认结果。

### Milestone 3：研究分析与可视化

- 可筛选实验数据集与统计导出；
- 成功率/轮数/稳定性/迁移性分析；
- 自动生成研究摘要、图表和报告模板；
- 可选本地 Web UI。

## 9. 非功能需求

- **本地优先：**数据库、原始对话、Cookie 和密钥默认只保存在本地；敏感目录被 Git 忽略。
- **可追溯：**任何 LLM 建议、Judge 结果或压缩摘要都应能定位到输入、模型、版本和原始记录。
- **可控：**自动执行有授权范围、预算和人工停止能力。
- **可扩展：**新增目标或评估器不应要求修改核心数据模型。
- **低门槛：**日常使用以一个 CLI 入口开始，后续才引入 Web UI；第三方环境不污染主项目依赖。

## 10. 首批交付清单（建议）

下一轮实现只做以下内容：

1. `Challenge Inbox`：从 Markdown/JSON 创建结构化 Case；
2. `MechanismCard`：存储经验卡并支持标签检索；
3. `Copilot Plan Schema`：定义 LLM 输出的假设、依据、变量、预期信号、停止条件；
4. `assist` 命令：读取 Case + 机制记忆，生成待用户确认的测试计划；
5. `analysis export`：导出 Case/Attempt 的表格和 Markdown 复盘；
6. 仅以 Replay Target 做端到端测试，再接入真实授权目标。

在这些功能完成前，不继续大规模接入新仓库。这样每个新组件都会有明确产品位置和验收标准。

### Challenge Inbox v0.1 输入格式

第一版采用一个可版本控制的 JSON 文件。模板见
[`examples/challenge-intake.example.json`](../examples/challenge-intake.example.json)。导入命令：

```powershell
python -m redteam_memory intake import examples/challenge-intake.example.json
```

它会创建 `Case`、保存授权范围/成功判据/约束/目标配置，并可一并导入已发生的对话。Markdown 题目导入将在下一次迭代补充，以避免在第一版用不稳定的自由文本解析替代结构化事实。

### MechanismCard v0.1

机制卡模板见 [`examples/mechanisms.example.json`](../examples/mechanisms.example.json)。它以机制、适用/排除信号和证据关联为中心，而不是保存某一句输入。常用流程：

```powershell
python -m redteam_memory mechanism import examples/mechanisms.example.json
python -m redteam_memory mechanism link --mechanism-id "mechanism-document-context" --case-id "<case-id>" --relation observed
python -m redteam_memory mechanism recommend --case-id "<case-id>"
```

推荐结果包含规则得分和逐项原因（标签、关键词、历史关联），便于人工审阅；后续 LLM 计划器将只使用这些可回链的候选卡，而不是凭空假设。

### 计划器与分析导出 v0.1

项目现在提供一个模型无关的计划器接口：`plan context` 导出最小、可追溯的 LLM 输入上下文；任意本地或云端模型可按输出 schema 生成 JSON，再由 `plan import` 校验并存入版本化计划。无 API 密钥时仍可使用 `plan draft` 创建确定性的人工审阅草案。

```powershell
python -m redteam_memory plan context --case-id "<case-id>" > planner-context.json
python -m redteam_memory plan draft --case-id "<case-id>"
python -m redteam_memory plan import --case-id "<case-id>" --planner "local-or-cloud-llm" --json-file examples/plan.example.json
python -m redteam_memory analysis markdown --case-id "<case-id>" --out artifacts/case-report.md
python -m redteam_memory analysis attempt-csv --case-id "<case-id>" --out artifacts/attempts.csv
```

计划默认是 `draft`，每个步骤均要求人工批准；该层不自动把计划发送给目标。自动 Campaign 将在具备明确预算、暂停点和平台成功验证器后再加入。

若使用本地或云端的 OpenAI-compatible 模型端点，可直接生成计划。命令默认只干运行，不读取密钥；只有显式添加 `--execute` 后，才从指定环境变量（默认 `OPENAI_API_KEY`）读取凭据并发出请求：

```powershell
python -m redteam_memory plan generate --case-id "<case-id>" `
  --endpoint "http://localhost:8000/v1/chat/completions" --model "your-model"

$env:OPENAI_API_KEY = "<local-session-key>"
python -m redteam_memory plan generate --case-id "<case-id>" `
  --endpoint "https://provider.example/v1/chat/completions" --model "your-model" --execute
```

端点和模型由调用者明确提供；密钥不会写入数据库、输出或 Git。返回内容会经过计划 schema 校验，失败时不会创建计划记录。

### Campaign Runner v0.1

Campaign 只执行已批准计划的显式输入文件，模板见 [`examples/campaign-inputs.example.json`](../examples/campaign-inputs.example.json)。它不会把抽象步骤自动扩展为无限请求。支持离线 Replay 与明确授权的 GraySwan 适配器，且每次运行都受轮数、时长和可观察成本预算控制：

```powershell
python -m redteam_memory plan approve "<plan-id>"
python -m redteam_memory campaign create --plan-id "<plan-id>" --target-kind replay --max-turns 3 --max-seconds 120
python -m redteam_memory campaign replay --campaign-id "<campaign-id>" --inputs-file examples/campaign-inputs.example.json
```

GraySwan Campaign 默认干运行，只有 `--execute` 才加载本地 `.headers.json` 文件并发送授权请求。发现经验证的运行时成功证据、达到预算或发生目标错误后，Campaign 会停止并保存原因。
