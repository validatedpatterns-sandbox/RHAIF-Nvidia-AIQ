# NVIDIA AI-Q on OpenShift (Validated Pattern)

OpenShift [Validated Pattern](https://validatedpatterns.io/) that deploys the
[NVIDIA AI-Q Blueprint](https://github.com/NVIDIA-AI-Blueprints/aiq) with GitOps.
This repository is the pattern wrapper (values, charts, overlays, GPU provisioning).
It does not contain AI-Q application source. Runtime images come from NGC
(`nvcr.io/nvidia/blueprint/aiq-agent:2.2.0` and `aiq-frontend:2.2.0`).

## What this pattern deploys

| Component | How |
|---|---|
| NFD + NVIDIA GPU Operator config | `charts/all/nfd-config`, `charts/all/nvidia-gpu-config` |
| OpenShift AI (KServe serving only) | `charts/all/rhods` |
| In-cluster vLLM (Nemotron 3.5 Lightning) | `charts/all/vllm-inference-service` |
| Hybrid workflow ConfigMap | `charts/aiq-workflow-config` |
| AI-Q backend + frontend | `charts/aiq2-web` + `overrides/` |

Profile: intent + shallow research on in-cluster vLLM; clarifier + deep research on
NVIDIA API Catalog (Nemotron 3 Ultra).

## Prerequisites

- OpenShift cluster with `oc` logged in (cluster-admin or equivalent)
- [Podman](https://podman.io/) (for `./pattern.sh`)
- GPU worker capacity (Machine API on AWS or Azure), or an existing GPU node
- `NVIDIA_API_KEY` for Ultra roles
- This branch pushed to a Git remote Argo CD can clone

## Quick start

```bash
# Phase 0 — GPU workers (AWS example)
./pattern.sh make create-gpu-machineset

# Secrets (do not commit)
cp values-secret.yaml.template ~/values-secret-aiq.yaml
# edit NVIDIA_API_KEY and other fields

./pattern.sh make ensure-pattern-namespaces
./pattern.sh make load-secrets
./pattern.sh make install
./pattern.sh make argo-healthcheck
```

Wait for vLLM:

```bash
oc wait --for=condition=Ready inferenceservice/vllm-inference-service -n aiq-inference --timeout=45m
oc get route -n aiq
```

Full install, upgrade, and validation notes:
[docs/source/deployment/validated-patterns.md](docs/source/deployment/validated-patterns.md).

GPU MachineSet details: [GPU_provisioning.md](GPU_provisioning.md).

## Repository layout

```text
values-global.yaml / values-prod.yaml   Pattern + cluster GitOps config
values-secret.yaml.template             Secret field template
charts/all/                             NFD, GPU Operator, RHOAI, vLLM
charts/aiq-workflow-config/             Hybrid Lightning workflow ConfigMap
charts/aiq2-web/                        AI-Q umbrella Helm chart (relocated)
overrides/                              OpenShift Route / hybrid mounts
ansible/                                GPU MachineSet playbooks
tests/deploy/                           Overlay and chart render tests
```

## License

This Validated Pattern wrapper is copyright Red Hat, Inc., and licensed under
Apache-2.0. See [LICENSE](LICENSE). AI-Q application source, NGC containers, and
upstream blueprint code remain under their NVIDIA licenses.
