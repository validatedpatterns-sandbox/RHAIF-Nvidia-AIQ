# BF16 with tensor parallel 4 on one AWS g6.12xlarge (four NVIDIA L4 GPUs).
GPU_INSTANCE_TYPE ?= g6.12xlarge
GPU_REPLICAS ?= 1
GPU_COUNT ?= 4
GPU_VCPU ?= 48
GPU_MEMORY_MB ?= 196608
GPU_ROOT_VOLUME_SIZE ?= 500
# The generic Azure T4 worker cannot run this four-GPU profile.
GPU_VM_SIZE_REQUIRED := true
GPU_SKU_REQUIREMENT := a SKU with four GPUs suitable for BF16 TP=4
