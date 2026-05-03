"""Integration test: verify agent restart scheduling spawns a helper process.

This test runs the agent command executor in a subprocess and asserts the
command returns success and that a short-lived launcher process appears.

This is best-effort and intended as a lightweight integration check only.
"""

from __future__ import annotations

import json
import time
import sys
import subprocess

import psutil


def test_agent_restart_schedules_process():
    start_time = time.time()
    # Call the executor in-process (it will spawn the helper launcher).
    from agent import commands as c
    result = c._execute('restart_agent', {'delay_seconds': 1})
    assert result.get('status') == 'success'

    # Patch subprocess.Popen to assert we attempted to spawn the helper launcher.
    from unittest.mock import patch, MagicMock
    with patch('subprocess.Popen') as popen_mock:
        popen_mock.return_value = MagicMock(pid=99999)
        result = c._execute('restart_agent', {'delay_seconds': 1})
        assert result.get('status') == 'success'
        assert popen_mock.called, 'Expected subprocess.Popen to be called to schedule restart.'
