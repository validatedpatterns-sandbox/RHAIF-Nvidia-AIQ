# AI-Q verification map

Maintained source for verifying user-facing research behavior of the OpenShift-deployed
NVIDIA AI-Q backend. Read this index before driving, then use the matching feature file.

## Baseline preconditions

- Pattern deployed; `svc/aiq-backend` exists in namespace `aiq`.
- Launch with
  `LAUNCH_OUT="$(.cursor/skills/verify-aiq/scripts/launch-port-forward.sh)" || exit 1; eval "${LAUNCH_OUT}"`
  so `AIQ_SERVER_URL` / `VERIFY_AIQ_STATE_DIR` are exported.
- Run `.cursor/skills/verify-aiq/scripts/doctor.sh` and require both
  `shallow_researcher` and `deep_researcher` in `agents`.
- Shallow uses `What is the capital of France?` unless `VERIFY_AIQ_QUESTION` is set.
- Deep uses the Chernobyl causes question unless `VERIFY_AIQ_DEEP_QUESTION` is set.
  See [deep research](./deep-research.md).
- Never drive a backend or port-forward that this verification run did not start
  (shared cluster: do not cancel foreign jobs).

## Driving conventions

- Prefer explicit async agent types over orchestrated `chat`.
- Treat every command as literal; keep quoted questions unchanged.
- Run helpers from the repo root with the absolute or relative skill path shown.
- After mutations (job submit), keep the job id in evidence before polling.
- Restore nothing on the server except cancel jobs this run started; retain artifacts.

## Proof and skip reporting

- Capture submit + final report for each agent, not only the final text.
- Reasonableness proof is a written `verdict.md`: **makes sense** or
  **does not make sense** per agent, with one short why.
- Record the feature ID and entry point with every artifact directory.
- Report an unreachable path with the unmet precondition (for example InferenceService
  not Ready). Do not claim shallow verified if only deep returned a report.

## Feature entry contract

Each feature file starts with an H1 and one paragraph, then exactly four H2 sections:

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with aiq.py`
4. `Gotchas`

## Features

- [Paired shallow + deep smoke](./paired-research-smoke.md) — easy question for
  shallow, harder cited question for deep; reasonableness verdict for each.
- [Shallow research](./shallow-research.md) — quick cited answer via
  `shallow_researcher` (in-cluster Lightning).
- [Deep research](./deep-research.md) — long-form report via `deep_researcher`
  (NVIDIA API Catalog Ultra).
