# Paired shallow + deep smoke

Runs an easy question through `shallow_researcher` and a harder cited question
through `deep_researcher`, then records whether each answer makes sense.

## Sub-features

- `pair-shallow` submits and polls `shallow_researcher` for the easy question.
- `pair-deep` submits and polls `deep_researcher` for the harder cited question.
- `pair-verdict` writes a coarse reasonableness judgment for each report.

## How to get to it (user POV)

- Operator/agent runs the verification helpers against a port-forwarded backend
  (not the browser UI).
- Equivalent manual path: submit two async jobs in the AI-Q API/debug console,
  shallow with the France question and deep with the Chernobyl question.

## Driving it with aiq.py

Preconditions:

- Port-forward launch succeeded (`LAUNCH_OUT="$(.../launch-port-forward.sh)" || exit 1; eval "${LAUNCH_OUT}"`).
- `.cursor/skills/verify-aiq/scripts/doctor.sh` lists both agent types.
- Shallow question is `What is the capital of France?` unless `VERIFY_AIQ_QUESTION` is set.
- Deep question is the Chernobyl causes prompt unless `VERIFY_AIQ_DEEP_QUESTION` is set.

- **Run pair.** Drive both agents. Run
  `OUT=$(.cursor/skills/verify-aiq/scripts/run-pair.sh)`. Exit code `0` and `$OUT`
  points at an artifact directory containing `shallow-report.json` and
  `deep-report.json`.
- **Read shallow report.** Open `$OUT/shallow-report.json`. The payload contains
  research answer text (report body / message content). Note the `job_id` in
  `$OUT/shallow-job-id.txt`.
- **Read deep report.** Open `$OUT/deep-report.json`. Note `$OUT/deep-job-id.txt`.
- **Judge reasonableness.** For each agent, decide only **makes sense** or
  **does not make sense**. Shallow makes sense when the answer names Paris.
  Deep makes sense when the report names the RBMK reactor and at least one
  technical cause, and the source section does not contradict that. Write
  `$OUT/verdict.md` with both verdicts and a one-line why each.
- **Proof.** Keep `$OUT` intact after cleanup. Proof is incomplete without
  `verdict.md` plus both report JSON files.

## Gotchas

- `chat` may escalate or choose depth automatically; do not use it for this feature.
- Deep research is slow; do not treat a long `running` status as failure until the
  job reaches a terminal state or the backend returns an error.
- If InferenceService is not Ready, shallow may fail while deep still succeeds —
  report shallow as failed, do not skip writing the deep verdict.
- Cleanup cancels only job IDs in this run's state file; foreign jobs stay running.
