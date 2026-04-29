"""Seed a default admin user for the `default` tenant.

Usage:
    python -m scripts.seed_default_admin
    python -m scripts.seed_default_admin --email admin@example.com --password 'YourPass!' --tenant default

Defaults (overridable via env vars or CLI):
    SEED_ADMIN_TENANT_SLUG   default
    SEED_ADMIN_TENANT_NAME   Default Tenant
    SEED_ADMIN_EMAIL         admin@example.com
    SEED_ADMIN_PASSWORD      ChangeMe123!
    SEED_ADMIN_FULL_NAME     Default Admin

The script is idempotent: re-running it will reuse the tenant/role and
either create the user or reset its password to the requested value.
"""

from __future__ import annotations

import argparse
import os
import sys

from server.app import create_app
from server.auth import hash_password
from server.extensions import db
from server.models import Organization, User
from server.blueprints.api import _get_or_create_default_admin_role


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a default admin user.")
    parser.add_argument("--tenant", default=os.environ.get("SEED_ADMIN_TENANT_SLUG", "default"))
    parser.add_argument("--tenant-name", default=os.environ.get("SEED_ADMIN_TENANT_NAME", "Default Tenant"))
    parser.add_argument("--email", default=os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com"))
    parser.add_argument("--password", default=os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe123!"))
    parser.add_argument("--full-name", default=os.environ.get("SEED_ADMIN_FULL_NAME", "Default Admin"))
    return parser.parse_args()


def seed(tenant_slug: str, tenant_name: str, email: str, password: str, full_name: str) -> dict:
    org = Organization.query.filter_by(slug=tenant_slug).first()
    org_created = False
    if not org:
        org = Organization(name=tenant_name, slug=tenant_slug, is_active=True)
        db.session.add(org)
        db.session.flush()
        org_created = True

    admin_role = _get_or_create_default_admin_role(org.id)

    user = User.query.filter_by(organization_id=org.id, email=email).first()
    user_created = False
    password_reset = False
    if not user:
        user = User(
            organization_id=org.id,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        user_created = True
    else:
        user.password_hash = hash_password(password)
        user.is_active = True
        user.failed_login_attempts = 0
        user.locked_until = None
        password_reset = True

    if admin_role not in user.roles:
        user.roles.append(admin_role)

    db.session.commit()

    return {
        "tenant_slug": org.slug,
        "tenant_id": org.id,
        "tenant_created": org_created,
        "user_id": user.id,
        "user_email": user.email,
        "user_created": user_created,
        "password_reset": password_reset,
        "role": admin_role.name,
    }


def main() -> int:
    args = parse_args()
    app = create_app()
    with app.app_context():
        result = seed(
            tenant_slug=args.tenant,
            tenant_name=args.tenant_name,
            email=args.email,
            password=args.password,
            full_name=args.full_name,
        )

    print("Default admin seed complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()
    print("Login at /login with:")
    print(f"  Tenant Slug: {result['tenant_slug']}")
    print(f"  Email:       {result['user_email']}")
    print(f"  Password:    {args.password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
