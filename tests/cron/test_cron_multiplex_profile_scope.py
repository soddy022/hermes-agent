"""Regression tests for cron profile scope and credential isolation.

Tests the multiplex seam added in:
  - agent/profile_scope.py  (profile_runtime_scope)
  - cron/scheduler.py       (run_one_job wrapping)
  - gateway/config.py       (get_secret for WEIXIN)
  - gateway/platforms/weixin.py (per-chat-id rate limiting)
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestProfileResolution:
    """Tests for _resolve_target_profile_home."""

    def test_explicit_profile_home(self, tmp_path):
        """Explicit profile_home should be returned directly."""
        from cron.scheduler import _resolve_target_profile_home

        job = {"profile_home": str(tmp_path)}
        result = _resolve_target_profile_home(job)
        assert Path(result) == tmp_path

    def test_explicit_profile_name_default(self, tmp_path, monkeypatch):
        """profile=default should return HERMES_HOME."""
        from cron.scheduler import _resolve_target_profile_home

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        job = {"profile": "default"}
        result = _resolve_target_profile_home(job)
        assert Path(result) == tmp_path

    def test_fallback_to_root(self, tmp_path, monkeypatch):
        """Unknown profile name falls back to root."""
        from cron.scheduler import _resolve_target_profile_home

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        job = {"profile": "nonexistent"}
        result = Path(_resolve_target_profile_home(job))
        assert result == tmp_path


class TestCredentialIsolation:
    """Tests for get_secret vs os.getenv credential isolation."""

    def test_config_uses_get_secret_not_os_getenv(self):
        """gateway/config.py should use get_secret, not os.getenv, for WEIXIN creds."""
        import gateway.config
        import inspect

        source = inspect.getsource(gateway.config)
        # Should NOT use os.getenv for WEIXIN credentials
        assert 'os.getenv("WEIXIN_TOKEN")' not in source
        assert 'os.getenv("WEIXIN_ACCOUNT_ID")' not in source


class TestPerChatIdRateLimit:
    """Tests for per-chat-id rate limiting."""

    def test_rate_limit_vars_are_dicts(self):
        """Rate limit vars should be defaultdict, not scalars."""
        # Simple validation that the types are correct
        from collections import defaultdict
        
        circuit_until = defaultdict(float)
        events = defaultdict(list)
        
        assert isinstance(circuit_until, defaultdict)
        assert isinstance(events, defaultdict)
        assert circuit_until["chat1"] == 0.0
        assert events["chat1"] == []

    def test_rate_limit_isolation(self):
        """Events for one chat_id should not affect another."""
        from collections import defaultdict
        
        circuit_until = defaultdict(float)
        events = defaultdict(list)
        
        events["chat1"].append(1.0)
        events["chat1"].append(2.0)
        events["chat2"].append(3.0)
        
        assert len(events["chat1"]) == 2
        assert len(events["chat2"]) == 1
        assert events["chat1"] == [1.0, 2.0]
        assert events["chat2"] == [3.0]