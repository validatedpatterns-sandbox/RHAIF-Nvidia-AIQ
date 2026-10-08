<!--
SPDX-FileCopyrightText: Copyright (c) 2026, Red Hat, Inc.
SPDX-License-Identifier: Apache-2.0
-->

# GPU worker provisioning (Phase 0)

Phase 0 prepares GPU worker nodes for a serving profile. Operator install and vLLM serving charts are part of the GitOps path, not Phase 0. Default `PROFILE` is `bf16-tp4`. `PROFILE=bf16` requires you to pass an 80 GiB `GPU_INSTANCE_TYPE` (AWS) or `GPU_VM_SIZE` (Azure).

This document follows [validatedpatterns/rag-llm-gitops GPU_provisioning.md](https://github.com/validatedpatterns/rag-llm-gitops/blob/main/GPU_provisioning.md), with AI-Q defaults. The hybrid Lightning `bf16-tp4` profile defaults to **one `g6.12xlarge` AWS worker with four NVIDIA L4 GPUs** and a 500 GiB root volume. Adjust with Makefile overrides when your quota or model sizing differs.

## When to use Ansible MachineSet provisioning

Use `./pattern.sh make create-gpu-machineset` only when the cluster exposes the OpenShift Machine API on a supported cloud (AWS by default, Azure via `create-gpu-machineset-azure`).

Clusters without Machine API (`platform: None`, bare metal, compact lab) cannot use these playbooks. Add GPU workers through your platform process, then label and taint nodes to match the conventions below.

## Provision GPU workers on AWS

Log in to the target cluster, then from the repository root:

```bash
./pattern.sh make create-gpu-machineset
```

Defaults:

| Variable | Default | Purpose |
|---|---|---|
| `PROFILE` | `bf16-tp4` | Serving profile and worker defaults |
| `GPU_INSTANCE_TYPE` | `g6.12xlarge` | EC2 GPU instance type |
| `GPU_REPLICAS` | `1` | MachineSet replica count |
| `GPU_COUNT` | `4` | GPUs per worker |
| `GPU_VCPU` | `48` | vCPUs per worker |
| `GPU_MEMORY_MB` | `196608` | RAM metadata (192 GiB) |
| `GPU_ROOT_VOLUME_SIZE` | `500` | Root gp3 volume in GiB |
| `OVERRIDE_ZONE` | _(empty)_ | Force an AWS availability zone (for example `us-east-2b`) when capacity fails |

For the optional single-L4 NVFP4 profile:

```bash
./pattern.sh make create-gpu-machineset PROFILE=nvfp4 GPU_ROOT_VOLUME_SIZE=500
# After preparing at least 200 GiB of usable model-cache disk:
./pattern.sh make install PROFILE=nvfp4
```

For two four-L4 workers with sufficient BF16 cache disk:

```bash
./pattern.sh make create-gpu-machineset GPU_REPLICAS=2
```

`GPU_ROOT_VOLUME_SIZE` controls the root gp3 volume in GiB (default 500 for `bf16-tp4`).
The hardware metadata defaults describe the selected profile's instance; override
them together when choosing a different instance. Verify free disk on each node
before applying the model-cache label. Provisioning two nodes does not itself
select serving data parallelism or pipeline parallelism.

If AWS returns `InsufficientInstanceCapacity`, retry another zone:

```bash
./pattern.sh make create-gpu-machineset OVERRIDE_ZONE=us-east-2b
./pattern.sh make create-gpu-machineset OVERRIDE_ZONE=us-east-2c
./pattern.sh make create-gpu-machineset OVERRIDE_ZONE=us-east-2a
```

Wait until Machines reach `Running` and nodes join the cluster:

```bash
oc get machines -n openshift-machine-api | grep gpu
oc get nodes -l node-role.kubernetes.io/odh-notebook=
```

GPU MachineSets are named `{clusterId}-gpu-{availabilityZone}` (for example `mycluster-gpu-us-east-2a`).
If you previously created a region-suffixed MachineSet (for example `mycluster-gpu-us-east-2`), delete the old
MachineSet after the zone-scoped one is healthy so you do not run duplicate GPU workers.

The playbook applies these conventions (same as rag-llm-gitops):

- Label `node-role.kubernetes.io/odh-notebook`
- Taint `odh-notebook=true:NoSchedule`

Later RHOAI vLLM charts can target these nodes with matching tolerations and affinity.

Before enabling serving, prepare enough local disk at `/var/lib/kserve/models`
and label every cache-ready GPU node:

```bash
oc label node <gpu-node> aiq.rhai.redhat.com/model-cache=true
```

The default cache capacity is 200Gi for NVFP4 or 350Gi for BF16, including room
for a previous revision. A capacity setting does not allocate physical disk.
Node-local disk preparation, additional GPU nodes, and any RDMA fabric remain
platform prerequisites. See [model storage and serving](docs/source/deployment/model-storage-and-serving.md)
before selecting replicated or distributed layouts.

## Provision GPU workers on Azure

The default `bf16-tp4` profile requires an explicit Azure SKU with four compatible
GPUs on one node; the generic single-T4 VM cannot run it. Select a suitable size:

```bash
./pattern.sh make create-gpu-machineset-azure GPU_VM_SIZE=<four-GPU-SKU> GPU_REPLICAS_AZURE=1
```

Azure provisioning settings (the playbook retains **two** replicas unless overridden):

| Variable | Default | Purpose |
|---|---|---|
| `GPU_VM_SIZE` | Required for `bf16-tp4` | Azure GPU VM SKU; generic fallback for profiles without a SKU requirement is `Standard_NC8as_T4_v3` |
| `GPU_REPLICAS_AZURE` | `2` | MachineSet replica count |
| `OVERRIDE_ZONE` | _(empty)_ | Force an availability zone when capacity fails |

Override `GPU_VM_SIZE`, `GPU_REPLICAS_AZURE`, or `OVERRIDE_ZONE` as needed. For the default single-node serving layout, pass `GPU_REPLICAS_AZURE=1`. Match both GPU count and VRAM to the serving profile.

## Manual MachineSet (AWS reference)

If your region is outside the playbook supported-region list, render the manifest and edit before apply:

```bash
ansible-playbook ansible/playbooks/create-gpu-machineset.yaml --check
# inspect /tmp/gpu-machineset.yaml
oc apply -f /tmp/gpu-machineset.yaml
```

See rag-llm-gitops [GPU_provisioning.md](https://github.com/validatedpatterns/rag-llm-gitops/blob/main/GPU_provisioning.md) for field-by-field MachineSet guidance.

## Verify GPU capacity before later phases

After nodes are Ready and the NVIDIA GPU Operator is installed (Phase 1 GitOps, not Phase 0):

```bash
oc describe node <gpu-worker> | grep -E 'nvidia.com/gpu|Capacity|Allocatable'
```

You should see allocatable `nvidia.com/gpu` on each worker.

## GPU Operator ClusterPolicy

The pattern chart `charts/all/nvidia-gpu-config` creates `ClusterPolicy` `aiq-gpu-cluster-policy`.
The GPU Operator reconciles a single cluster-wide policy. On clusters that already have a
`cluster-policy` resource, verify which policy is active (`oc get clusterpolicy`) and merge
`odh-notebook` tolerations into the live policy if GPU pods stay Pending.

## Install order with the Validated Pattern

**Hybrid Lightning (default `PROFILE=bf16-tp4`):**

1. **Phase 0 (this doc).** Provision one four-L4 AWS worker (default); on Azure select a compatible four-GPU SKU and pass `GPU_REPLICAS_AZURE=1`.
2. **Namespaces + secrets.** `./pattern.sh make ensure-pattern-namespaces` then `./pattern.sh make load-secrets`.
3. **Install.** `./pattern.sh make install` — syncs NFD/GPU config, OpenShift AI (KServe), vLLM, then AI-Q.

## References

- [rag-llm-gitops ansible playbooks](https://github.com/validatedpatterns/rag-llm-gitops/tree/main/ansible)
- [OpenShift AI on NVIDIA GPUs](https://ai-on-openshift.io/odh-rhoai/nvidia-gpus/)
- [NVIDIA GPU Operator on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/index.html)
