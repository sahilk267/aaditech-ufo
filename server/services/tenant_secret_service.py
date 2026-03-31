"""Tenant-scoped encrypted secret storage helpers."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from cryptography.fernet import Fernet

from ..extensions import db
from ..models import TenantSecret


class TenantSecretService:
    """Create, rotate, revoke, and decrypt tenant secrets via a stable service boundary."""

    @staticmethod
    def _utcnow_naive() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _derive_key(config: dict[str, Any]) -> bytes:
        configured = str(config.get('TENANT_SECRET_ENCRYPTION_KEY') or '').strip()
        if configured:
            return configured.encode('ascii')

        fallback_seed = str(
            config.get('SECRET_KEY')
            or config.get('JWT_SECRET_KEY')
            or 'tenant-secret-dev-fallback'
        )
        digest = sha256(fallback_seed.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest)

    @classmethod
    def _fernet(cls, config: dict[str, Any]) -> Fernet:
        return Fernet(cls._derive_key(config))

    @classmethod
    def encrypt_value(cls, raw_value: str, config: dict[str, Any]) -> str:
        return cls._fernet(config).encrypt(raw_value.encode('utf-8')).decode('ascii')

    @classmethod
    def decrypt_value(cls, ciphertext: str, config: dict[str, Any]) -> str:
        return cls._fernet(config).decrypt(ciphertext.encode('ascii')).decode('utf-8')

    @classmethod
    def list_secrets(cls, organization_id: int) -> list[TenantSecret]:
        return (
            TenantSecret.query
            .filter_by(organization_id=organization_id)
            .order_by(TenantSecret.created_at.desc())
            .all()
        )

    @classmethod
    def create_secret(
        cls,
        organization_id: int,
        payload: dict[str, Any],
        config: dict[str, Any],
        created_by_user_id: int | None = None,
    ) -> tuple[TenantSecret | None, dict[str, list[str]] | None]:
        secret_type = str(payload.get('secret_type') or '').strip()
        name = str(payload.get('name') or '').strip()
        secret_value = str(payload.get('secret_value') or '').strip()
        errors: dict[str, list[str]] = {}
        if not secret_type:
            errors['secret_type'] = ['Field required.']
        if not name:
            errors['name'] = ['Field required.']
        if not secret_value:
            errors['secret_value'] = ['Field required.']
        if errors:
            return None, errors

        existing = TenantSecret.query.filter_by(
            organization_id=organization_id,
            secret_type=secret_type,
            name=name,
        ).first()
        if existing is not None:
            return None, {'name': ['Secret already exists for this type.']}

        secret = TenantSecret(
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            secret_type=secret_type,
            name=name,
            ciphertext=cls.encrypt_value(secret_value, config),
            status='active',
        )
        db.session.add(secret)
        db.session.commit()
        return secret, None

    @classmethod
    def rotate_secret(
        cls,
        organization_id: int,
        secret_id: int,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> tuple[TenantSecret | None, dict[str, list[str]] | None, str | None]:
        secret = TenantSecret.query.filter_by(id=secret_id, organization_id=organization_id).first()
        if secret is None:
            return None, None, 'not_found'

        secret_value = str(payload.get('secret_value') or '').strip()
        if not secret_value:
            return None, {'secret_value': ['Field required.']}, None

        secret.ciphertext = cls.encrypt_value(secret_value, config)
        secret.rotated_at = cls._utcnow_naive()
        secret.status = 'active'
        db.session.commit()
        return secret, None, None

    @classmethod
    def revoke_secret(cls, organization_id: int, secret_id: int) -> bool:
        secret = TenantSecret.query.filter_by(id=secret_id, organization_id=organization_id).first()
        if secret is None:
            return False
        secret.status = 'revoked'
        secret.updated_at = cls._utcnow_naive()
        db.session.commit()
        return True
