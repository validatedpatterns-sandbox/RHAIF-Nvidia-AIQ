<!--
SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# OpenShift (Validated Patterns)

Deploy AI-Q on OpenShift through the [Validated Patterns](https://validatedpatterns.io/learn/) GitOps framework. Scaffolding was generated with [patternizer](https://validatedpatterns.io/learn/creating-patterns-with-patternizer/). This path is single-cluster only: no ACM hub/spoke and no HashiCorp Vault / External Secrets Operator. Secrets use the Validated Patterns `none` backend, which writes Kubernetes Secret `aiq-credentials` from a local file.

The application Helm chart is unchanged. Pattern values point Argo CD at `deploy/helm/deployment-k8s` and apply `overrides/values-aiq-openshift.yaml` (MaaS Granite config mount, Postgres PVC on the cluster default StorageClass, nginx Ingress disabled, frontend OpenShift Route enabled). Use [Kubernetes (Helm)](./kubernetes.md) for a direct `helm install`.

## Prerequisites

- An OpenShift cluster and `oc` logged in with enough privilege to install operators.
- [Podman](https://podman.io/) (the `./pattern.sh` wrapper runs make targets in the Validated Patterns utility container).
- A Git remote Argo CD can clone (for example `https://github.com/validatedpatterns-sandbox/RHAIF-Nvidia-AIQ`) and this branch pushed.
- Local secret file `~/values-secret-aiq.yaml` (see below). `make install` loads it before waiting for Argo health.

### GPU workers (Phase 0, optional today)

The default MaaS Granite overlay does not need GPUs. For a future self-hosted Nemotron Lightning profile (RHOAI vLLM on-cluster), provision GPU workers first.

On AWS clusters with Machine API, mirror [rag-llm-gitops](https://github.com/validatedpatterns/rag-llm-gitops) and create two `g6.2xlarge` workers:

```bash
./pattern.sh make create-gpu-machineset
```

See [GPU_provisioning.md](https://github.com/validatedpatterns-sandbox/RHAIF-Nvidia-AIQ/blob/main/GPU_provisioning.md) for Azure, manual MachineSet, bare-metal, and verification steps. Clusters without Machine API must add GPU nodes outside GitOps before later RHOAI phases.

Default destination namespace is `aiq`. Override `clusterGroup.namespaces`, each application's `namespace` in `values-prod.yaml`, and `targetNamespaces` in `values-secret.yaml.template` only if your cluster requires a different project name.

## Configure secrets

Do not commit secrets. Copy the template out of Git and fill in real values:

```bash
cp values-secret.yaml.template ~/values-secret-aiq.yaml
# edit ~/values-secret-aiq.yaml
# set DB_USER_NAME, DB_USER_PASSWORD, OPENAI_API_KEY,
# AIQ_INFERENCE_BASE_URL, MAAS_MODEL_NAME; TAVILY_API_KEY may be empty
```

`./pattern.sh make install` (and `./pattern.sh make load-secrets`) looks for that file before falling back to the in-repo template. Encrypt it with `ansible-vault encrypt ~/values-secret-aiq.yaml` if you want it encrypted at rest.

`NVIDIA_API_KEY` is not required for the MaaS Granite profile (`charts/aiq-maas-config/files/config_maas_granite.yml`). NGC images on this overlay are public enough for many clusters; add an image-pull secret if your cluster cannot pull `nvcr.io/nvidia/blueprint/*`.

## Install

From the repository root, on the branch Argo CD should track:

```bash
./pattern.sh make validate-prereq
./pattern.sh make validate-cluster
./pattern.sh make show
./pattern.sh make install
./pattern.sh make argo-healthcheck
```

`make install` installs the Validated Patterns Operator, OpenShift GitOps, and a `Pattern` custom resource. It then loads `aiq-credentials` into `aiq` (`global.secretStore.backend: none`). Argo CD syncs `aiq-maas-config` (workflow ConfigMap) and `aiq` (umbrella Helm chart).

`make install` always provisions OpenShift GitOps (`vp-gitops`) when it is missing. `values-global.yaml` sets `global.singleArgoCD: true` so clustergroup Applications are created in that instance instead of a second Argo CD in `aiq-prod`.

Re-running `podman run ... quay.io/validatedpatterns/patternizer init` is idempotent. After it runs, keep `values-prod.yaml` pointed at `deploy/helm/deployment-k8s` and namespace `aiq` — patternizer auto-discovers the child chart under `deploy/helm/helm-charts-k8s/aiq`, which does not include the web-profile values. Keep `secretStore.backend: none` and `secretLoader.disabled: false`.

## Validate

```bash
oc get pods,pvc -n aiq
oc -n aiq port-forward svc/aiq-backend 8000:8000
# in another terminal:
curl -sf http://127.0.0.1:8000/live && echo
curl -sf http://127.0.0.1:8000/health && echo
```

Frontend Ingress is disabled on OpenShift (the chart defaults to `ingressClassName: nginx`). The overlay enables an OpenShift Route for `svc/aiq-frontend` on port 3000 instead; OpenShift assigns the hostname. Use `oc get route -n aiq` to find the UI URL.

The NGC backend image does not contain the MaaS Granite workflow YAML. GitOps mounts it from ConfigMap `aiq-maas-config`, sourced from `charts/aiq-maas-config/files/config_maas_granite.yml`.
