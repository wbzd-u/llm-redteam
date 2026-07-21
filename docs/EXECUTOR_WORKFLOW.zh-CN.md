# PyRIT、Inspect AI 与 Promptfoo 执行流程

三种工具共享同一个经过人工审核的 Campaign，但职责不同：

- PyRIT：对授权 HTTP 目标执行 Campaign；
- Inspect AI：固定 Campaign 样本与实验条件；
- Promptfoo：把 Campaign 变成版本回归配置。

## 可选 LLM 规划器

任务工作台可以保存 OpenAI-compatible endpoint、模型名和 API Key 环境变量名。配置检查默认不联网、不读取密钥。只有点击“明确联网并生成审核草稿”时，后端才从指定环境变量临时读取密钥并请求模型。

LLM 只能输出满足固定 schema 的草稿：机制假设、依据、控制变量、预期信号、停止条件和 `approval_required=true` 的步骤。草稿不会自动批准、创建 Campaign 或执行目标。

## PyRIT Campaign

先执行 dry-run。此命令不会读取请求文件，也不会发送网络请求：

```powershell
python -m redteam_memory campaign pyrit-http `
  --campaign-id "<campaign-id>" `
  --request-file "<local-request-template>"
```

检查 Campaign、预算、模板和目标范围后，才显式增加 `--execute`。请求模板与凭据文件不应提交到 Git，也不会由看板读取或展示。

## Inspect AI Campaign

Inspect 任务入口能够直接读取一个已审核 Campaign：

```powershell
$env:REDTEAM_CAMPAIGN_ID = "<campaign-id>"
$env:REDTEAM_MEMORY_DB = "<local-memory.sqlite3>"
python -m inspect_ai eval experiments/memory_cases.py --model "<authorized-model>"
```

任务不内置通用“是否攻破”评分器。需要根据题目的平台状态、工具结果或业务状态配置专用 scorer。

## Promptfoo Campaign

```powershell
python -m redteam_memory campaign export `
  --campaign-id "<campaign-id>" `
  --format promptfoo `
  --out artifacts\campaign.promptfoo.json
```

导出的 `providers` 为空。补充授权 Provider 和与成功判据对应的 assertions 后，再运行 Promptfoo。

## 导回外部结果

无论来自 Inspect、Promptfoo 还是人工复核，都先转换为下面的最小 JSON，再导回 Campaign：

```json
[
  {
    "step_id": "s1",
    "outcome": "no_change",
    "response": "可选的模型响应",
    "refusal": false,
    "observed_effect": "外部可观察结果",
    "evidence_description": "可选的工具或平台判据",
    "evidence_verified": false,
    "confirms_impact": false
  }
]
```

```powershell
python -m redteam_memory campaign import-results `
  --campaign-id "<campaign-id>" `
  --source inspect `
  --file artifacts\normalized-results.json
```

导入只记录外部结果，不会把模型回答自动升级为“已确认通关”。只有有对应平台、UI、工具或后端证据的记录才能进入确认流程。
