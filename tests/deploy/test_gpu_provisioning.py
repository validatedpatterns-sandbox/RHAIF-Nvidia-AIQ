"""Check the worker manifest produced by Make's profile-specific provisioning inputs."""

import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "ansible/playbooks/create-gpu-machineset.yaml"
TEMPLATE = ROOT / "ansible/playbooks/templates/gpu-machineset.j2"


def render_worker(variables):
    environment = Environment(undefined=StrictUndefined)
    environment.filters["to_json"] = json.dumps
    return yaml.safe_load(environment.from_string(TEMPLATE.read_text()).render(
        **variables,
        clusterId="test-cluster",
        cloudAvailabilityZone="us-east-2a",
        cloudRegion="us-east-2",
        instanceAmi="ami-test",
        securityGroups=[{"id": "sg-test"}],
        subnets={"id": "subnet-test"},
        tags=[],
    ))


def assert_worker(worker, instance, replicas, gpus, cpu, memory, disk):
    assert worker["spec"]["replicas"] == replicas
    annotations = worker["metadata"]["annotations"]
    assert annotations["machine.openshift.io/GPU"] == str(gpus)
    assert annotations["machine.openshift.io/vCPU"] == str(cpu)
    assert annotations["machine.openshift.io/memoryMb"] == str(memory)
    provider = worker["spec"]["template"]["spec"]["providerSpec"]["value"]
    assert provider["instanceType"] == instance
    assert provider["blockDevices"][0]["ebs"]["volumeSize"] == disk


@pytest.mark.parametrize("overrides,expected", [
    ([], ("g6.12xlarge", 1, 4, 48, 196608, 500)),
    (["PROFILE=bf16-tp4"], ("g6.12xlarge", 1, 4, 48, 196608, 500)),
    (["PROFILE=nvfp4"], ("g6.2xlarge", 1, 1, 8, 32768, 150)),
    (["PROFILE=nvfp4-pp2"], ("g6.2xlarge", 2, 1, 8, 32768, 500)),
    (["GPU_REPLICAS=2", "GPU_ROOT_VOLUME_SIZE=750"], ("g6.12xlarge", 2, 4, 48, 196608, 750)),
])
def test_make_provisioning_renders_profile_hardware(overrides, expected):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("GPU_") and key not in
                   {"PROFILE", "TARGET_VARIANT", "OVERRIDE_ZONE", "MAKEFLAGS", "MAKEOVERRIDES"}}
    result = subprocess.run(
        ["make", "-n", "create-gpu-machineset", *overrides],
        cwd=ROOT, env=environment, check=True, capture_output=True, text=True,
    )
    arguments = shlex.split(result.stdout.split("ansible-playbook ", 1)[1].replace("\\\n", ""))
    variables = dict(item.split("=", 1) for item in arguments[arguments.index("-e") + 1].split())
    assert_worker(render_worker(variables), *expected)


def test_direct_playbook_defaults_render_one_four_l4_worker():
    variables = yaml.safe_load(PLAYBOOK.read_text())[0]["vars"]
    assert_worker(render_worker(variables), "g6.12xlarge", 1, 4, 48, 196608, 500)
