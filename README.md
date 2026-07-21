# LLM Red Team Workbench

一个面向**授权 LLM 安全评估、CTF 和防御研究**的证据优先红队工作台。

本项目将个人红队经验从零散对话整理为可检索、可重放、可比较的实验记录，并连接 PyRIT、Inspect AI、Promptfoo、IPI Arena 与 Jailbreaker-CE。它不会因为模型在文本中“声称成功”就认定漏洞成立；只有平台评分、工具状态、UI 状态或其他可验证运行时证据，才能确认真实影响。

> 当前定位：红队 Agent 的执行、记忆与证据底座，尚不是无人值守的全自主攻击 Agent。

## 为什么需要它

常规聊天窗口适合探索，但不适合长期红队研究：上下文会丢失，失败过程难以复盘，模型自述容易造成误判，同一测试也难以跨模型、跨版本复现。

本项目重点解决四个问题：

- **机制记忆**：保存成功、失败、适用模型、载体、前置条件与边界。
- **受控执行**：通过 Replay、PyRIT HTTP 或专用目标适配器执行明确授权的测试。
- **实验复现**：导出 Inspect AI 样本和 Promptfoo 回归配置。
- **证据闭环**：区分叙事性配合、Judge 评分与真实运行时状态变化。

## 架构

```text
知识库 / IPI Arena / Jailbreaker-CE
                 |
                 v
     Case -> Attempt -> Turn -> Evidence
                 |
                 v
       状态机与保守下一步建议
                 |
        +--------+---------+
        |        |         |
      Replay   PyRIT    GraySwan
        |        |         |
        +--------+---------+
                 |
                 v
       Inspect AI / Promptfoo / 审计导出
```

核心代码不依赖第三方包，使用 SQLite 保存以下对象：

| 对象 | 作用 |
| --- | --- |
| `Case` | 一个目标、关卡或风险假设 |
| `Attempt` | 一次机制测试及其结果 |
| `Turn` | 按顺序保存用户、模型、工具或评估器回合 |
| `Evidence` | 运行时状态、平台评分、人工验证或 Judge 观察 |

状态机包含：`baseline`、`probing`、`first_refusal`、`verification`、`confirmed` 和 `halted`。连续两次没有状态变化时，系统建议切换机制，而不是重复堆叠相同输入。

## 已接入组件

| 组件 | 当前用途 | 状态 |
| --- | --- | --- |
| 自研记忆层 | SQLite、状态机、证据最小化、检索 | 可用 |
| ReplayTarget | 无网络离线重放 | 可用 |
| PyRIT | HTTP 目标执行与消息编排 | 可用，可选依赖 |
| Inspect AI | 从已记录案例构建可复现实验 | 可用，可选依赖 |
| Promptfoo | 导出回归测试配置 | 可用，导出级 |
| 防御感知评测 | 防御档案、差异观察、覆盖矩阵与回归门禁 | 可用，人工观察驱动 |
| IPI Arena | 导入间接提示注入种子 | 可用 |
| Jailbreaker-CE | 离线发现并生成技术种子 | 可用 |
| GraySwan | 授权关卡的 JSON/SSE 单轮执行 | 实验性 |

导入的攻击样本统一标记为 `unknown`，不会被自动当成已验证漏洞。

## 快速开始

要求 Python 3.11 或更高版本。

```powershell
git clone https://github.com/wbzd-u/llm-redteam.git
cd llm-redteam

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e . pytest
.\.venv\Scripts\python.exe -m pytest -q
```

初始化数据库：

```powershell
.\.venv\Scripts\python.exe -m redteam_memory init
```

查看全部命令：

```powershell
.\.venv\Scripts\python.exe -m redteam_memory --help
.\.venv\Scripts\python.exe -m redteam_memory run --help
```

## 最小工作流

### 1. 创建案例

```powershell
.\.venv\Scripts\python.exe -m redteam_memory case add `
  --title "Authorized baseline" `
  --target "sandbox-model" `
  --challenge "controlled evaluation" `
  --mechanism baseline `
  --carrier direct-chat `
  --impact "protocol validation" `
  --tag baseline
```

记下输出中的 `case_id`。

### 2. 离线重放

```powershell
.\.venv\Scripts\python.exe -m redteam_memory run replay `
  --case-id "<case-id>" `
  --mechanism baseline `
  --input "CONTROLLED_CANARY" `
  --response "controlled response" `
  --outcome unknown
```

该命令会同时保存用户回合、模型回合和 Attempt，不会访问网络。

### 3. 查看案例与下一步建议

```powershell
.\.venv\Scripts\python.exe -m redteam_memory show "<case-id>"
.\.venv\Scripts\python.exe -m redteam_memory recommend "<case-id>"
.\.venv\Scripts\python.exe -m redteam_memory compact "<case-id>"
```

`compact` 会生成经过最小化与脱敏的交接视图，适合进入下一次实验或新的 Agent 上下文。

## 记录真实证据

模型输出不是事实来源。证据可信度默认按以下顺序处理：

```text
后端 / UI / 工具状态
> 部署侧评分器
> LLM Judge
> 模型自述
```

记录一条独立验证的证据：

```powershell
.\.venv\Scripts\python.exe -m redteam_memory evidence add `
  --case-id "<case-id>" `
  --kind runtime `
  --description "Challenge UI state changed" `
  --source "challenge-ui" `
  --verified
```

只有明确的正向运行时字段或外部状态变化才应确认影响。拒绝、失败和无变化同样应该记录，因为它们可以帮助识别防御边界并避免重复测试。

## 防御感知评测

防御感知评测层用于把**公开文档、已授权配置和实际观察**转为可比较数据。它不读取私有服务内部规则，不生成规避变体，也不将“检测器未拦截”自动认定为漏洞。

它包含三类记录：

| 记录 | 作用 |
| --- | --- |
| `DefenseProfile` | 防御名称、版本、公开来源、声明范围、假设与已知限制 |
| `DefenseObservation` | 某条已授权案例在一个 run 中的期望 allow/block 与实际 allow/block |
| 回归报告 | 比较两个 run，识别覆盖变化、过度拦截和潜在漏放回归 |

创建一个防御档案：

```powershell
python -m redteam_memory defense profile add `
  --name "Example policy classifier" `
  --version "1.0" `
  --kind classifier `
  --source "public system card" `
  --scope "text input" `
  --assumption "English coverage is documented" `
  --limitation "Multilingual coverage must be measured"
```

记录一项人工确认的观察。`expected` 表示该授权测试按你的政策应当 allow 还是 block；`observed` 表示防御器实际决定：

```powershell
python -m redteam_memory defense observe add `
  --case-id "<case-id>" `
  --profile-id "<profile-id>" `
  --run-id "model-2026-07" `
  --expected allow `
  --observed block `
  --language en `
  --carrier text `
  --verified `
  --notes "Authorized false-positive check"
```

生成按语言、载体和期望决策分组的覆盖矩阵：

```powershell
python -m redteam_memory defense matrix --profile-id "<profile-id>"
```

比较模型或防御版本前后的回归：

```powershell
python -m redteam_memory defense regression `
  --profile-id "<profile-id>" `
  --baseline-run "model-2026-06" `
  --candidate-run "model-2026-07"
```

当一个原本应当 block 的案例从 `block` 变为 `allow` 时，报告会标记 `critical_under_block_regression`，但仍要求人工复核和部署侧证据。

### LLM Guard 桥接

本地 `llm-guard` checkout 通过子进程桥接，不会作为主项目依赖导入。当前仓库 README 已标记该项目归档；建议在独立 Python 3.10–3.12 环境安装，并单独管理其模型与重量级依赖：

```powershell
cd C:\path\to\llm-guard
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

从主项目执行一次离线扫描：

```powershell
cd C:\Users\www29\ai_redteam_agent
python -m redteam_memory defense llm-guard `
  --repo "C:\path\to\llm-guard" `
  --python "C:\path\to\llm-guard\.venv\Scripts\python.exe" `
  --input "SAFE_CANARY" `
  --scanner PromptInjection `
  --timeout 900
```

如果同时提供 `--case-id`、`--profile-id`、`--run-id` 和 `--expected`，扫描结果会自动写入 `DefenseObservation`：

```powershell
python -m redteam_memory defense llm-guard `
  --repo "C:\path\to\llm-guard" `
  --python "C:\path\to\llm-guard\.venv\Scripts\python.exe" `
  --input "SAFE_CANARY" `
  --case-id "<case-id>" `
  --profile-id "<profile-id>" `
  --run-id "llm-guard-0.3.16" `
  --expected allow `
  --language en `
  --carrier text `
  --verified
```

当前桥只开放 `PromptInjection`，后续扫描器必须逐个验证构造函数、依赖和输出语义后再加入；扫描器没有拦截不等于目标模型或应用已经被攻破。

`PromptInjection` 首次运行还会从 Hugging Face 缓存一个约 704 MiB 的分类权重。该权重不进入本仓库，也不属于主项目依赖；网络受限时可以先使用桥接、记录和回归功能，待缓存完成后再执行真实分类扫描。

## PyRIT HTTP 执行

PyRIT 在本项目中是执行引擎：负责发送、接收和编排；自研层负责机制记忆、状态判断和证据归档。

Dashboard 中的“PyRIT 专栏”将 PyRIT 从任务页中的一个选项提升为独立工作台。它展示：

- 当前已可运行的单轮受控发送；
- 即将接入的 Converter 管线与固定多轮；
- 需要额外 attacker、scorer 与预算配置的自适应 Red Teaming、Crescendo、PAIR/TAP；
- 每个任务是否已具备批准计划、审核输入、非敏感请求引用和外置凭据等执行条件。

这个分层很重要：专栏会把“已接入”“待接入”“需要配置”清楚区分；不会把尚未实施的 PyRIT 策略伪装成已经可以运行的功能。

### PyRIT 入门模式

Dashboard 默认打开“PyRIT 入门”。它只演示一个最小、离线的原生闭环：

```text
Objective -> PromptSendingAttack -> TextTarget -> AttackResult
```

可选的 `Base64Converter` 会在发送前转换学习文本。`TextTarget` 只显示接收到的消息，不访问网络、不调用模型，也不读取请求模板或凭据；返回 `undetermined` 且原因是“没有配置 Scorer”是预期结果。理解这一页后，再逐步切换到 HTTP Target、Scorer 和固定多轮策略。

准备一份带 `{PROMPT}` 占位符的 Burp 风格请求文件。默认只做 dry-run，只有显式添加 `--execute` 才会访问目标：

```powershell
$env:PYTHONPATH = (Get-Location).Path
$pyritPython = "C:\path\to\pyrit\.venv\Scripts\python.exe"

& $pyritPython -m redteam_memory run pyrit-http `
  --case-id "<case-id>" `
  --mechanism baseline `
  --request-file examples\request_template.txt `
  --input "CONTROLLED_CANARY" `
  --prompt-encoding json
```

确认请求文件和目标范围后再追加 `--execute`。`json`、`url` 和 `raw` 分别适用于 JSON 字符串、表单/查询参数和已自行处理转义的请求。

## GraySwan 授权基线

GraySwan 适配器用于授权比赛环境的 JSON/SSE 实验。它会生成消息 UUID 和时间戳，拼接流式 `0:` 文本，并保存 `messageId`、`chatId` 与显式完成字段。

会话头必须放在本机 Git 忽略文件中，例如：

```text
secrets/session.headers.json
```

```json
{
  "Cookie": "<local-authorized-session-value>"
}
```

不要把 Cookie、Authorization 或 Token 放入命令行、聊天记录或仓库。

先执行 dry-run：

```powershell
python -m redteam_memory run grayswan `
  --case-id "<case-id>" `
  --mechanism baseline `
  --input "CONTROLLED_CANARY" `
  --model "<model>" `
  --association-id "<association-id>" `
  --behavior-id "<behavior-id>" `
  --challenge-id "<challenge-id>" `
  --headers-file secrets\session.headers.json
```

检查目标标识后再追加 `--execute`。已有会话可通过 `--chat-id` 传递顶层聊天 ID；后续回合还需要传递上次响应返回的 `next_parent_id`。当前适配器不会把纯叙事回复当成通关证据。

## 数据集与攻击种子

### IPI Arena

```powershell
python -m redteam_memory import-ipi `
  "C:\path\to\ipi_arena_attacks\attacks.jsonl" `
  --limit 5
```

导入过程使用确定性 ID，重复导入不会创建重复案例。

### Jailbreaker-CE

列出本地技术注册表：

```powershell
python -m redteam_memory jailbreaker list `
  --repo "C:\path\to\Jailbreaker-CE"
```

生成一个离线种子：

```powershell
python -m redteam_memory jailbreaker seed `
  --repo "C:\path\to\Jailbreaker-CE" `
  --technique indirect_prompt_injection `
  --intent "authorized boundary probe" `
  --target-id offline-target
```

生成结果只进入 Attempt，结果仍为 `unknown`，必须人工审阅后才能交给执行层。

## Inspect AI 与 Promptfoo

导出已记录案例：

```powershell
python -m redteam_memory export inspect `
  --case-id "<case-id>" `
  --out artifacts\case.inspect.json

python -m redteam_memory export promptfoo `
  --case-id "<case-id>" `
  --out artifacts\case.promptfoo.json
```

Inspect AI 任务入口位于 `experiments/memory_cases.py`：

```powershell
$env:PYTHONPATH = (Get-Location).Path
& "C:\path\to\inspect_ai\.venv\Scripts\python.exe" `
  -m inspect_ai eval experiments\memory_cases.py --model mockllm/model
```

该任务故意不提供通用“是否攻破”评分器。不同部署的真实影响需要由对应平台评分、工具状态或业务状态证明。

## 机制研究与论文数据包

[`examples/mechanism-taxonomy.zh-CN.json`](examples/mechanism-taxonomy.zh-CN.json) 提供中文机制术语表，覆盖外部上下文信任边界、多轮会话状态、规则优先级、语义校验绑定、跨语言安全对齐、RAG 证据链、Agent 权限边界和多模态载体等研究维度。导入后，可把历史 Case 以 `confirmed`、`observed` 或 `negative` 的关系关联到机制卡：

```powershell
python -m redteam_memory mechanism import examples/mechanism-taxonomy.zh-CN.json
python -m redteam_memory mechanism import examples/mechanism-taxonomy-research-extension.zh-CN.json
python -m redteam_memory mechanism link --mechanism-id <机制ID> --case-id <案例ID> --relation observed
```

生成论文准备数据包：

```powershell
python -m redteam_memory research paper-packet --out artifacts\research-paper-packet.md
```

该数据包只导出方法草稿、机制 × 证据表、数据字典和当前数据缺口，不包含原始输入或模型响应。它会明确区分历史观察与有运行时证据的可复现实验结果，不会把案例数自动包装成统计结论。

机制术语与公开研究方向的对应依据位于 [`docs/MECHANISM_LITERATURE.md`](docs/MECHANISM_LITERATURE.md)。

## 安全边界

- 仅用于自有系统、明确授权环境、比赛沙箱与防御研究。
- 网络执行默认关闭，必须显式添加 `--execute`。
- `secrets/`、`*.headers.json`、数据库、日志和虚拟环境不会进入 Git。
- 不要将模型自述、角色扮演、虚构工具调用或单一 Judge 评分视为漏洞证据。
- 不要对未经授权的线上目标批量运行导入样本。
- 高影响工具调用应额外实施最小权限、人工确认和独立审计。

## 当前限制

- GraySwan 目前以单次 CLI 执行为主，多轮会话仍需显式传递聊天和父消息 ID。
- PyRIT 目前已接入 `HTTPTarget` 与已审核 Campaign 的单轮受控发送；`PromptSendingAttack`、Converter、`MultiPromptSendingAttack`、`RedTeamingAttack`、`CrescendoAttack` 与 `PAIR/TAP` 的原生策略适配将按 PyRIT 专栏路线逐层接入。
- Promptfoo 当前为配置导出，尚未内置 provider 与 CI 执行。
- 防御感知评测目前由人工或已授权外部评估器提供 allow/block 观察；尚未连接具体防守产品的私有 API。
- 本地 LLM Guard checkout 已归档，桥接层目前只支持 `PromptInjection`，且需要独立环境和模型依赖。
- 尚未实现自动机制选择、自动变异、Judge 反馈循环和成功样本最小化。
- 第三方工具保持独立虚拟环境，通过 JSON、子进程或适配器连接，不共享依赖环境。

## 路线图

- 持久化多轮 `ConversationRunner`。
- 基于历史成功率、拒绝位置和目标类型选择测试机制。
- 加入受控候选生成、去重、预算和停止条件。
- 建立部署特定 scorer 与人工复核队列。
- 自动生成最小复现、失败对照和回归矩阵。
- 将 Inspect AI 与 Promptfoo 纳入持续集成。

## 项目结构

```text
redteam_memory/
  store.py                 SQLite 存储
  models.py                Case / Attempt / Turn / Evidence
  state.py                 状态机与证据最小化
  defense.py               防御档案、覆盖矩阵与回归门禁
  llm_guard_adapter.py     LLM Guard 独立环境桥接
  runner.py                单次执行与持久化
  targets.py               Replay 与 PyRIT HTTP Target
  grayswan.py              GraySwan JSON/SSE 适配器
  inspect_integration.py   Inspect AI 集成
  ipi_import.py            IPI Arena 导入
  jailbreaker_adapter.py   Jailbreaker-CE 桥接
experiments/
  memory_cases.py          Inspect AI 任务入口
scripts/
  smoke_pyrit_http.py      PyRIT 回环测试
  llm_guard_bridge.py      LLM Guard JSON 子进程桥
tests/
  test_memory.py           核心测试
```

## 项目状态

当前版本为研究型 MVP。核心测试、离线重放、SQLite 记忆层、PyRIT/Inspect 桥接、数据集导入和 GraySwan SSE 解析已经可用；自主规划与完整多轮 Agent 循环仍在开发中。
