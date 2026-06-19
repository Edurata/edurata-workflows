# AGENTS.md — Edurata Workflows

Notes for AI agents generating or editing workflow YAML in this repository. Workflows are declarative: **execution order and dataflow are inferred from `props` dependencies**, not from YAML key order.

**Canonical schema:** `../edurata-yaml/schema.json` (JSON Schema draft-07)  
**Runtime validation / types:** `../edurata-sdki/clients/types/src/definitions.ts` (Zod; superset of the JSON schema)  
**Primary reference example:** `examples/hello-world.yaml`

---

## What this repo is

Public workflow templates for [Edurata](https://docs.edurata.com). A workflow chains **steps** (inline code, git-sourced functions, or Docker images). Companion implementations live in [edurata-functions](https://github.com/Edurata/edurata-functions).

| Path | Purpose |
| --- | --- |
| `examples/` | Small, teaching workflows (`hello-world.yaml`, `breakfast-info.eduwc.yml`, …) |
| `apps/` | Product workflows; often split into `partials/` + root file with `includes` |
| `internals/` | Platform workflows (e.g. `build-functions.eduwc.yaml`) |
| `apps/*/functions/*/` | Co-located **function** definitions (`.edufc.yaml` + `index.py` / `index.ts`) used by app workflows |

Private/customer workflows: sibling repo `edurata-workflows-private`.

---

## File types and naming

| Extension | Resource | `apiRevision` |
| --- | --- | --- |
| `.yaml`, `.yml`, `.eduwc.yml`, `.eduwc.yaml` | Workflow | Prefer `edurata.io/workflow/v1` |
| `.edufc.yaml` | Standalone function | `edurata.io/function/v1` |
| `.edurata.yaml` | Workflow (VS Code extension) | Same as workflow |

Legacy files may use `apiRevision: edurata.io/v1`; new workflows should use **`edurata.io/workflow/v1`**.

**Step keys** must match `^[a-zA-Z0-9-_]{1,100}$` (kebab-case is conventional: `fetch-weather`, `get-listing-data`).

---

## Workflow document schema

### Required

- **`steps`** — map of step id → step definition. Each step needs **either** `(runtime` + `code)` **or** `source` **or** nested `steps` (sub-workflow step).

### Strongly recommended for generation

| Field | Type | Notes |
| --- | --- | --- |
| `apiRevision` | `"edurata.io/workflow/v1"` | Version pin |
| `name` | string | Registry id (unique per account) |
| `title` | string | Human label (not the registry id) |
| `description` | string | What the workflow does |
| `interface` | object | Typed `inputs` / `outputs` (JSON Schema–style) |

### Optional (top level)

| Field | Purpose |
| --- | --- |
| `outputs` | Map workflow outputs → `${stepId.outputKey}` or nested paths |
| `inputs` | Explicit wiring of globals into workflow inputs (often unnecessary; globals work in `props`) |
| `billingIds` | Usage metering ids (string, array, object, or interpolation); see Billing |
| `schedule` | Cron expression (e.g. `0 8 * * *`) |
| `integrations` | OAuth provider declarations (see Integrations) |
| `includes` | Relative paths to partial YAML files (see Partials) |
| `cache` | boolean |
| `resources` | `{ memory, cpu }` for ECS sizing |
| `retentionInHours`, `sensitive`, `multiplicator` | Platform metadata |

### Minimal skeleton

```yaml
apiRevision: edurata.io/workflow/v1
name: my-workflow
title: Short human title
description: |
  What this workflow does.
interface:
  inputs:
    type: object
    properties:
      myInput:
        type: string
    required:
      - myInput
  outputs:
    type: object
    properties:
      result:
        type: string
outputs:
  result: ${last-step.result}
steps:
  last-step:
    description: One sentence describing this step.
    runtime: python3_10
    code: |
      def handler(event):
          return {"result": event["myInput"]}
    props:
      myInput: ${inputs.myInput}
```

---

## `interface` (inputs / outputs)

JSON Schema–inspired. Top-level `inputs` and `outputs` each have:

- `type: object` (optional but common)
- `properties` — map of field name → property schema
- `required` — array of required property names

### Property `type` values

Standard: `string`, `number`, `integer`, `boolean`, `array`, `object`, `null`, `any`, …

Edurata-specific (see `IEduFcInterfaceType` in sdki):

| Type | Use |
| --- | --- |
| `file` | Path to uploaded file in runner `/tmp` |
| `env` | Secret/env value (sensitive) |
| `cmdValue` | Docker command argv list |
| `cmdKeyValue` | Docker env-style key/value |
| `dependency` | Reference to another resource |
| `interpolation` | String with `${…}` |
| `meta` | Platform metadata |

Nested objects/arrays use `properties`, `items`, `required`, `enum`, `default`, `description` like JSON Schema.

Step-level `interface` documents that step’s handler inputs/outputs (recommended for inline steps; git functions bring their own `.edufc.yaml` or inline definition).

---

## Steps

Every step should have a **`description`** (used by UI and AI tooling).

### Mode A — Inline function

```yaml
my-step:
  description: Transforms the payload.
  runtime: nodejs20   # or python3_10 | docker
  code: |
    exports.handler = async (event) => {
      return { out: event.in };
    };
  interface: { ... }    # optional but good practice
  props:
    in: ${upstream-step.out}
```

- **Node:** `exports.handler = async (event) => { … }` (event = resolved `props`).
- **Python:** `def handler(event): …` or `def handler(inputs): …` (both appear in this repo; match surrounding app style).
- **`packages`** (Node only): npm deps for inline steps, e.g. `packages: { "isomorphic-git": "1.25.6" }`.
- **`entrypoint`**, **`include`**, **`exclude`**: packaging hints for inline/deployed functions.

### Mode B — Git source (preferred for reuse)

```yaml
my-step:
  description: HTTP call via shared axios helper.
  source:
    repoUrl: https://github.com/Edurata/edurata-functions.git
    path: general/axios
    ref: main          # optional; defaults to main
  props:
    method: GET
    url: https://api.example.com/data
    headers:
      Authorization: Bearer ${secrets.MY_API_KEY}
```

`source` alternatives:

| Shape | Meaning |
| --- | --- |
| `{ repoUrl, path?, ref? }` | Clone repo subpath |
| `{ imageRepoUrl, tag }` | Docker image (`runtime: docker` on step or implied) |
| `{ name, revision? }` | Edurata registry function |
| `{ name, ref }` | Inline registry reference |

### Mode C — Docker

```yaml
test-docker:
  description: Run container with interpolated command.
  runtime: docker
  source:
    imageRepoUrl: docker/whalesay
    tag: latest
  interface:
    inputs:
      properties:
        cmd:
          type: cmdValue
  props:
    cmd:
      - cowsay
      - "Hello ${other-step.message}"
```

### Step modifiers

| Field | Behavior |
| --- | --- |
| `foreach` | Iterate over array dependency; use `${each}` or `${each.field}` in `props` |
| `if` | [JSONLogic](https://jsonlogic.com) object; step/iteration skipped when false |
| `else` | On skip: `fail` \| `success` \| `skip` \| `continue` |
| `optional` | Step marked optional at definition level |
| `concurrency` | Limit parallel foreach branches |
| `delaySeconds` | Delay before run |

**Execution order:** determined by which steps appear in `${…}` references inside `props` (and `foreach` / `if`), **not** by order under `steps:`.

---

## Interpolation `${…}`

Primary dataflow mechanism. Appears in `props`, `outputs`, `billingIds`, `foreach`, and string templates.

### Forms

| Pattern | Meaning |
| --- | --- |
| `${inputs.field}` | Workflow input |
| `${secrets.SECRET_NAME}` | Secret (often OAuth token) |
| `${variables.VAR_NAME}` | Variable |
| `${files.FILE_NAME}` | User-uploaded file |
| `${stepId.outputKey}` | Prior step output |
| `${stepId.nested.path}` | Dot path into output object |
| `${stepId.response.data.items[0].id}` | JSONPath-like segments in brackets |
| `${stepId[each.index].field}` | Foreach: align with current iteration index |
| `${stepId[*].field}` | Collect field across all foreach results |
| `${stepId?}` | **Optional** dependency — step may be skipped without failing dependents |
| `${each}` | Current foreach element (string or object) |
| `${each.index}` | Current iteration index |

Literals without `${}` are passed as-is. Strings can mix text and interpolations: `"Hello ${name}"`.

**Do not** invent step output keys; they must match the function’s `interface.outputs` or inline handler return shape.

---

## `if` conditions (JSONLogic)

Evaluated with [json-logic-js](https://github.com/jwadhams/json-logic.js). Use a **single operator per object**; nest for complex logic.

Supported operators include: `===`, `==`, `!==`, `!=`, `>`, `<`, `>=`, `<=`, `and`, `or`, `!`, `!!`, `in`, `if`, `min`, `max`.

Example (from `examples/hello-world.yaml`):

```yaml
foreach: ${inputs.messages}
if:
  or:
    - ===:
        - ${each}
        - Hello
    - ===:
        - ${each}
        - World
```

Operands are usually interpolations or literals. Conditions apply per foreach iteration when both are set.

---

## `foreach`

```yaml
process-items:
  description: Handle each id.
  foreach: ${list-step.ids}
  source:
    repoUrl: https://github.com/Edurata/edurata-functions.git
    path: some/function
  props:
    id: ${each}
    parentData: ${list-step[each.index].meta}
```

- `foreach` value must resolve to an **array** (empty array → step may be skipped).
- Reference sibling foreach results with **`[each.index]`** on the step id.
- Use **`[*]`** to fan-in all iterations (e.g. `${generate-ai-responses[*].response}`).

---

## Globals: secrets, variables, files

| Scope in interpolation | Source |
| --- | --- |
| `secrets.*` | Deployment/environment secrets; OAuth integrations use names from `integrations` |
| `variables.*` | Non-secret config |
| `files.*` | Uploaded files |
| `inputs.*` | Workflow interface inputs |

Declare required OAuth in **`integrations`**:

```yaml
integrations:
  copilot-outlook-oauth:
    provider: microsoft
    scopes:
      - Mail.Read
      - Mail.ReadWrite
      - Mail.Send
```

Use as `${secrets.copilot-outlook-oauth}` in `props`.

---

## Workflow `outputs`

Maps declared interface outputs to dependencies:

```yaml
outputs:
  weather: ${fetch-weather.response.data.timelines.daily[0].values}
  news: ${fetch-news.response.data.articles}
```

Omit `outputs` when nothing must be exposed outside the run.

---

## `billingIds`

Top-level (or per-step on functions) for usage accounting:

```yaml
billingIds: ${inputs.messages}
# or
billingIds: ${generate-replies[*].response.data.reply}
```

Values flatten to a list of strings at runtime.

---

## Partials and `includes`

Large apps split YAML across files. Root workflow lists partials **in merge order**; **later files override keys** on conflict.

```yaml
# apps/copilot/copilot-listener.eduwc.yml
name: copilot-listener
apiRevision: edurata.io/workflow/v1
includes:
  - ./partials/copilot-listener.interface-integrations.eduwc.yml
  - ./partials/copilot-listener.outlook-steps.eduwc.yml
  - ./partials/copilot-listener.common-steps.eduwc.yml
```

Rules:

- Paths are **relative** to the including file (not absolute).
- No circular includes.
- Partials may define only `steps`, `interface`, `integrations`, etc.; the merger deep-merges objects and concatenates arrays of primitives (deduped).
- **Step execution order is still dependency-based**, not include order.

When generating a big workflow, prefer: `interface` + `integrations` partial → provider-specific step partials → shared steps partial.

---

## Co-located functions (`.edufc.yaml`)

App-specific logic under `apps/<app>/functions/<name>/`:

```yaml
apiRevision: edurata.io/function/v1
name: get-listing-data
title: Get listing data
runtime: python3_10
interface:
  inputs:
    type: object
    properties:
      messages:
        type: array
    required:
      - messages
  outputs:
    type: object
    properties:
      response:
        type: object
    required:
      - response
```

Reference from a workflow via `source.repoUrl` pointing at **this** repo (or publish to registry). Keep `name` aligned with the directory name.

---

## Runtimes

| `runtime` | Handler contract |
| --- | --- |
| `nodejs20` | `exports.handler = async (event) => …` |
| `python3_10` | `def handler(event): …` |
| `docker` | `cmd` / env via `props`; `cmdValue` / `cmdKeyValue` types |

---

## Generation checklist

When creating or extending a workflow:

1. Set `apiRevision: edurata.io/workflow/v1` and unique `name`.
2. Define `interface.inputs` / `interface.outputs` with `type: object` wrappers where the repo’s examples do.
3. Add a clear `description` on the workflow and **every** step.
4. Prefer **`source` → edurata-functions** over large inline `code` when a suitable function exists (`general/axios`, `etl/extract/*`, …).
5. Wire data only through **`props`** using `${…}`; ensure every referenced `stepId` exists and outputs match.
6. Use **`foreach`** + `[each.index]` for per-item processing; **`*`** for aggregate fan-in.
7. Add **`integrations`** when using `${secrets.*}` OAuth secrets.
8. For multi-provider or long workflows, split with **`includes`** partials instead of one huge file.
9. Match existing apps’ naming (`get-*`, `create-*`, `extract-*`) and runtime (Python vs Node) in the same folder.
10. Validate mentally against `examples/hello-world.yaml` and an app similar to your task (e.g. `apps/copilot/` for email/AI patterns).

---

## Anti-patterns

- Relying on YAML key order under `steps` for execution sequencing.
- Missing `description` on steps (hurts UI and AI step implementation).
- `${step.output}` keys that don’t exist on the function’s declared outputs.
- Forgetting `[each.index]` when combining two foreach steps in one iteration.
- Using `apiRevision: edurata.io/v1` on new files.
- Absolute paths in `includes`.
- Huge inline `code` blocks when `edurata-functions` already provides the operation.

---

## Related repos

| Repo | Role |
| --- | --- |
| `edurata-functions` | Public function library (`source.repoUrl`) |
| `edurata-yaml` | VS Code grammar + `schema.json` |
| `edurata-sdki` | Zod schemas, include merger, graph/staging helpers |
| `edurata-backend` | `prepare-step-context` resolves props at runtime; `private-api` AI generation prompts in `constants.ts` |

Platform docs: https://docs.edurata.com/#workflow-config
