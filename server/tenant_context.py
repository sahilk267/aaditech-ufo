"""Tenant context middleware and helpers for multi-tenant request scoping."""

from flask import current_app, g, request
from .extensions import db
from .models import Organization


def _default_tenant_slug() -> str:
    return current_app.config.get('DEFAULT_TENANT_SLUG', 'default')


def _tenant_header_name() -> str:
    return current_app.config.get('TENANT_HEADER', 'X-Tenant-Slug')


def get_or_create_default_tenant() -> Organization:
    """Return default tenant and create it if it does not exist."""
    slug = _default_tenant_slug()
    tenant = Organization.query.filter_by(slug=slug).first()
    if tenant:
        return tenant

    tenant = Organization(name='Default Organization', slug=slug, is_active=True)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def resolve_request_tenant() -> Organization:
    """Resolve tenant from request header, fallback to default tenant."""
    requested_slug = request.headers.get(_tenant_header_name(), '').strip().lower()
    if requested_slug:
        tenant = Organization.query.filter_by(slug=requested_slug, is_active=True).first()
        if tenant:
            return tenant

    return get_or_create_default_tenant()


def init_tenant_context(app):
    """Register tenant context middleware with Flask app."""

    @app.before_request
    def _bind_current_tenant():
        g.tenant = resolve_request_tenant()
