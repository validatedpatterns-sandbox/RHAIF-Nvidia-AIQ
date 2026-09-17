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

from pathlib import Path

import yaml

from tests.deploy.test_helm_deployment_k8s import render_chart

REPO_ROOT = Path(__file__).resolve().parents[2]
OVERLAY_PATH = REPO_ROOT / "overrides" / "values-aiq-openshift.yaml"
CHART_MAAS_CONFIG = REPO_ROOT / "charts" / "aiq-maas-config" / "files" / "config_maas_granite.yml"
VALUES_PROD = REPO_ROOT / "values-prod.yaml"
VALUES_GLOBAL = REPO_ROOT / "values-global.yaml"
VALUES_SECRET_TEMPLATE = REPO_ROOT / "values-secret.yaml.template"


def test_maas_config_chart_file_is_valid_yaml():
    assert CHART_MAAS_CONFIG.is_file()
    config = yaml.safe_load(CHART_MAAS_CONFIG.read_text(encoding="utf-8"))
    assert config["general"]["front_end"]["_type"] == "aiq_api"


def test_secret_template_targets_aiq_credentials_in_aiq():
    template = yaml.safe_load(VALUES_SECRET_TEMPLATE.read_text(encoding="utf-8"))
    secret = template["secrets"][0]
    field_names = [field["name"] for field in secret["fields"]]

    assert template["version"] == "2.0"
    assert secret["name"] == "aiq-credentials"
    assert secret["targetNamespaces"] == ["aiq"]
    assert field_names == [
        "DB_USER_NAME",
        "DB_USER_PASSWORD",
        "NVIDIA_API_KEY",
        "TAVILY_API_KEY",
    ]


def test_pattern_values_target_umbrella_chart_and_aiq():
    values_global = yaml.safe_load(VALUES_GLOBAL.read_text(encoding="utf-8"))
    values_prod = yaml.safe_load(VALUES_PROD.read_text(encoding="utf-8"))

    assert values_global["global"]["singleArgoCD"] is True
    assert values_global["global"]["secretLoader"]["disabled"] is False
    assert values_global["global"]["secretStore"]["backend"] == "none"
    assert values_global["main"]["clusterGroupName"] == "prod"

    applications = values_prod["clusterGroup"]["applications"]
    assert "aiq" in values_prod["clusterGroup"]["namespaces"]
    assert applications["aiq"]["path"] == "deploy/helm/deployment-k8s"
    assert applications["aiq"]["namespace"] == "aiq"
    assert applications["aiq-maas-config"]["path"] == "charts/aiq-maas-config"
    assert "/overrides/values-aiq-openshift.yaml" in applications["aiq"]["extraValueFiles"]


def test_openshift_overlay_mounts_maas_config_and_disables_nginx_ingress():
    manifests = render_chart("-f", str(OVERLAY_PATH), namespace="aiq")
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

    assert env["CONFIG_FILE"] == "/app/configs/config_maas_granite.yml"
    assert "NAT_JOB_STORE_DB_URL" in env
    assert volume_names == {"postgres-init", "maas-config"}
    assert config_maps == {"aiq-postgres-init", "aiq-maas-config"}
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
