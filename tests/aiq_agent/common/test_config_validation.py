# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import os

from aiq_agent.common.config_validation import validate_llm_configs


def test_validate_llm_configs_allows_api_key_with_default_syntax(monkeypatch):
    monkeypatch.delenv("VLLM_API_KEY", raising=False)
    config = {
        "llms": {
            "nemotron_lightning_intent_llm": {
                "_type": "openai",
                "api_key": "${VLLM_API_KEY:-local-vllm}",
            },
            "nemotron_ultra_llm": {
                "_type": "nim",
                "api_key": "${NVIDIA_API_KEY}",
            },
        }
    }
    is_valid, missing_keys = validate_llm_configs(config)
    assert is_valid is False
    assert missing_keys == ["NVIDIA_API_KEY"]

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    is_valid, missing_keys = validate_llm_configs(config)
    assert is_valid is True
    assert missing_keys == []


def test_validate_llm_configs_honors_explicit_vllm_api_key_when_set(monkeypatch):
    monkeypatch.setenv("VLLM_API_KEY", "custom-token")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    config = {
        "llms": {
            "nemotron_lightning_intent_llm": {
                "_type": "openai",
                "api_key": "${VLLM_API_KEY:-local-vllm}",
            }
        }
    }
    is_valid, missing_keys = validate_llm_configs(config)
    assert is_valid is True
    assert missing_keys == []
    assert os.getenv("VLLM_API_KEY") == "custom-token"
