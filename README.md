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

Model artifacts are published to a TLS-protected RustFS store and cached on each
selected serving node. Profiles support one-node serving, independent replicas,
and configurable tensor/pipeline distribution through LeaderWorkerSet. See
[model storage and serving](docs/source/deployment/model-storage-and-serving.md)
for disk preparation, topology settings, migration, rollback, and validation status.

## Deploying the demo

Prerequisites: OpenShift cluster with `oc` logged in (cluster-admin or equivalent);
[Podman](https://podman.io/) for `./pattern.sh`; this branch pushed to a Git remote
Argo CD can clone.

### Configure secrets

```bash
cp values-secret.yaml.template ~/values-secret-aiq.yaml
# Fill in keys. Do not commit this file.
```

`./pattern.sh make install` loads `~/values-secret-aiq.yaml` into Vault.

### Provision a GPU node (required before install)

On AWS, the default is **one `g6.12xlarge` worker with four NVIDIA L4 GPUs**,
48 vCPUs, 192 GiB RAM, and a 500 GiB root volume:

```bash
./pattern.sh make create-gpu-machineset
```

See [GPU_provisioning.md](GPU_provisioning.md) for AWS/Azure MachineSet steps and
for labeling an existing GPU node.
Verify at least 350 GiB of usable model-cache disk at `/var/lib/kserve/models`
and apply the cache-node label described in the
[storage prerequisites](docs/source/deployment/model-storage-and-serving.md#prepare-the-platform)
before installation.

### Deploy the pattern

```bash
# Default: BF16 across four L4 GPUs on one node (bf16-tp4):
./pattern.sh make install
# Single-GPU NVFP4 / small token budgets:
./pattern.sh make install PROFILE=nvfp4
# BF16 on one supported 80 GiB GPU:
./pattern.sh make install PROFILE=bf16
# B200 profile:
./pattern.sh make install PROFILE=b200
```

`PROFILE` selects `variants/<name>/` and `profiles/<name>.yaml`. The default is
`bf16-tp4`: one serving replica of Nemotron 3.5 Lightning BF16, using all four
GPUs on one node with TP=4 and PP=1. It has a 65,536-token context limit and a
32,768-token shallow output budget. An explicit `PROFILE=bf16-tp4` selects the
same configuration. GPU provisioning is a separate step from `make install`.

### Check readiness

```bash
oc wait --for=condition=Ready inferenceservice/vllm-inference-service -n aiq-inference --timeout=45m
oc get route -n aiq
python scripts/model-cache.py status
```

Open the frontend Route and try a shallow research query. For upgrade, uninstall,
and troubleshooting, see
[docs/source/deployment/validated-patterns.md](docs/source/deployment/validated-patterns.md).

## License

This Validated Pattern wrapper is copyright Red Hat, Inc., and licensed under
Apache-2.0. See [LICENSE](LICENSE). AI-Q application source, NGC containers, and
upstream blueprint code remain under their NVIDIA licenses.
