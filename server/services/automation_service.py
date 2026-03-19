"""Automation workflow service for Phase 2 Week 11-12 foundation."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, UTC
from typing import Any

from ..extensions import db
from ..models import AutomationWorkflow


class AutomationService:
    """Business logic for tenant-scoped automation workflows."""

    ALLOWED_TRIGGER_TYPES = {'manual', 'api', 'alert'}
    ALLOWED_ACTION_TYPES = {'service_restart', 'script_execute', 'webhook_call'}
    SAFE_SERVICE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_.@-]{1,64}$')
    ALLOWED_RESTART_BINARIES = {'systemctl', 'service'}
    ALLOWED_STATUS_ADAPTERS = {'windows', 'linux_test_double'}

    @staticmethod
    def list_workflows(organization_id: int) -> list[AutomationWorkflow]:
        """Return all automation workflows for a tenant."""
        return (
            AutomationWorkflow.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationWorkflow.created_at.desc())
            .all()
        )

    @classmethod
    def create_workflow(
        cls,
        organization_id: int,
        payload: dict[str, Any],
    ) -> tuple[AutomationWorkflow | None, dict[str, list[str]]]:
        """Create workflow if payload is valid."""
        errors = cls._validate_payload(payload, partial=False)
        if errors:
            return None, errors

        workflow = AutomationWorkflow(
            organization_id=organization_id,
            name=payload['name'].strip(),
            trigger_type=payload['trigger_type'],
            trigger_conditions=payload.get('trigger_conditions') or {},
            action_type=payload['action_type'],
            action_config=payload.get('action_config') or {},
            is_active=bool(payload.get('is_active', True)),
        )

        db.session.add(workflow)
        db.session.commit()
        return workflow, {}

    @classmethod
    def get_workflow(
        cls,
        organization_id: int,
        workflow_id: int,
    ) -> AutomationWorkflow | None:
        """Return tenant workflow by id."""
        return AutomationWorkflow.query.filter_by(
            id=workflow_id,
            organization_id=organization_id,
        ).first()

    @classmethod
    def evaluate_alert_triggers(
        cls,
        organization_id: int,
        alerts: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Match alert-triggered workflows against input alerts."""
        if not alerts:
            return []

        workflows = (
            AutomationWorkflow.query
            .filter_by(organization_id=organization_id, is_active=True, trigger_type='alert')
            .all()
        )

        matches: list[dict[str, Any]] = []
        for workflow in workflows:
            trigger_conditions = workflow.trigger_conditions or {}
            matched_alerts = cls._filter_alerts(alerts, trigger_conditions)
            if not matched_alerts:
                continue

            matches.append({
                'workflow': workflow.to_dict(),
                'matched_alert_count': len(matched_alerts),
                'matched_alerts': matched_alerts[:5],
                'should_execute': True,
            })

        return matches

    @classmethod
    def execute_workflow(
        cls,
        organization_id: int,
        workflow_id: int,
        payload: dict[str, Any] | None = None,
        dry_run: bool = True,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Execute workflow foundation with dry-run-safe behavior."""
        workflow = cls.get_workflow(organization_id, workflow_id)
        if workflow is None:
            return None, 'not_found'

        if not workflow.is_active:
            return None, 'inactive'

        payload = payload or {}
        runtime_config = runtime_config or {}
        executed_at = datetime.now(UTC)

        action_result: dict[str, Any] = {
            'status': 'simulated' if dry_run else 'executed',
            'details': {},
        }

        if not dry_run:
            action_result, action_error = cls._execute_action(
                action_type=workflow.action_type,
                action_config=workflow.action_config or {},
                runtime_config=runtime_config,
            )
            if action_error:
                return {
                    'workflow_id': workflow.id,
                    'workflow_name': workflow.name,
                    'action_type': workflow.action_type,
                    'dry_run': False,
                    'executed_at': executed_at.isoformat(),
                    'action_config': workflow.action_config or {},
                    'input_payload': payload,
                    'status': 'failed',
                    'action_result': action_result,
                }, 'execution_failed'

        if not dry_run:
            workflow.last_triggered_at = executed_at.replace(tzinfo=None)
            db.session.commit()

        result = {
            'workflow_id': workflow.id,
            'workflow_name': workflow.name,
            'action_type': workflow.action_type,
            'dry_run': bool(dry_run),
            'executed_at': executed_at.isoformat(),
            'action_config': workflow.action_config or {},
            'input_payload': payload,
            'status': 'simulated' if dry_run else 'executed',
            'action_result': action_result,
        }
        return result, None

    @classmethod
    def _execute_action(
        cls,
        action_type: str,
        action_config: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Execute supported action types using policy-guarded handlers."""
        if action_type == 'service_restart':
            return cls._execute_service_restart(action_config, runtime_config)

        if action_type == 'script_execute':
            return {
                'status': 'not_implemented',
                'message': 'Script executor backend pending implementation.',
            }, 'not_implemented'

        if action_type == 'webhook_call':
            return {
                'status': 'not_implemented',
                'message': 'Webhook action backend pending implementation.',
            }, 'not_implemented'

        return {'status': 'unsupported_action'}, 'unsupported_action'

    @classmethod
    def _execute_service_restart(
        cls,
        action_config: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Execute service restart with strict command policy and sanitization."""
        service_name = str(action_config.get('service_name') or '').strip()
        if not service_name:
            return {'status': 'validation_failed', 'reason': 'service_name_missing'}, 'service_name_missing'

        if not cls.SAFE_SERVICE_NAME_PATTERN.fullmatch(service_name):
            return {'status': 'policy_blocked', 'reason': 'service_name_invalid'}, 'service_name_invalid'

        allowed_services = runtime_config.get('allowed_services') or []
        if allowed_services:
            allowed_set = {str(value).strip() for value in allowed_services if str(value).strip()}
            if service_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'service_not_allowlisted',
                    'service_name': service_name,
                }, 'service_not_allowlisted'

        restart_binary = str(runtime_config.get('restart_binary') or 'systemctl').strip()
        if restart_binary not in cls.ALLOWED_RESTART_BINARIES:
            return {'status': 'policy_blocked', 'reason': 'binary_not_allowed'}, 'binary_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        command = cls._build_restart_command(restart_binary, service_name)
        completed = cls._run_service_restart_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        is_success = int(completed.returncode) == 0

        result = {
            'status': 'success' if is_success else 'command_failed',
            'service_name': service_name,
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _build_restart_command(restart_binary: str, service_name: str) -> list[str]:
        """Create restart command while keeping service name as a single argv token."""
        if restart_binary == 'service':
            return ['service', service_name, 'restart']
        return ['systemctl', 'restart', service_name]

    @staticmethod
    def _run_service_restart_command(command: list[str], timeout_seconds: int):
        """Execute restart command with shell disabled for safety."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def get_service_status(
        cls,
        service_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Return service status using configured adapter boundary."""
        runtime_config = runtime_config or {}

        service_name = str(service_name or '').strip()
        if not service_name:
            return {'status': 'validation_failed', 'reason': 'service_name_missing'}, 'service_name_missing'

        if not cls.SAFE_SERVICE_NAME_PATTERN.fullmatch(service_name):
            return {'status': 'policy_blocked', 'reason': 'service_name_invalid'}, 'service_name_invalid'

        allowed_services = runtime_config.get('allowed_services') or []
        if allowed_services:
            allowed_set = {str(value).strip() for value in allowed_services if str(value).strip()}
            if service_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'service_not_allowlisted',
                    'service_name': service_name,
                }, 'service_not_allowlisted'

        adapter = str(runtime_config.get('service_status_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_STATUS_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._query_windows_service_status(service_name, timeout_seconds)

        service_statuses = runtime_config.get('linux_test_double_statuses') or {}
        return cls._query_linux_test_double_status(service_name, service_statuses)

    @classmethod
    def get_service_dependencies(
        cls,
        service_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Return service dependencies using configured adapter boundary."""
        runtime_config = runtime_config or {}

        service_name = str(service_name or '').strip()
        if not service_name:
            return {'status': 'validation_failed', 'reason': 'service_name_missing'}, 'service_name_missing'

        if not cls.SAFE_SERVICE_NAME_PATTERN.fullmatch(service_name):
            return {'status': 'policy_blocked', 'reason': 'service_name_invalid'}, 'service_name_invalid'

        allowed_services = runtime_config.get('allowed_services') or []
        if allowed_services:
            allowed_set = {str(value).strip() for value in allowed_services if str(value).strip()}
            if service_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'service_not_allowlisted',
                    'service_name': service_name,
                }, 'service_not_allowlisted'

        adapter = str(runtime_config.get('service_dependency_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_STATUS_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._query_windows_service_dependencies(service_name, timeout_seconds)

        dependency_map = runtime_config.get('linux_test_double_dependencies') or {}
        return cls._query_linux_test_double_dependencies(service_name, dependency_map)

    @classmethod
    def get_service_failures(
        cls,
        service_name: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Detect service failure state via configured adapter boundary."""
        runtime_config = runtime_config or {}

        service_name = str(service_name or '').strip()
        if not service_name:
            return {'status': 'validation_failed', 'reason': 'service_name_missing'}, 'service_name_missing'

        if not cls.SAFE_SERVICE_NAME_PATTERN.fullmatch(service_name):
            return {'status': 'policy_blocked', 'reason': 'service_name_invalid'}, 'service_name_invalid'

        allowed_services = runtime_config.get('allowed_services') or []
        if allowed_services:
            allowed_set = {str(value).strip() for value in allowed_services if str(value).strip()}
            if service_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'service_not_allowlisted',
                    'service_name': service_name,
                }, 'service_not_allowlisted'

        adapter = str(runtime_config.get('service_failure_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_STATUS_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._query_windows_service_failures(service_name, timeout_seconds)

        failure_map = runtime_config.get('linux_test_double_failures') or {}
        return cls._query_linux_test_double_failures(service_name, failure_map)

    @classmethod
    def _query_windows_service_status(
        cls,
        service_name: str,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Query Windows service status using `sc query` command boundary."""
        command = ['sc', 'query', service_name]
        completed = cls._run_windows_service_query_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        output_text = '\n'.join([part for part in [stdout_text, stderr_text] if part]).upper()

        parsed_state = 'unknown'
        if 'RUNNING' in output_text:
            parsed_state = 'running'
        elif 'STOPPED' in output_text:
            parsed_state = 'stopped'

        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'service_name': service_name,
            'service_state': parsed_state,
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_service_query_command(command: list[str], timeout_seconds: int):
        """Execute Windows service query with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _query_windows_service_dependencies(
        cls,
        service_name: str,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Query Windows service dependencies using `sc qc` command boundary."""
        command = ['sc', 'qc', service_name]
        completed = cls._run_windows_service_dependencies_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()

        dependencies: list[str] = []
        for line in stdout_text.splitlines():
            normalized = line.strip()
            if 'DEPENDENCIES' not in normalized.upper():
                continue

            _, _, value = normalized.partition(':')
            raw_values = [token.strip() for token in value.replace('/', ' ').split() if token.strip()]
            dependencies.extend(raw_values)

        unique_dependencies = sorted(set(dependencies))
        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'service_name': service_name,
            'dependencies': unique_dependencies,
            'dependency_count': len(unique_dependencies),
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_service_dependencies_command(command: list[str], timeout_seconds: int):
        """Execute Windows service dependency query with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _query_windows_service_failures(
        cls,
        service_name: str,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Detect Windows service failure using `sc queryex` boundary."""
        command = ['sc', 'queryex', service_name]
        completed = cls._run_windows_service_failures_command(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        output_text = '\n'.join([part for part in [stdout_text, stderr_text] if part]).upper()

        service_state = 'unknown'
        if 'RUNNING' in output_text:
            service_state = 'running'
        elif 'STOPPED' in output_text:
            service_state = 'stopped'

        failure_reasons: list[str] = []
        if service_state == 'stopped':
            failure_reasons.append('service_stopped')

        exit_code_match = re.search(r'WIN32_EXIT_CODE\s*:\s*(\d+)', output_text)
        if exit_code_match and exit_code_match.group(1) != '0':
            failure_reasons.append(f"win32_exit_code_{exit_code_match.group(1)}")

        failure_detected = len(failure_reasons) > 0
        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'service_name': service_name,
            'service_state': service_state,
            'failure_detected': failure_detected,
            'failure_reasons': failure_reasons,
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_service_failures_command(command: list[str], timeout_seconds: int):
        """Execute Windows service failure query with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @staticmethod
    def _query_linux_test_double_status(
        service_name: str,
        service_statuses: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve service state from deterministic Linux test-double map."""
        mapped_value = str(service_statuses.get(service_name, 'unknown')).strip().lower()
        if mapped_value not in {'running', 'stopped', 'unknown'}:
            mapped_value = 'unknown'

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'service_name': service_name,
            'service_state': mapped_value,
            'source': 'configured_test_double',
        }, None

    @staticmethod
    def _query_linux_test_double_dependencies(
        service_name: str,
        dependency_map: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve dependencies from deterministic Linux test-double map."""
        raw_dependencies = dependency_map.get(service_name, [])
        if isinstance(raw_dependencies, str):
            dependencies = [item.strip() for item in raw_dependencies.split('|') if item.strip()]
        elif isinstance(raw_dependencies, list):
            dependencies = [str(item).strip() for item in raw_dependencies if str(item).strip()]
        else:
            dependencies = []

        dependencies = sorted(set(dependencies))
        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'service_name': service_name,
            'dependencies': dependencies,
            'dependency_count': len(dependencies),
            'source': 'configured_test_double',
        }, None

    @staticmethod
    def _query_linux_test_double_failures(
        service_name: str,
        failure_map: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve failure state from deterministic Linux test-double map."""
        raw_value = failure_map.get(service_name, 'unknown')
        if isinstance(raw_value, list):
            tokens = [str(item).strip() for item in raw_value if str(item).strip()]
        else:
            tokens = [item.strip() for item in str(raw_value).split('|') if item.strip()]

        state_token = (tokens[0].lower() if tokens else 'unknown')
        if state_token in {'failed', 'failure', 'down', 'stopped'}:
            service_state = 'stopped'
            failure_detected = True
            reasons = tokens[1:] if len(tokens) > 1 else ['reported_by_test_double']
        elif state_token in {'healthy', 'running', 'ok'}:
            service_state = 'running'
            failure_detected = False
            reasons = []
        else:
            service_state = 'unknown'
            failure_detected = False
            reasons = []

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'service_name': service_name,
            'service_state': service_state,
            'failure_detected': failure_detected,
            'failure_reasons': reasons,
            'source': 'configured_test_double',
        }, None

    @classmethod
    def _validate_payload(cls, payload: dict[str, Any], partial: bool) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}

        required_fields = ['name', 'trigger_type', 'action_type']
        if not partial:
            for field in required_fields:
                if field not in payload:
                    errors.setdefault(field, []).append('Field required.')

        if 'name' in payload and not str(payload.get('name', '')).strip():
            errors.setdefault('name', []).append('Name cannot be empty.')

        trigger_type = payload.get('trigger_type')
        if trigger_type is not None and trigger_type not in cls.ALLOWED_TRIGGER_TYPES:
            errors.setdefault('trigger_type', []).append('Unsupported trigger type.')

        action_type = payload.get('action_type')
        if action_type is not None and action_type not in cls.ALLOWED_ACTION_TYPES:
            errors.setdefault('action_type', []).append('Unsupported action type.')

        if 'trigger_conditions' in payload and not isinstance(payload.get('trigger_conditions'), dict):
            errors.setdefault('trigger_conditions', []).append('Must be an object.')

        if 'action_config' in payload and not isinstance(payload.get('action_config'), dict):
            errors.setdefault('action_config', []).append('Must be an object.')

        return errors

    @staticmethod
    def _filter_alerts(alerts: list[dict[str, Any]], conditions: dict[str, Any]) -> list[dict[str, Any]]:
        """Apply simple matching logic for alert-trigger conditions."""
        severity_in = conditions.get('severity_in')
        metric_in = conditions.get('metric_in')
        min_actual_value = conditions.get('min_actual_value')

        filtered = alerts

        if isinstance(severity_in, list) and severity_in:
            severity_set = {str(value) for value in severity_in}
            filtered = [alert for alert in filtered if str(alert.get('severity')) in severity_set]

        if isinstance(metric_in, list) and metric_in:
            metric_set = {str(value) for value in metric_in}
            filtered = [alert for alert in filtered if str(alert.get('metric')) in metric_set]

        if min_actual_value is not None:
            try:
                threshold = float(min_actual_value)
                filtered = [
                    alert
                    for alert in filtered
                    if alert.get('actual_value') is not None and float(alert.get('actual_value')) >= threshold
                ]
            except (TypeError, ValueError):
                return []

        min_alert_count = conditions.get('min_alert_count', 1)
        try:
            min_alert_count = int(min_alert_count)
        except (TypeError, ValueError):
            min_alert_count = 1

        if len(filtered) < max(min_alert_count, 1):
            return []

        return filtered

    @classmethod
    def execute_service_command(
        cls,
        service_name: str,
        command_text: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Execute remote command via configured adapter boundary."""
        runtime_config = runtime_config or {}

        service_name = str(service_name or '').strip()
        if not service_name:
            return {'status': 'validation_failed', 'reason': 'service_name_missing'}, 'service_name_missing'

        if not cls.SAFE_SERVICE_NAME_PATTERN.fullmatch(service_name):
            return {'status': 'policy_blocked', 'reason': 'service_name_invalid'}, 'service_name_invalid'

        allowed_services = runtime_config.get('allowed_services') or []
        if allowed_services:
            allowed_set = {str(value).strip() for value in allowed_services if str(value).strip()}
            if service_name not in allowed_set:
                return {
                    'status': 'policy_blocked',
                    'reason': 'service_not_allowlisted',
                    'service_name': service_name,
                }, 'service_not_allowlisted'

        command_text = str(command_text or '').strip()
        if not command_text:
            return {'status': 'validation_failed', 'reason': 'command_text_missing'}, 'command_text_missing'

        if len(command_text) > 1024:
            return {'status': 'policy_blocked', 'reason': 'command_text_too_long'}, 'command_text_too_long'

        adapter = str(runtime_config.get('command_executor_adapter') or 'linux_test_double').strip()
        if adapter not in cls.ALLOWED_STATUS_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        timeout_seconds = runtime_config.get('command_timeout_seconds', 8)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 8
        timeout_seconds = max(1, min(timeout_seconds, 30))

        if adapter == 'windows':
            return cls._execute_windows_service_command(service_name, command_text, timeout_seconds)

        command_outputs = runtime_config.get('linux_test_double_commands') or {}
        return cls._execute_linux_test_double_command(service_name, command_text, command_outputs)

    @classmethod
    def _execute_windows_service_command(
        cls,
        service_name: str,
        command_text: str,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], str | None]:
        """Execute command via Windows PowerShell command boundary."""
        command = ['powershell.exe', '-Command', command_text]
        completed = cls._run_windows_service_command_executor(command, timeout_seconds)

        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()

        is_success = int(completed.returncode) == 0
        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'windows',
            'service_name': service_name,
            'command_text': command_text[:200],
            'command': command,
            'returncode': int(completed.returncode),
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_windows_service_command_executor(command: list[str], timeout_seconds: int):
        """Execute Windows PowerShell command with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @staticmethod
    def _execute_linux_test_double_command(
        service_name: str,
        command_text: str,
        command_outputs: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Resolve command output from deterministic Linux test-double map."""
        key = f"{service_name}:{command_text}"
        raw_output = command_outputs.get(key, '')
        
        if isinstance(raw_output, dict):
            output_data = raw_output
        else:
            output_data = {
                'returncode': 0,
                'stdout': str(raw_output),
                'stderr': '',
            }

        return {
            'status': 'success',
            'adapter': 'linux_test_double',
            'service_name': service_name,
            'command_text': command_text[:200],
            'returncode': int(output_data.get('returncode', 0)),
            'stdout': str(output_data.get('stdout', ''))[:500],
            'stderr': str(output_data.get('stderr', ''))[:500],
            'source': 'configured_test_double',
        }, None
