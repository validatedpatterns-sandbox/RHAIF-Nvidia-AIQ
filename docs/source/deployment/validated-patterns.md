<!--
SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# OpenShift (Validated Patterns)

Deploy AI-Q on OpenShift through the [Validated Patterns](https://validatedpatterns.io/learn/) GitOps framework. Scaffolding was generated with [patternizer](https://validatedpatterns.io/learn/creating-patterns-with-patternizer/). This path is single-cluster only: no ACM hub/spoke and no HashiCorp Vault / External Secrets Operator. Secrets use the Validated Patterns `none` backend, which writes Kubernetes Secrets from a local file.

The application Helm chart is unchanged. Pattern values point Argo CD at `deploy/helm/deployment-k8s` and apply OpenShift Helm value overlays under `overrides/` (see `overrides/README.md`). Use [Kubernetes (Helm)](./kubernetes.md) for a direct `helm install`.

## Deployment profile

The Validated Pattern ships one OpenShift profile. `values-prod.yaml` deploys hybrid Lightning with a GPU stack and in-cluster vLLM.

| Prod values | Overlay files | LLM routing |
|---|---|---|
| `values-prod.yaml` | `values-openshift-base.yaml` + `values-openshift-hybrid-lightning.yaml` | Intent + shallow → in-cluster vLLM (Nemotron 3.5 Lightning); clarifier + deep → NVIDIA API Catalog (Nemotron 3 Ultra) |

Workflow YAML is mounted from ConfigMap `aiq-workflow-config` (`charts/aiq-workflow-config/files/config_hybrid_lightning.yml`).

## Prerequisites

- An OpenShift cluster and `oc` logged in with enough privilege to install operators.
- [Podman](https://podman.io/) (the `./pattern.sh` wrapper runs make targets in the Validated Patterns utility container).
- A Git remote Argo CD can clone and this branch pushed.
- Local secret file `~/values-secret-aiq.yaml` (see below). `make install` loads it before waiting for Argo health.

### GPU workers (Phase 0, hybrid profile)

The hybrid Lightning profile requires one GPU worker before OpenShift AI and vLLM can serve the model. On AWS clusters with Machine API:

```bash
./pattern.sh make create-gpu-machineset
# or explicitly:
./pattern.sh make create-gpu-machineset GPU_INSTANCE_TYPE=g6.2xlarge GPU_REPLICAS=1
```

If AWS returns `InsufficientInstanceCapacity`, retry with a different availability zone:

```bash
./pattern.sh make create-gpu-machineset OVERRIDE_ZONE=us-east-2b
./pattern.sh make create-gpu-machineset OVERRIDE_ZONE=us-east-2c
./pattern.sh make create-gpu-machineset OVERRIDE_ZONE=us-east-2a
```

Verify the GPU node:

```bash
oc get machines -n openshift-machine-api | grep gpu
oc get nodes -l node-role.kubernetes.io/odh-notebook=
```

Phase 0 is complete when one GPU worker is `Ready`, labeled `node-role.kubernetes.io/odh-notebook`, and tainted `odh-notebook=true:NoSchedule`. `nvidia.com/gpu` allocatable appears after the GPU Operator syncs (Phase 1).

See [GPU_provisioning.md](https://github.com/validatedpatterns-sandbox/RHAIF-Nvidia-AIQ/blob/main/GPU_provisioning.md) for Azure, manual MachineSet, bare-metal, and verification steps. Clusters without Machine API must add GPU nodes outside GitOps.

The bootstrap profile uses **1× `g6.2xlarge`** (NVIDIA L4, 24 GiB VRAM) with the **NVFP4 Hugging Face checkpoint** (`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4`). vLLM reads quantization from `config.json` — do not pass `--quantization` manually. The vLLM chart provisions an **80Gi model-cache PVC** so Hugging Face weights survive pod restarts; set `global.storageClass` in `values-global.yaml` when the cluster default is not suitable. Track upsize and quantization follow-ups in [TODO.md](https://github.com/validatedpatterns-sandbox/RHAIF-Nvidia-AIQ/blob/main/TODO.md).

Default destination namespace is `aiq` (application) and `aiq-inference` (vLLM). Override `clusterGroup.namespaces`, each application's `namespace` in `values-prod.yaml`, and `targetNamespaces` in `values-secret.yaml.template` only if your cluster requires different project names.

## Configure secrets

Do not commit secrets. Copy the template out of Git and fill in real values:

```bash
cp values-secret.yaml.template ~/values-secret-aiq.yaml
# edit ~/values-secret-aiq.yaml
```

| Field | Purpose |
|---|---|
| `DB_USER_NAME`, `DB_USER_PASSWORD` | In-cluster Postgres |
| `NVIDIA_API_KEY` | Nemotron 3 Ultra (clarifier + deep research) on NVIDIA API Catalog |
| `TAVILY_API_KEY` | Web search (optional for install-only smoke tests) |
| `VLLM_API_KEY` | Optional. Omit from `~/values-secret-aiq.yaml` to use workflow default (`local-vllm`) |
| `AIQ_LIGHTNING_BASE_URL` | Optional. Omit to use the in-cluster vLLM service URL baked into the workflow config |
| `hftoken` in `huggingface-secret` | Optional Hugging Face token if model download is gated |

In-cluster vLLM does not authenticate callers. The hybrid workflow config supplies a default placeholder token so you do not need a real key for Lightning roles. `NVIDIA_API_KEY` is only for Ultra roles that call the NVIDIA API Catalog.

`./pattern.sh make install` (and `./pattern.sh make load-secrets`) looks for `~/values-secret-aiq.yaml` before falling back to the in-repo template. On a fresh cluster, create workload namespaces before `load-secrets` so `huggingface-secret` can land in `aiq-inference`:

```bash
./pattern.sh make ensure-pattern-namespaces
./pattern.sh make load-secrets
```

Encrypt `~/values-secret-aiq.yaml` with `ansible-vault encrypt` if you want it encrypted at rest.

NGC images on this overlay are public enough for many clusters; add an image-pull secret if your cluster cannot pull `nvcr.io/nvidia/blueprint/*`.

## Install

From the repository root, on the branch Argo CD should track:

```bash
./pattern.sh make validate-prereq
./pattern.sh make validate-cluster
./pattern.sh make show
./pattern.sh make install
./pattern.sh make argo-healthcheck
```

`make install` installs the Validated Patterns Operator, OpenShift GitOps, and a `Pattern` custom resource. It then loads secrets into `aiq` and `aiq-inference` (`global.secretStore.backend: none`). Argo CD syncs applications in sync-wave order:

```text
wave -1: aiq-workflow-config (workflow ConfigMap)
wave 10:  nfd-config, nvidia-config (GPU operator enablement)
wave 15:  openshift-ai (DataScienceCluster, KServe serving only)
wave 20:  vllm-inference-service (Nemotron Lightning on vLLM)
wave 30:  aiq (umbrella Helm chart)
```

Before `make install`, run `./pattern.sh make ensure-pattern-namespaces` (or `make load-secrets`, which depends on it) so `huggingface-secret` can land in `aiq-inference`.

`make install` always provisions OpenShift GitOps (`vp-gitops`) when it is missing. `values-global.yaml` sets `global.singleArgoCD: true` so clustergroup Applications are created in that instance instead of a second Argo CD in `aiq-prod`.

## Upgrading from MaaS Granite or older overlays

Earlier pattern revisions used the MaaS Granite profile (`aiq-maas-config`, `values-aiq-openshift.yaml`,
`config_maas_granite.yml`). The current tree ships hybrid Lightning only. After you push this branch and Argo CD
syncs:

1. Delete the legacy Argo CD Application `aiq-maas-config` if it still exists.
2. Delete ConfigMap `aiq-maas-config` in namespace `aiq` when `aiq-workflow-config` is healthy.
3. Update `~/values-secret-aiq.yaml`: remove `OPENAI_API_KEY`, `MAAS_MODEL_NAME`, and
   `AIQ_INFERENCE_BASE_URL` if present; set `NVIDIA_API_KEY` and re-run `./pattern.sh make load-secrets`.
4. Provision a GPU worker (Phase 0) before expecting shallow Lightning traffic to succeed.

Fresh installs can ignore this section.

## Validate

### Infrastructure

The DataScienceCluster enables KServe with headed RawDeployment only. Dashboard, workbenches, data
science pipelines, Kueue, and Ray stay Removed. The pattern does not install the OpenShift Serverless
operator.

```bash
oc get csv -n redhat-ods-operator
oc get csv -n nvidia-gpu-operator
oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.kserve.managementState}{"\n"}'
oc describe node -l node-role.kubernetes.io/odh-notebook= | grep -A2 'nvidia.com/gpu'
oc get inferenceservice -n aiq-inference
oc get pods -n aiq-inference -o wide
```

Wait until the InferenceService is ready before shallow Lightning smoke tests. Model download and GPU
scheduling can take tens of minutes after Argo syncs wave 20:

```bash
oc wait --for=condition=Ready inferenceservice/vllm-inference-service -n aiq-inference --timeout=45m
```

From a debug pod in `aiq`, confirm the vLLM OpenAI API responds:

```bash
curl -sf http://vllm-inference-service-predictor.aiq-inference.svc.cluster.local:8080/v1/models
```

If shallow research fails while `aiq-backend` is healthy, check that the InferenceService above is `Ready`
and that `NVIDIA_API_KEY` is set for Ultra roles.

### AI-Q health

```bash
oc get pods,pvc -n aiq
oc -n aiq port-forward svc/aiq-backend 8000:8000
# in another terminal:
curl -sf http://127.0.0.1:8000/live && echo
curl -sf http://127.0.0.1:8000/health && echo
```

Frontend Ingress is disabled on OpenShift. The overlay enables an OpenShift Route for `svc/aiq-frontend` on port 3000; use `oc get route -n aiq` to find the UI URL.

### Agent smoke proof (hybrid routing)

Use [`skills/aiq-research/scripts/aiq.py`](../../../skills/aiq-research/scripts/aiq.py) against the port-forwarded backend:

```bash
export AIQ_SERVER_URL=http://127.0.0.1:8000
python3 skills/aiq-research/scripts/aiq.py health
python3 skills/aiq-research/scripts/aiq.py agents

# Shallow — must hit in-cluster vLLM (Lightning)
python3 skills/aiq-research/scripts/aiq.py submit \
  "What is NVIDIA Nemotron in one sentence?" shallow_researcher
python3 skills/aiq-research/scripts/aiq.py status <JOB_ID>
python3 skills/aiq-research/scripts/aiq.py report <JOB_ID>

# Deep — must hit NVIDIA API (Ultra); cancel to limit cost
python3 skills/aiq-research/scripts/aiq.py submit \
  "List three public facts about OpenShift." deep_researcher
python3 skills/aiq-research/scripts/aiq.py status <JOB_ID>
python3 skills/aiq-research/scripts/aiq.py cancel <JOB_ID>
```

Confirm routing in backend or vLLM predictor logs: shallow traffic to `aiq-inference`, deep traffic to `integrate.api.nvidia.com`.

For hosted-Lightning citation behavior vs self-hosted validation, see [troubleshooting](../resources/troubleshooting.md#nemotron-35-lightning-on-nvidia-api-catalog).
