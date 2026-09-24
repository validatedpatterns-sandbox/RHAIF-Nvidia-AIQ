# Deep research

Deep research runs the multi-step `deep_researcher` agent and returns a longer
citation-backed report (Nemotron Ultra on the NVIDIA API Catalog in this pattern).

## Sub-features

- `deep-submit` creates an async job with `agent_type=deep_researcher`.
- `deep-poll` waits until success and fetches the final report.
- `deep-verdict` judges whether the report makes sense for the question asked.

## How to get to it (user POV)

- Submit an async job selecting the deep researcher (API, debug console, or
  verification helper).
- In the web UI, ask for thorough / deep research on a topic (UI path is
  secondary; this map drives the explicit agent).

## Driving it with aiq.py

Preconditions:

- Port-forward and doctor as in the feature map baseline.
- Deployment has a valid `NVIDIA_API_KEY` for Ultra.
- Question: the Chernobyl causes prompt (or `VERIFY_AIQ_DEEP_QUESTION`).

- **Submit.** Run
  `python3 .cursor/skills/verify-aiq/scripts/aiq.py submit "What were the main technical causes of the Chernobyl disaster on 26 April 1986, and which reactor type was involved? Include a source section with the pages you used." deep_researcher`.
  Exit code `0`; stdout JSON includes `job_id`.
- **Poll.** Run
  `python3 .cursor/skills/verify-aiq/scripts/aiq.py research_poll <job_id>`.
  Exit code `0`; stdout is the report JSON. Allow a long wait.
- **Judge.** Report makes sense if it names the RBMK reactor and at least one
  technical cause, and the source section does not contradict that. Write a
  one-line verdict.
- **Proof.** Save submit JSON, job id, report JSON, and the verdict.

## Gotchas

- Deep jobs are asynchronous and continue server-side if local polling stops;
  resume with `research_poll <job_id>`.
- Admission limits may reject submit under load; surface the API error and stop.
- A report that never names the RBMK reactor fails the reasonableness bar.
- A one-line answer with no source section fails citation integrity. That is why
  this question asks for causes and a source section.
