<!--
SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# GPU worker provisioning (Phase 0)

Phase 0 prepares GPU worker nodes for a future self-hosted RHOAI vLLM stack. The default AI-Q Validated Pattern overlay (MaaS Granite) does not require GPUs. Operator install and vLLM serving charts land in later phases.

This document mirrors [validatedpatterns/rag-llm-gitops GPU_provisioning.md](https://github.com/validatedpatterns/rag-llm-gitops/blob/main/GPU_provisioning.md). AI-Q defaults to **two** `g6.2xlarge` AWS workers (NVIDIA L4). Adjust with Makefile overrides when your quota or model sizing differs.

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
| `GPU_INSTANCE_TYPE` | `g6.2xlarge` | EC2 GPU instance type |
| `GPU_REPLICAS` | `2` | MachineSet replica count |

Example with one larger node instead of two smaller ones:

```bash
./pattern.sh make create-gpu-machineset GPU_REPLICAS=1 GPU_INSTANCE_TYPE=g6.12xlarge
```

Wait until Machines reach `Running` and nodes join the cluster:

```bash
oc get machines -n openshift-machine-api | grep gpu
oc get nodes -l node-role.kubernetes.io/odh-notebook=
```

The playbook applies these conventions (same as rag-llm-gitops):

- Label `node-role.kubernetes.io/odh-notebook`
- Taint `odh-notebook=true:NoSchedule`

Later RHOAI vLLM charts can target these nodes with matching tolerations and affinity.

## Provision GPU workers on Azure

```bash
./pattern.sh make create-gpu-machineset-azure
```

Override `GPU_VM_SIZE`, `GPU_REPLICAS`, or `OVERRIDE_ZONE` as needed. The default Azure SKU remains `Standard_NC8as_T4_v3` from rag-llm-gitops. Pick an NC-series size with enough VRAM for your target model when you move past Phase 0.

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

## Install order with the Validated Pattern

1. **Phase 0 (this doc).** Provision GPU workers.
2. **Default pattern today.** `./pattern.sh make install` deploys AI-Q with the MaaS Granite overlay (no GPU stack required).
3. **Future hybrid Lightning profile.** Re-run install after Phase 1–2 charts add RHOAI operators and vLLM InferenceService.

## References

- [rag-llm-gitops ansible playbooks](https://github.com/validatedpatterns/rag-llm-gitops/tree/main/ansible)
- [OpenShift AI on NVIDIA GPUs](https://ai-on-openshift.io/odh-rhoai/nvidia-gpus/)
- [NVIDIA GPU Operator on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/index.html)
