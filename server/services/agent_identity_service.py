"""Agent identity, enrollment token, and credential issuance helpers."""

from __future__ import annotations

import re
import secrets
from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from ..extensions import db
from ..models import Agent, AgentCredential, AgentEnrollmentToken


class AgentIdentityService:
    """Manage agent enrollment tokens, inventory, and per-agent credentials."""

    @staticmethod
    def _utcnow_naive() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _fingerprint(value: str) -> str:
        return sha256(value.encode('utf-8')).hexdigest()

    @classmethod
    def list_agents(cls, organization_id: int) -> list[Agent]:
        return (
            Agent.query
            .filter_by(organization_id=organization_id)
            .order_by(Agent.created_at.desc())
            .all()
        )

    @classmethod
    def create_enrollment_token(
        cls,
        organization_id: int,
        created_by_user_id: int | None = None,
        intended_hostname_pattern: str | None = None,
        ttl_hours: int = 24,
    ) -> tuple[AgentEnrollmentToken, str]:
        raw_token = urlsafe_b64encode(secrets.token_bytes(24)).decode('ascii').rstrip('=')
        token = AgentEnrollmentToken(
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            token_fingerprint=cls._fingerprint(raw_token),
            intended_hostname_pattern=(intended_hostname_pattern or '').strip() or None,
            expires_at=cls._utcnow_naive() + timedelta(hours=max(int(ttl_hours), 1)),
            status='issued',
        )
        db.session.add(token)
        db.session.commit()
        return token, raw_token

    @classmethod
    def enroll_agent(
        cls,
        payload: dict[str, Any],
        remote_addr: str | None = None,
        credential_ttl_days: int | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, list[str]] | None]:
        enrollment_token = str(payload.get('enrollment_token') or '').strip()
        hostname = str(payload.get('hostname') or '').strip()
        serial_number = str(payload.get('serial_number') or '').strip()
        platform = str(payload.get('platform') or 'unknown').strip() or 'unknown'
        agent_version = str(payload.get('agent_version') or '').strip() or None
        display_name = str(payload.get('display_name') or hostname or serial_number).strip()

        errors: dict[str, list[str]] = {}
        if not enrollment_token:
            errors['enrollment_token'] = ['Field required.']
        if not hostname:
            errors['hostname'] = ['Field required.']
        if not serial_number:
            errors['serial_number'] = ['Field required.']
        if not display_name:
            errors['display_name'] = ['Field required.']
        if errors:
            return None, errors

        token = AgentEnrollmentToken.query.filter_by(
            token_fingerprint=cls._fingerprint(enrollment_token)
        ).first()
        now = cls._utcnow_naive()
        if token is None or token.status != 'issued' or token.expires_at < now:
            return None, {'enrollment_token': ['Invalid or expired token.']}

        pattern = str(token.intended_hostname_pattern or '').strip()
        if pattern and not re.fullmatch(pattern, hostname):
            return None, {'hostname': ['Hostname does not match enrollment policy.']}

        agent = Agent.query.filter_by(
            organization_id=token.organization_id,
            serial_number=serial_number,
        ).first()
        if agent is None:
            agent = Agent(
                organization_id=token.organization_id,
                display_name=display_name,
                hostname=hostname,
                serial_number=serial_number,
                platform=platform,
                agent_version=agent_version,
            )
            db.session.add(agent)
            db.session.flush()
        else:
            agent.display_name = display_name
            agent.hostname = hostname
            agent.platform = platform
            agent.agent_version = agent_version

        for credential in agent.credentials:
            if credential.status == 'active':
                credential.status = 'superseded'
                credential.revoked_at = now
                credential.rotation_reason = 're_enrollment'

        raw_credential = urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii').rstrip('=')
        expires_at = None
        if credential_ttl_days:
            expires_at = now + timedelta(days=max(int(credential_ttl_days), 1))

        credential = AgentCredential(
            agent_id=agent.id,
            credential_fingerprint=cls._fingerprint(raw_credential),
            issued_at=now,
            expires_at=expires_at,
            status='active',
        )
        db.session.add(credential)

        token.status = 'used'
        token.used_at = now
        agent.enrollment_state = 'active'
        agent.trust_state = 'trusted'
        agent.last_seen_at = now
        agent.last_ip = remote_addr
        agent.credential_rotated_at = now
        db.session.commit()

        return {
            'agent': agent.to_dict(),
            'credential': {
                'token': raw_credential,
                'issued_at': credential.issued_at.isoformat() if credential.issued_at else None,
                'expires_at': credential.expires_at.isoformat() if credential.expires_at else None,
                'fingerprint': credential.credential_fingerprint,
            },
        }, None
