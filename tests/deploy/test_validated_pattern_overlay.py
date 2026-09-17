# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
from pathlib import Path

import yaml

from tests.deploy.test_helm_deployment_k8s import render_chart

REPO_ROOT = Path(__file__).resolve().parents[2]
OVERLAY_BASE_PATH = REPO_ROOT / "overrides" / "values-openshift-base.yaml"
OVERLAY_HYBRID_PATH = REPO_ROOT / "overrides" / "values-openshift-hybrid-lightning.yaml"
CHART_HYBRID_CONFIG = REPO_ROOT / "charts" / "aiq-workflow-config" / "files" / "config_hybrid_lightning.yml"
WORKFLOW_CONFIG_CHART = REPO_ROOT / "charts" / "aiq-workflow-config"
VLLM_CHART = REPO_ROOT / "charts" / "all" / "vllm-inference-service"
NFD_CHART = REPO_ROOT / "charts" / "all" / "nfd-config"
NVIDIA_CONFIG_CHART = REPO_ROOT / "charts" / "all" / "nvidia-gpu-config"
RHODS_CHART = REPO_ROOT / "charts" / "all" / "rhods"
DEFAULT_LIGHTNING_BASE_URL = (
    "http://vllm-inference-service-predictor.aiq-inference.svc.cluster.local/v1"
)
VALUES_PROD = REPO_ROOT / "values-prod.yaml"
VALUES_GLOBAL = REPO_ROOT / "values-global.yaml"
VALUES_SECRET_TEMPLATE = REPO_ROOT / "values-secret.yaml.template"
SERVED_MODEL_NAME = "nemotron-3.5-lightning-30b-a3b"
HF_REPO = "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4"


def _render_openshift_overlay(*extra_value_files: str):
    return render_chart(
        "-f",
        str(OVERLAY_BASE_PATH),
        "-f",
        str(extra_value_files[0]),
        namespace="aiq",
    )


def _render_helm_chart(chart_path: Path, release_name: str, namespace: str, *value_files: str) -> list[dict]:
    command = [
        "helm",
        "template",
        release_name,
        str(chart_path),
        "-n",
        namespace,
    ]
    for value_file in value_files:
        command.extend(["-f", value_file])
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def _write_values_file(tmp_path: Path, values: dict) -> str:
    values_file = tmp_path / "values.yaml"
    values_file.write_text(yaml.safe_dump(values), encoding="utf-8")
    return str(values_file)


def _render_vllm_chart(tmp_path: Path) -> list[dict]:
    values_global = yaml.safe_load(VALUES_GLOBAL.read_text(encoding="utf-8"))
    return _render_helm_chart(
        VLLM_CHART,
        "vllm-inference-service",
        "aiq-inference",
        _write_values_file(tmp_path, values_global),
    )


def test_hybrid_config_chart_file_is_valid_yaml():
    assert CHART_HYBRID_CONFIG.is_file()
    config = yaml.safe_load(CHART_HYBRID_CONFIG.read_text(encoding="utf-8"))
    assert config["general"]["front_end"]["_type"] == "aiq_api"
    assert config["llms"]["nemotron_lightning_intent_llm"]["_type"] == "openai"
    assert config["llms"]["nemotron_ultra_llm"]["_type"] == "nim"
    assert config["functions"]["shallow_research_agent"]["llm"] == "nemotron_lightning_agent_llm"
    assert config["functions"]["clarifier_agent"]["llm"] == "nemotron_ultra_llm"
    assert config["llms"]["nemotron_lightning_agent_llm"]["max_tokens"] == 4096
    intent_extra = config["llms"]["nemotron_lightning_intent_llm"]["extra_body"]
    agent_extra = config["llms"]["nemotron_lightning_agent_llm"]["extra_body"]
    assert intent_extra["chat_template_kwargs"]["enable_thinking"] is False
    assert agent_extra["chat_template_kwargs"]["enable_thinking"] is True
    assert agent_extra["thinking_token_budget"] == 2048
    assert config["llms"]["nemotron_lightning_intent_llm"]["model_name"] == SERVED_MODEL_NAME
    intent_base_url = config["llms"]["nemotron_lightning_intent_llm"]["base_url"]
    agent_base_url = config["llms"]["nemotron_lightning_agent_llm"]["base_url"]
    assert intent_base_url == agent_base_url
    assert intent_base_url.startswith("${AIQ_LIGHTNING_BASE_URL:-")
    assert DEFAULT_LIGHTNING_BASE_URL in intent_base_url


def test_hybrid_workflow_model_name_matches_values_global():
    values_global = yaml.safe_load(VALUES_GLOBAL.read_text(encoding="utf-8"))
    config = yaml.safe_load(CHART_HYBRID_CONFIG.read_text(encoding="utf-8"))
    served_name = values_global["global"]["model"]["servedName"]
    assert config["llms"]["nemotron_lightning_intent_llm"]["model_name"] == served_name
    assert config["llms"]["nemotron_lightning_agent_llm"]["model_name"] == served_name


def test_workflow_config_chart_renders_hybrid_configmap():
    manifests = _render_helm_chart(WORKFLOW_CONFIG_CHART, "aiq-workflow-config", "aiq")
    configmaps = [manifest for manifest in manifests if manifest.get("kind") == "ConfigMap"]
    assert len(configmaps) == 1
    assert configmaps[0]["metadata"]["name"] == "aiq-workflow-config"
    assert "config_hybrid_lightning.yml" in configmaps[0]["data"]
    assert "nemotron_lightning_intent_llm" in configmaps[0]["data"]["config_hybrid_lightning.yml"]


def test_nfd_chart_renders_with_chart_defaults(tmp_path: Path):
    manifests = _render_helm_chart(NFD_CHART, "nfd-config", "openshift-nfd")
    kinds = {manifest["kind"] for manifest in manifests}
    assert "NodeFeatureDiscovery" in kinds


def test_gpu_stack_charts_render_expected_kinds(tmp_path: Path):
    values_global = yaml.safe_load(VALUES_GLOBAL.read_text(encoding="utf-8"))
    values_file = _write_values_file(tmp_path, values_global)

    nfd_kinds = {manifest["kind"] for manifest in _render_helm_chart(NFD_CHART, "nfd-config", "openshift-nfd", values_file)}
    nvidia_kinds = {
        manifest["kind"] for manifest in _render_helm_chart(NVIDIA_CONFIG_CHART, "nvidia-config", "nvidia-gpu-operator")
    }
    rhods_kinds = {manifest["kind"] for manifest in _render_helm_chart(RHODS_CHART, "openshift-ai", "redhat-ods-operator")}
    assert "NodeFeatureDiscovery" in nfd_kinds
    assert "ClusterPolicy" in nvidia_kinds
    assert "DataScienceCluster" in rhods_kinds


def test_secret_template_targets_aiq_and_inference_namespaces():
    template = yaml.safe_load(VALUES_SECRET_TEMPLATE.read_text(encoding="utf-8"))
    secrets = {secret["name"]: secret for secret in template["secrets"]}
    aiq_fields = [field["name"] for field in secrets["aiq-credentials"]["fields"]]
    hf_fields = [field["name"] for field in secrets["huggingface-secret"]["fields"]]

    assert template["version"] == "2.0"
    assert secrets["aiq-credentials"]["targetNamespaces"] == ["aiq"]
    assert secrets["huggingface-secret"]["targetNamespaces"] == ["aiq-inference"]
    assert aiq_fields == [
        "DB_USER_NAME",
        "DB_USER_PASSWORD",
        "TAVILY_API_KEY",
        "NVIDIA_API_KEY",
        "VLLM_API_KEY",
    ]
    assert hf_fields == ["hftoken"]


def test_pattern_values_target_umbrella_chart_and_serving_stack():
    values_global = yaml.safe_load(VALUES_GLOBAL.read_text(encoding="utf-8"))
    values_prod = yaml.safe_load(VALUES_PROD.read_text(encoding="utf-8"))

    assert values_global["global"]["singleArgoCD"] is True
    assert values_global["global"]["secretLoader"]["disabled"] is False
    assert values_global["global"]["secretStore"]["backend"] == "none"
    assert values_global["global"]["model"]["hfRepo"] == HF_REPO
    assert values_global["global"]["model"]["servedName"] == SERVED_MODEL_NAME
    assert values_global["global"]["rhoai"]["version"] == "3.5"
    assert values_global["global"]["rhoai"]["vllmImage"].startswith(
        "registry.redhat.io/rhaii/vllm-cuda-rhel9@sha256:"
    )
    assert values_global["global"]["inference"]["namespace"] == "aiq-inference"
    assert values_global["global"]["storageClass"] == ""
    assert values_global["main"]["clusterGroupName"] == "prod"

    applications = values_prod["clusterGroup"]["applications"]
    namespaces = values_prod["clusterGroup"]["namespaces"]
    subscriptions = values_prod["clusterGroup"]["subscriptions"]

    assert "aiq" in namespaces
    assert "aiq-inference" in namespaces
    assert subscriptions["rhoai"]["name"] == "rhods-operator"
    assert applications["openshift-ai"]["path"] == "charts/all/rhods"
    assert applications["nfd-config"]["annotations"]["argocd.argoproj.io/sync-wave"] == "10"
    assert applications["openshift-ai"]["annotations"]["argocd.argoproj.io/sync-wave"] == "15"
    assert applications["vllm-inference-service"]["namespace"] == "aiq-inference"
    assert applications["aiq"]["path"] == "deploy/helm/deployment-k8s"
    assert applications["aiq"]["namespace"] == "aiq"
    assert applications["aiq-workflow-config"]["path"] == "charts/aiq-workflow-config"
    assert "/overrides/values-openshift-base.yaml" in applications["aiq"]["extraValueFiles"]
    assert "/overrides/values-openshift-hybrid-lightning.yaml" in applications["aiq"]["extraValueFiles"]


def test_vllm_chart_renders_served_name_hf_repo_and_model_cache_pvc(tmp_path: Path):
    manifests = _render_vllm_chart(tmp_path)
    kinds = {manifest["kind"] for manifest in manifests}
    assert "InferenceService" in kinds
    assert "ServingRuntime" in kinds
    assert "PersistentVolumeClaim" in kinds
    assert "Route" not in kinds
    assert "HardwareProfile" not in kinds

    pvc = next(m for m in manifests if m["kind"] == "PersistentVolumeClaim")
    assert pvc["spec"]["resources"]["requests"]["storage"] == "80Gi"
    assert "storageClassName" not in pvc["spec"]

    inference_service = next(m for m in manifests if m["kind"] == "InferenceService")
    assert inference_service["metadata"]["name"] == "vllm-inference-service"

    serving_runtime = next(m for m in manifests if m["kind"] == "ServingRuntime")
    assert serving_runtime["metadata"]["name"] == "vllm-inference-service"
    container = serving_runtime["spec"]["containers"][0]
    args = container["args"]
    env = {item["name"]: item.get("value") for item in container["env"]}
    hf_token_ref = next(item for item in container["env"] if item["name"] == "HF_TOKEN")
    volume_names = {volume["name"] for volume in serving_runtime["spec"]["volumes"]}

    assert env["MODEL_ID"] == HF_REPO
    assert container["image"].startswith("registry.redhat.io/rhaii/vllm-cuda-rhel9@sha256:")
    assert container["command"] == ["python", "-m", "vllm.entrypoints.openai.api_server"]
    assert f"--served-model-name={SERVED_MODEL_NAME}" in args
    assert "--quantization=compressed-tensors" not in args
    assert hf_token_ref["valueFrom"]["secretKeyRef"]["optional"] is True
    assert "model-cache" in volume_names

    init_env = {
        item["name"]: item.get("value")
        for item in inference_service["spec"]["predictor"]["initContainers"][0]["env"]
    }
    assert init_env["MODEL_ID"] == HF_REPO
    init_mounts = inference_service["spec"]["predictor"]["initContainers"][0]["volumeMounts"]
    assert init_mounts[0]["name"] == "model-cache"
    assert "volumes" not in inference_service["spec"]["predictor"]


def test_openshift_overlay_mounts_hybrid_config_and_disables_nginx_ingress():
    manifests = _render_openshift_overlay(OVERLAY_HYBRID_PATH)
    deployments = {
        manifest["metadata"]["name"]: manifest for manifest in manifests if manifest.get("kind") == "Deployment"
    }
    ingresses = [manifest for manifest in manifests if manifest.get("kind") == "Ingress"]
    routes = {manifest["metadata"]["name"]: manifest for manifest in manifests if manifest.get("kind") == "Route"}
    pvcs = {
        manifest["metadata"]["name"]: manifest
        for manifest in manifests
        if manifest.get("kind") == "PersistentVolumeClaim"
    }

    backend = deployments["aiq-backend"]["spec"]["template"]["spec"]
    env = {item["name"]: item.get("value") for item in backend["containers"][0]["env"]}
    volume_names = {volume["name"] for volume in backend["volumes"]}
    config_maps = {volume["configMap"]["name"] for volume in backend["volumes"] if volume.get("configMap") is not None}

    assert env["CONFIG_FILE"] == "/app/configs/config_hybrid_lightning.yml"
    assert "NAT_JOB_STORE_DB_URL" in env
    assert volume_names == {"postgres-init", "workflow-config"}
    assert config_maps == {"aiq-postgres-init", "aiq-workflow-config"}
    assert ingresses == []
    assert list(routes) == ["aiq-frontend"]
    frontend_route = routes["aiq-frontend"]
    assert frontend_route["apiVersion"] == "route.openshift.io/v1"
    assert frontend_route["spec"]["to"] == {
        "kind": "Service",
        "name": "aiq-frontend",
        "weight": 100,
    }
    assert frontend_route["spec"]["port"]["targetPort"] == 3000
    assert "host" not in frontend_route["spec"]
    assert frontend_route["spec"]["tls"]["termination"] == "edge"
    assert frontend_route["spec"]["tls"]["insecureEdgeTerminationPolicy"] == "Redirect"
    assert "storageClassName" not in pvcs["aiq-postgres-data"]["spec"]
    assert deployments["aiq-backend"]["metadata"]["namespace"] == "aiq"
