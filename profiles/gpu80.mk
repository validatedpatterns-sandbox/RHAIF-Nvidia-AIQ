# 80 GiB class (A100 or H100). No single default SKU; the MachineSet targets require one.
GPU_INSTANCE_TYPE_REQUIRED := true
GPU_VM_SIZE_REQUIRED := true
GPU_REPLICAS ?= 1
