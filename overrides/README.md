# OpenShift Helm value overlays

Validated Patterns applies these files on top of the AI-Q umbrella chart at
`charts/aiq2-web`. Argo CD loads them through `clusterGroup.applications.aiq.extraValueFiles`
in `values-prod.yaml`.

## Three configuration layers

| Layer | Files | What it controls |
|---|---|---|
| Pattern globals | `values-global.yaml` | Argo CD mode, secret backend, model IDs |
| Cluster topology | `values-prod.yaml` | Operators, GPU stack, vLLM, and AI-Q Argo applications |
| OpenShift overlays | `overrides/values-openshift-*.yaml` | Platform tweaks for the AI-Q umbrella chart (Route, PVC, workflow mount) |

These overlays only adjust how the published AI-Q images run on OpenShift.

## Overlay files

| File | Purpose |
|---|---|
| `values-openshift-base.yaml` | OpenShift Route instead of Ingress, Postgres PVC |
| `values-openshift-hybrid-lightning.yaml` | Mount `config_hybrid_lightning.yml` (in-cluster vLLM + NVIDIA API Ultra) |

Helm list values replace rather than merge. Always apply base plus the hybrid overlay.

## Credentials

- `NVIDIA_API_KEY` — Nemotron 3 Ultra on the NVIDIA API Catalog (clarifier + deep research).
- In-cluster vLLM (Lightning) does not need a real API key. The workflow config defaults a placeholder token.

See `values-secret.yaml.template` and [validated-patterns.md](../docs/source/deployment/validated-patterns.md).
