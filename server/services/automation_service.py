"""Automation workflow service for Phase 2 Week 11-12 foundation."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from datetime import datetime, UTC
from typing import Any
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import json

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..extensions import db
from ..models import AutomationWorkflow, ScheduledJob, WorkflowRun


class AutomationService:
    """Business logic for tenant-scoped automation workflows."""

    ALLOWED_TRIGGER_TYPES = {'manual', 'api', 'alert'}
    ALLOWED_ACTION_TYPES = {'service_restart', 'script_execute', 'webhook_call'}
    SAFE_SERVICE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_.@-]{1,64}$')
    ALLOWED_RESTART_BINARIES = {'systemctl', 'service'}
    ALLOWED_STATUS_ADAPTERS = {'windows', 'linux_test_double'}
    ALLOWED_SCRIPT_EXECUTOR_ADAPTERS = {'subprocess', 'linux_test_double'}
    ALLOWED_WEBHOOK_ADAPTERS = {'urllib', 'linux_test_double'}
    ALLOWED_WEBHOOK_METHODS = {'GET', 'POST', 'PUT', 'PATCH'}

    @staticmethod
    def _commit_with_rollback(
        duplicate_field: str | None = None,
        duplicate_message: str | None = None,
        generic_message: str = 'Database operation failed.',
    ) -> dict[str, list[str]]:
        try:
            db.session.commit()
            return {}
        except IntegrityError:
            db.session.rollback()
            if duplicate_field and duplicate_message:
                return {duplicate_field: [duplicate_message]}
            return {'database': ['Constraint violation.']}
        except SQLAlchemyError:
            db.session.rollback()
            return {'database': [generic_message]}

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
    def _build_workflow_run(
        cls,
        organization_id: int,
        workflow: AutomationWorkflow,
        payload: dict[str, Any],
        dry_run: bool,
        executed_at: datetime,
        status: str,
        action_result: dict[str, Any],
        error_reason: str | None = None,
        execution_context: dict[str, Any] | None = None,
        runtime_config: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        execution_context = execution_context or {}
        trigger_source = str(execution_context.get('trigger_source') or 'manual').strip() or 'manual'
        task_id = execution_context.get('task_id')
        scheduled_job_id = execution_context.get('scheduled_job_id')

        return WorkflowRun(
            organization_id=organization_id,
            workflow_id=workflow.id,
            scheduled_job_id=scheduled_job_id,
            trigger_source=trigger_source,
            task_id=str(task_id).strip() if task_id is not None else None,
            dry_run=bool(dry_run),
            status=status,
            error_reason=error_reason,
            input_payload=payload or {},
            action_result=action_result or {},
            execution_metadata={
                'workflow_name': workflow.name,
                'action_type': workflow.action_type,
                'action_config': cls._summarize_action_config(workflow.action_config or {}),
                'runtime_config': cls._summarize_runtime_config(runtime_config or {}),
            },
            executed_at=executed_at.replace(tzinfo=None),
        )

    @staticmethod
    def _summarize_action_config(action_config: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        if action_config.get('service_name'):
            summary['service_name'] = str(action_config.get('service_name'))
        if action_config.get('script_path'):
            summary['script_path'] = str(action_config.get('script_path'))
        if action_config.get('script'):
            summary['script_path'] = str(action_config.get('script'))
        if action_config.get('url'):
            summary['url'] = str(action_config.get('url'))
        if action_config.get('method'):
            summary['method'] = str(action_config.get('method')).upper()
        return summary

    @classmethod
    def _summarize_runtime_config(cls, runtime_config: dict[str, Any]) -> dict[str, Any]:
        return {
            'restart_binary': str(runtime_config.get('restart_binary') or '').strip() or None,
            'script_executor_adapter': str(runtime_config.get('script_executor_adapter') or '').strip() or None,
            'webhook_adapter': str(runtime_config.get('webhook_adapter') or '').strip() or None,
            'allowed_services': cls._coerce_string_list(runtime_config.get('allowed_services')),
            'allowed_script_roots': cls._coerce_string_list(runtime_config.get('allowed_script_roots')),
            'allowed_webhook_hosts': cls._coerce_string_list(runtime_config.get('allowed_webhook_hosts')),
            'command_timeout_seconds': int(runtime_config.get('command_timeout_seconds') or 0),
        }

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
        commit_errors = cls._commit_with_rollback(
            duplicate_field='name',
            duplicate_message='Workflow name already exists for this tenant.',
            generic_message='Failed to persist workflow.',
        )
        if commit_errors:
            return None, commit_errors
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
        execution_context: dict[str, Any] | None = None,
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

        workflow_run: WorkflowRun | None = None

        if not dry_run:
            action_result, action_error = cls._execute_action(
                action_type=workflow.action_type,
                action_config=workflow.action_config or {},
                runtime_config=runtime_config,
            )
            if action_error:
                workflow_run = cls._build_workflow_run(
                    organization_id=organization_id,
                    workflow=workflow,
                    payload=payload,
                    dry_run=False,
                    executed_at=executed_at,
                    status='failed',
                    action_result=action_result,
                    error_reason=action_error,
                    execution_context=execution_context,
                    runtime_config=runtime_config,
                )
                db.session.add(workflow_run)
                commit_errors = cls._commit_with_rollback(generic_message='Failed to persist workflow execution history.')
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
                    'execution_metadata': workflow_run.execution_metadata if workflow_run is not None else {},
                    'workflow_run_id': workflow_run.id if not commit_errors else None,
                    'persistence_errors': commit_errors or None,
                }, 'execution_failed'

        workflow_run = cls._build_workflow_run(
            organization_id=organization_id,
            workflow=workflow,
            payload=payload,
            dry_run=bool(dry_run),
            executed_at=executed_at,
            status='simulated' if dry_run else 'executed',
            action_result=action_result,
            execution_context=execution_context,
            runtime_config=runtime_config,
        )
        db.session.add(workflow_run)

        if not dry_run:
            workflow.last_triggered_at = executed_at.replace(tzinfo=None)
        commit_errors = cls._commit_with_rollback(generic_message='Failed to persist workflow execution state.')
        if commit_errors:
            return {
                'workflow_id': workflow.id,
                'workflow_name': workflow.name,
                'action_type': workflow.action_type,
                'dry_run': bool(dry_run),
                'executed_at': executed_at.isoformat(),
                'action_config': workflow.action_config or {},
                'input_payload': payload,
                'status': 'failed',
                'action_result': action_result,
                'persistence_errors': commit_errors,
            }, 'persistence_failed'

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
            'execution_metadata': workflow_run.execution_metadata if workflow_run is not None else {},
            'workflow_run_id': workflow_run.id if workflow_run is not None else None,
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
            return cls._execute_script(action_config, runtime_config)

        if action_type == 'webhook_call':
            return cls._execute_webhook(action_config, runtime_config)

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

    @staticmethod
    def _coerce_timeout_seconds(value: Any, default: int = 8, minimum: int = 1, maximum: int = 30) -> int:
        """Normalize timeout values to a bounded integer."""
        try:
            timeout_seconds = int(value)
        except (TypeError, ValueError):
            timeout_seconds = default
        return max(minimum, min(timeout_seconds, maximum))

    @staticmethod
    def _coerce_string_list(value: Any) -> list[str]:
        """Normalize comma-separated or list-like config values into a string list."""
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or '').split(',') if item.strip()]

    @staticmethod
    def _resolve_allowed_path(candidate_path: str, allowed_roots: list[str]) -> Path | None:
        """Return resolved path when it stays under an allowed root."""
        candidate = Path(candidate_path).expanduser().resolve(strict=False)
        for root_text in allowed_roots:
            root = Path(root_text).expanduser().resolve(strict=False)
            try:
                candidate.relative_to(root)
                return candidate
            except ValueError:
                continue
        return None

    @staticmethod
    def _coerce_script_args(value: Any) -> tuple[list[str], str | None]:
        """Validate and normalize script arguments for shell-free execution."""
        if value is None:
            return [], None
        if not isinstance(value, list):
            return [], 'script_args_invalid'

        args: list[str] = []
        for item in value[:10]:
            arg = str(item)
            if len(arg) > 200 or any(ch in arg for ch in ['\x00', '\n', '\r']):
                return [], 'script_args_invalid'
            args.append(arg)
        return args, None

    @classmethod
    def _execute_script(
        cls,
        action_config: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Execute an allowlisted script via subprocess or deterministic test double."""
        script_path = str(action_config.get('script_path') or action_config.get('script') or '').strip()
        if not script_path:
            return {'status': 'validation_failed', 'reason': 'script_path_missing'}, 'script_path_missing'

        script_args, args_error = cls._coerce_script_args(action_config.get('args'))
        if args_error:
            return {'status': 'validation_failed', 'reason': args_error}, args_error

        adapter = str(runtime_config.get('script_executor_adapter') or 'subprocess').strip()
        if adapter not in cls.ALLOWED_SCRIPT_EXECUTOR_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        allowed_roots = cls._coerce_string_list(runtime_config.get('allowed_script_roots'))
        if not allowed_roots:
            return {'status': 'policy_blocked', 'reason': 'script_root_not_configured'}, 'script_root_not_configured'

        resolved_script = cls._resolve_allowed_path(script_path, allowed_roots)
        if resolved_script is None:
            return {
                'status': 'policy_blocked',
                'reason': 'script_path_not_allowlisted',
                'script_path': script_path,
            }, 'script_path_not_allowlisted'

        if not resolved_script.is_file():
            return {'status': 'validation_failed', 'reason': 'script_not_found', 'script_path': str(resolved_script)}, 'script_not_found'

        command = [str(resolved_script), *script_args]

        if adapter == 'linux_test_double':
            return {
                'status': 'success',
                'adapter': 'linux_test_double',
                'script_path': str(resolved_script),
                'command': command,
                'stdout': 'configured_test_double',
                'stderr': '',
                'returncode': 0,
            }, None

        timeout_seconds = cls._coerce_timeout_seconds(
            runtime_config.get('command_timeout_seconds'),
            default=8,
        )
        completed = cls._run_script_command(command, timeout_seconds)
        stdout_text = (completed.stdout or '').strip()
        stderr_text = (completed.stderr or '').strip()
        is_success = int(completed.returncode) == 0

        result = {
            'status': 'success' if is_success else 'command_failed',
            'adapter': 'subprocess',
            'script_path': str(resolved_script),
            'command': command,
            'stdout': stdout_text[:500],
            'stderr': stderr_text[:500],
            'returncode': int(completed.returncode),
        }
        return result, None if is_success else 'command_failed'

    @staticmethod
    def _run_script_command(command: list[str], timeout_seconds: int):
        """Execute a script via subprocess with shell disabled."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

    @classmethod
    def _execute_webhook(
        cls,
        action_config: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        """Invoke an allowlisted webhook endpoint."""
        url = str(action_config.get('url') or '').strip()
        if not url:
            return {'status': 'validation_failed', 'reason': 'url_missing'}, 'url_missing'

        parsed = urllib_parse.urlparse(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            return {'status': 'validation_failed', 'reason': 'url_invalid'}, 'url_invalid'

        allowed_hosts = {item.lower() for item in cls._coerce_string_list(runtime_config.get('allowed_webhook_hosts'))}
        if not allowed_hosts:
            return {'status': 'policy_blocked', 'reason': 'webhook_allowlist_not_configured'}, 'webhook_allowlist_not_configured'

        hostname = (parsed.hostname or '').lower()
        if hostname not in allowed_hosts:
            return {
                'status': 'policy_blocked',
                'reason': 'webhook_host_not_allowlisted',
                'host': hostname,
            }, 'webhook_host_not_allowlisted'

        method = str(action_config.get('method') or 'POST').upper()
        if method not in cls.ALLOWED_WEBHOOK_METHODS:
            return {'status': 'validation_failed', 'reason': 'webhook_method_invalid'}, 'webhook_method_invalid'

        headers = action_config.get('headers') or {}
        if not isinstance(headers, dict):
            return {'status': 'validation_failed', 'reason': 'headers_invalid'}, 'headers_invalid'

        adapter = str(runtime_config.get('webhook_adapter') or 'urllib').strip()
        if adapter not in cls.ALLOWED_WEBHOOK_ADAPTERS:
            return {'status': 'policy_blocked', 'reason': 'adapter_not_allowed'}, 'adapter_not_allowed'

        body = action_config.get('body')
        data = None
        normalized_headers = {str(key): str(value) for key, value in headers.items()}
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode('utf-8')
                normalized_headers.setdefault('Content-Type', 'application/json')
            else:
                data = str(body).encode('utf-8')

        if adapter == 'linux_test_double':
            return {
                'status': 'success',
                'adapter': 'linux_test_double',
                'url': url,
                'method': method,
                'host': hostname,
                'status_code': 200,
                'response_body': 'configured_test_double',
            }, None

        timeout_seconds = cls._coerce_timeout_seconds(
            runtime_config.get('webhook_timeout_seconds'),
            default=5,
            maximum=20,
        )
        request_obj = urllib_request.Request(
            url,
            data=data,
            headers=normalized_headers,
            method=method,
        )
        response = cls._perform_webhook_request(request_obj, timeout_seconds)
        response_body = response.read().decode('utf-8', errors='replace').strip()
        status_code = int(getattr(response, 'status', 200))

        result = {
            'status': 'success' if 200 <= status_code < 300 else 'request_failed',
            'adapter': 'urllib',
            'url': url,
            'method': method,
            'host': hostname,
            'status_code': status_code,
            'response_body': response_body[:500],
        }
        return result, None if 200 <= status_code < 300 else 'request_failed'

    @staticmethod
    def _perform_webhook_request(request_obj, timeout_seconds: int):
        """Perform the webhook HTTP request."""
        return urllib_request.urlopen(request_obj, timeout=timeout_seconds)

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

        action_config = payload.get('action_config')
        if isinstance(action_config, dict):
            if action_type == 'script_execute':
                script_path = str(action_config.get('script_path') or action_config.get('script') or '').strip()
                if not script_path:
                    errors.setdefault('action_config.script_path', []).append('Field required for script execution.')
                script_args = action_config.get('args')
                if script_args is not None and not isinstance(script_args, list):
                    errors.setdefault('action_config.args', []).append('Must be a list.')

            if action_type == 'webhook_call':
                url = str(action_config.get('url') or '').strip()
                if not url:
                    errors.setdefault('action_config.url', []).append('Field required for webhook actions.')
                method = action_config.get('method')
                if method is not None and str(method).upper() not in cls.ALLOWED_WEBHOOK_METHODS:
                    errors.setdefault('action_config.method', []).append('Unsupported webhook method.')
                headers = action_config.get('headers')
                if headers is not None and not isinstance(headers, dict):
                    errors.setdefault('action_config.headers', []).append('Must be an object.')

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

    # ------------------------------------------------------------------
    # Scheduled Automation Jobs
    # ------------------------------------------------------------------

    SAFE_CRON_PATTERN = re.compile(
        r'^(\*|[0-9,\-*/]+)\s+(\*|[0-9,\-*/]+)\s+(\*|[0-9,\-*/]+)\s+(\*|[0-9,\-*/]+)\s+(\*|[0-9,\-*/]+)$'
    )

    @classmethod
    def list_scheduled_jobs(cls, organization_id: int) -> list[ScheduledJob]:
        """Return all scheduled jobs for a tenant."""
        return (
            ScheduledJob.query
            .filter_by(organization_id=organization_id)
            .order_by(ScheduledJob.created_at.desc())
            .all()
        )

    @classmethod
    def schedule_job(
        cls,
        organization_id: int,
        payload: dict[str, Any],
        runtime_config: dict[str, Any] | None = None,
    ) -> tuple[ScheduledJob | None, dict[str, list[str]]]:
        """Create a scheduled job if payload is valid."""
        runtime_config = runtime_config or {}
        errors: dict[str, list[str]] = {}

        workflow_id = payload.get('workflow_id')
        if workflow_id is None:
            errors.setdefault('workflow_id', []).append('Field required.')
        else:
            try:
                workflow_id = int(workflow_id)
            except (TypeError, ValueError):
                errors.setdefault('workflow_id', []).append('Must be an integer.')
                workflow_id = None

        cron_expression = str(payload.get('cron_expression') or '').strip()
        if not cron_expression:
            errors.setdefault('cron_expression', []).append('Field required.')
        elif not cls.SAFE_CRON_PATTERN.fullmatch(cron_expression):
            errors.setdefault('cron_expression', []).append('Invalid cron expression format.')

        if errors:
            return None, errors

        # Verify workflow belongs to this tenant
        workflow = AutomationWorkflow.query.filter_by(
            id=workflow_id,
            organization_id=organization_id,
        ).first()
        if workflow is None:
            return None, {'workflow_id': ['Workflow not found or not accessible.']}

        max_jobs = int(runtime_config.get('scheduled_job_max_per_tenant', 50))
        current_count = ScheduledJob.query.filter_by(organization_id=organization_id).count()
        if current_count >= max_jobs:
            return None, {'scheduled_job': [f'Tenant limit of {max_jobs} scheduled jobs reached.']}

        job = ScheduledJob(
            organization_id=organization_id,
            workflow_id=workflow_id,
            cron_expression=cron_expression,
            is_active=bool(payload.get('is_active', True)),
        )
        db.session.add(job)
        commit_errors = cls._commit_with_rollback(generic_message='Failed to persist scheduled job.')
        if commit_errors:
            return None, commit_errors
        return job, {}

    @classmethod
    def trigger_scheduled_jobs(
        cls,
        organization_id: int,
        runtime_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate due scheduled jobs and execute them via configured adapter."""
        runtime_config = runtime_config or {}
        scheduler_adapter = str(
            runtime_config.get('scheduler_adapter') or 'linux_test_double'
        ).strip()

        jobs = (
            ScheduledJob.query
            .filter_by(organization_id=organization_id, is_active=True)
            .all()
        )

        if scheduler_adapter == 'linux_test_double':
            due_job_ids = set(
                int(item)
                for item in str(runtime_config.get('linux_test_double_due_jobs', '')).split(',')
                if str(item).strip().isdigit()
            )
            due_jobs = [job for job in jobs if job.id in due_job_ids]
        else:
            due_jobs = jobs  # In production all active jobs considered due

        triggered: list[dict[str, Any]] = []
        for job in due_jobs:
            workflow = AutomationWorkflow.query.filter_by(
                id=job.workflow_id,
                organization_id=organization_id,
            ).first()
            exec_result = None
            if workflow:
                exec_result, _ = cls.execute_workflow(
                    organization_id,
                    job.workflow_id,
                    runtime_config=runtime_config,
                    execution_context={
                        'trigger_source': 'scheduled',
                        'scheduled_job_id': job.id,
                    },
                )
            job.last_run_at = datetime.now(UTC)
            triggered.append({
                'job_id': job.id,
                'workflow_id': job.workflow_id,
                'cron_expression': job.cron_expression,
                'executed': exec_result is not None,
            })
        commit_errors = cls._commit_with_rollback(generic_message='Failed to persist scheduled job execution state.')
        if commit_errors:
            return {
                'status': 'failed',
                'organization_id': organization_id,
                'adapter': scheduler_adapter,
                'total_active_jobs': len(jobs),
                'due_jobs_count': len(due_jobs),
                'triggered': triggered,
                'errors': commit_errors,
            }

        return {
            'status': 'success',
            'organization_id': organization_id,
            'adapter': scheduler_adapter,
            'total_active_jobs': len(jobs),
            'due_jobs_count': len(due_jobs),
            'triggered': triggered,
        }

    # ------------------------------------------------------------------
    # Self-Healing Infrastructure Loop
    # ------------------------------------------------------------------

    @classmethod
    def trigger_self_healing(
        cls,
        organization_id: int,
        alerts: list[dict[str, Any]] | None,
        runtime_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate alerts → match workflow rules → execute matched workflows.

        When ``dry_run`` is True in runtime_config the workflows are matched
        but NOT executed — safe for testing and preview.
        """
        runtime_config = runtime_config or {}
        dry_run = bool(runtime_config.get('self_healing_dry_run', True))

        if not alerts or not isinstance(alerts, list):
            return {
                'status': 'success',
                'dry_run': dry_run,
                'organization_id': organization_id,
                'matched_workflows': [],
                'triggered_count': 0,
                'skipped_count': 0,
                'reason': 'no_alerts_provided',
            }

        max_loop_depth = int(runtime_config.get('self_healing_max_depth', 10))
        matches = cls.evaluate_alert_triggers(organization_id, alerts)
        matches = matches[:max_loop_depth]

        triggered: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for match in matches:
            workflow_id = match.get('workflow_id')
            if workflow_id is None:
                continue
            if dry_run:
                skipped.append({'workflow_id': workflow_id, 'reason': 'dry_run'})
            else:
                result, err = cls.execute_workflow(
                    organization_id,
                    workflow_id,
                    runtime_config=runtime_config,
                    execution_context={'trigger_source': 'self_heal'},
                )
                triggered.append({
                    'workflow_id': workflow_id,
                    'outcome': 'error' if err else 'success',
                    'error': err,
                })

        return {
            'status': 'success',
            'dry_run': dry_run,
            'organization_id': organization_id,
            'alert_count': len(alerts),
            'matched_workflows': [m.get('workflow_id') for m in matches],
            'triggered_count': len(triggered),
            'skipped_count': len(skipped),
            'triggered': triggered,
            'skipped': skipped,
        }

