# AI Red Team Agent MVP

This project is a small, dependency-free memory and evidence layer for
authorized LLM red-team experiments. It does not generate attack payloads or
claim success from narrative text. It records the mechanism, carrier, impact,
conversation state, runtime evidence, and evaluator results so experiments can
be replayed and compared.

## Setup

```powershell
cd C:\Users\www29\ai_redteam_agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

The core package uses only the Python standard library. PyRIT, Inspect AI and
Promptfoo remain optional adapters and are not imported at startup.

## Seed the known break log

```powershell
.\.venv\Scripts\python.exe -m redteam_memory --db data\redteam_memory.sqlite3 seed examples\seed_cases.json
```

## Basic commands

```powershell
.\.venv\Scripts\python.exe -m redteam_memory case list
.\.venv\Scripts\python.exe -m redteam_memory search guard
.\.venv\Scripts\python.exe -m redteam_memory show B-20260714-002
.\.venv\Scripts\python.exe -m redteam_memory attempt add --case-id B-20260714-002 --mechanism "controlled canary" --input "example" --outcome refused --first-refusal
```

Record a turn from a file when the response contains newlines:

```powershell
.\.venv\Scripts\python.exe -m redteam_memory turn add --case-id B-20260714-002 --role assistant --content-file response.txt --provenance target --refusal
```

Record independently verified evidence:

```powershell
.\.venv\Scripts\python.exe -m redteam_memory evidence add --case-id B-20260714-002 --kind runtime --description "UI counter changed" --source "challenge-ui" --verified
```

Export stored cases as provider-neutral Inspect samples or a Promptfoo
regression skeleton:

```powershell
.\.venv\Scripts\python.exe -m redteam_memory export inspect --case-id B-20260714-002 --out artifacts\guard.inspect.json
.\.venv\Scripts\python.exe -m redteam_memory export promptfoo --case-id B-20260714-002 --out artifacts\guard.promptfoo.yaml.json
```

The adapters intentionally produce plain JSON. Provider-specific credentials,
target connectors and attack selection remain outside this first component.

## Offline execution

The replay target exercises the complete recording path without network access:

```powershell
python -m redteam_memory run replay `
  --case-id B-20260714-002 `
  --mechanism baseline `
  --input "controlled canary" `
  --response "target response" `
  --outcome unclear
```

## PyRIT HTTP execution

Save a captured Burp-style request locally with a `{PROMPT}` placeholder. The
command performs a dry run unless `--execute` is explicitly supplied:

```powershell
$pyritPython = "C:\\Users\\www29\\ai_redteam_tools\\pyrit\\.venv\\Scripts\\python.exe"
$env:PYTHONPATH = "C:\\Users\\www29\\ai_redteam_agent"
& $pyritPython -m redteam_memory run pyrit-http `
  --case-id B-20260714-002 `
  --mechanism baseline `
  --request-file request.txt `
  --input "controlled canary" `
  --prompt-encoding json `
  --response-key "choices[0].message.content"
```

Review the dry-run output, then add `--execute` to permit the request. Use
`--prompt-encoding json` for a JSON body, `url` for a query/form placeholder,
and `raw` only when the captured request already handles escaping.

The PyRIT adapter is optional. The core package does not import PyRIT at
startup, and no network request is made by importing the adapter.

For a loopback-only adapter smoke test:

```powershell
$env:PYTHONPATH = "C:\\Users\\www29\\ai_redteam_agent"
& "C:\\Users\\www29\\ai_redteam_tools\\pyrit\\.venv\\Scripts\\python.exe" `
  scripts\\smoke_pyrit_http.py
```

## GraySwan execution

Store the request headers for an authorized GraySwan session in a local JSON
file such as `session.headers.json`. Files ending in `.headers.json` are ignored
by this project. Header values are loaded only when `--execute` is supplied and
are never included in command output.

```json
{
  "Authorization": "Bearer <authorized-session-token>"
}
```

Review a dry run first. This validates the command without loading credentials
or making a network request:

```powershell
python -m redteam_memory run grayswan `
  --case-id B-20260714-002 `
  --mechanism baseline `
  --input "controlled canary" `
  --model "<model>" `
  --association-id "<association-id>" `
  --behavior-id "<behavior-id>" `
  --challenge-id "<challenge-id>" `
  --headers-file session.headers.json
```

Add `--execute` only after reviewing the target identifiers. For a follow-up
turn, pass the returned `next_chat_id` as `--chat-id` and `next_parent_id` as
`--parent-id`. An existing browser conversation may also require its top-level
request `id` to be supplied as `--chat-id`. GraySwan completion
fields are recorded as verified observations, but only an explicit positive
`success` or `passed` field confirms the claimed impact.

## Import IPI Arena attacks

IPI attacks are imported as `seed` cases with `unknown` outcomes. They are
not treated as successful findings because the dataset README documents model
and transfer limitations.

```powershell
python -m redteam_memory import-ipi `
  "C:\\Users\\www29\\ai_redteam_tools\\ipi_arena_attacks\\qwen_open_source_only_attacks.jsonl"
```

The importer is deterministic and idempotent. Use `--limit 5` for a small
offline sample.

## Jailbreaker-CE bridge

The bridge calls Jailbreaker-CE's local attack registry without starting its
Docker services or contacting a target. List techniques:

```powershell
python -m redteam_memory jailbreaker list `
  --repo "C:\\Users\\www29\\ai_redteam_tools\\Jailbreaker-CE"
```

Generate and store one offline seed case:

```powershell
python -m redteam_memory jailbreaker seed `
  --repo "C:\\Users\\www29\\ai_redteam_tools\\Jailbreaker-CE" `
  --technique indirect_prompt_injection `
  --intent "authorized indirect-injection boundary probe" `
  --target-id offline-target
```

The generated rendered messages are stored as an `Attempt` with outcome
`unknown`. Review and select a case before sending it through PyRIT.

An imported IPI attempt can be replayed without copying its payload manually:

```powershell
python -m redteam_memory run replay `
  --case-id ipi-<case-hash> `
  --attempt-id ipi-<case-hash>-attempt `
  --response "offline response" `
  --outcome unknown
```

The same `--attempt-id` option is available on `run pyrit-http`; add a captured
request file and the explicit `--execute` flag when a real authorized target is
ready.

## Inspect AI task

The task entry point is [experiments/memory_cases.py]. It reads only cases
with recorded user turns or attempts; metadata-only seed cases are skipped so
an empty task cannot be mistaken for a valid experiment.

Run it from the Inspect AI environment after recording at least one replay:

```powershell
$env:PYTHONPATH = "C:\\Users\\www29\\ai_redteam_agent"
& "C:\\Users\\www29\\ai_redteam_tools\\inspect_ai\\.venv\\Scripts\\python.exe" `
  -m inspect_ai eval experiments\\memory_cases.py --model mockllm/model
```

The task intentionally has no generic scorer. A real break must be scored with
the deployment-specific runtime, tool, UI, or challenge evaluator evidence.

To choose a conservative next experiment or create a redacted handoff:

```powershell
.\.venv\Scripts\python.exe -m redteam_memory recommend B-20260714-002
.\.venv\Scripts\python.exe -m redteam_memory compact B-20260714-002
```
