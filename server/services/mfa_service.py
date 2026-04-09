"""TOTP MFA enrollment and verification helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..extensions import db
from ..models import UserTotpFactor
from .tenant_secret_service import TenantSecretService


class MfaService:
    """Handle encrypted TOTP factor lifecycle for users."""

    @staticmethod
    def _utcnow_naive() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    @classmethod
    def get_factor(cls, user_id: int, organization_id: int) -> UserTotpFactor | None:
        return UserTotpFactor.query.filter_by(user_id=user_id, organization_id=organization_id).first()

    @classmethod
    def create_or_rotate_pending_factor(
        cls,
        user_id: int,
        organization_id: int,
        secret: str,
        config: dict[str, Any],
    ) -> UserTotpFactor:
        factor = cls.get_factor(user_id, organization_id)
        if factor is None:
            factor = UserTotpFactor(
                user_id=user_id,
                organization_id=organization_id,
                secret_ciphertext=TenantSecretService.encrypt_value(secret, config),
                status='pending',
            )
        else:
            factor.secret_ciphertext = TenantSecretService.encrypt_value(secret, config)
            factor.status = 'pending'
            factor.verified_at = None
            factor.last_used_at = None
            factor.disabled_at = None
        db.session.add(factor)
        db.session.commit()
        return factor

    @classmethod
    def decrypt_secret(cls, factor: UserTotpFactor, config: dict[str, Any]) -> str:
        return TenantSecretService.decrypt_value(factor.secret_ciphertext, config)

    @classmethod
    def activate_factor(cls, factor: UserTotpFactor) -> UserTotpFactor:
        factor.status = 'active'
        factor.verified_at = cls._utcnow_naive()
        factor.last_used_at = factor.verified_at
        db.session.add(factor)
        db.session.commit()
        return factor

    @classmethod
    def mark_used(cls, factor: UserTotpFactor) -> None:
        factor.last_used_at = cls._utcnow_naive()
        db.session.add(factor)
        db.session.commit()

    @classmethod
    def disable_factor(cls, factor: UserTotpFactor) -> UserTotpFactor:
        factor.status = 'disabled'
        factor.disabled_at = cls._utcnow_naive()
        db.session.add(factor)
        db.session.commit()
        return factor
