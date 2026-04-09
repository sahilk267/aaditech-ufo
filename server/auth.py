# server/auth.py
"""
API Authentication Module
Handles API key validation for secure endpoint access
"""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, UTC
from functools import wraps
from flask import request, jsonify, g, current_app, redirect, session, url_for
import os
import uuid
from dotenv import load_dotenv
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'default-api-key-change-me')
WEB_SESSION_USER_ID_KEY = 'web_user_id'
WEB_SESSION_TENANT_SLUG_KEY = 'web_tenant_slug'
WEB_SESSION_AUTH_VERSION_KEY = 'web_auth_version'
WEB_SESSION_STARTED_AT_KEY = 'web_session_started_at'


def default_auth_policy() -> dict:
    """Return baseline tenant auth policy defaults."""
    return {
        'min_password_length': 8,
        'require_uppercase': False,
        'require_lowercase': False,
        'require_number': False,
        'require_symbol': False,
        'lockout_threshold': 5,
        'lockout_minutes': 15,
        'session_max_age_minutes': 60 * 24 * 7,
        'totp_mfa_enabled': False,
        'oidc_enabled': False,
        'local_admin_fallback_enabled': True,
    }


def get_effective_auth_policy(organization_id: int) -> dict:
    """Merge tenant auth-policy overrides over baseline defaults."""
    from .models import TenantSetting

    policy = default_auth_policy()
    settings = TenantSetting.query.filter_by(organization_id=organization_id).first()
    if settings and isinstance(settings.auth_policy, dict):
        for key, value in settings.auth_policy.items():
            if key in policy:
                policy[key] = value
    return policy


def validate_password_against_policy(password: str, policy: dict) -> list[str]:
    """Validate a plaintext password against an effective auth policy."""
    errors: list[str] = []
    min_length = max(int(policy.get('min_password_length', 8) or 8), 8)
    if len(password) < min_length:
        errors.append(f'Minimum length is {min_length}')
    if bool(policy.get('require_uppercase')) and not any(ch.isupper() for ch in password):
        errors.append('Must include an uppercase letter')
    if bool(policy.get('require_lowercase')) and not any(ch.islower() for ch in password):
        errors.append('Must include a lowercase letter')
    if bool(policy.get('require_number')) and not any(ch.isdigit() for ch in password):
        errors.append('Must include a number')
    if bool(policy.get('require_symbol')) and not any(not ch.isalnum() for ch in password):
        errors.append('Must include a symbol')
    return errors


def is_user_locked_out(user) -> bool:
    """Return whether the user is currently locked out from login."""
    return bool(user.locked_until and user.locked_until > datetime.now(UTC).replace(tzinfo=None))


def record_failed_login(user):
    """Increment failed login attempts and apply tenant-scoped lockout policy."""
    from .extensions import db

    policy = get_effective_auth_policy(user.organization_id)
    threshold = max(int(policy.get('lockout_threshold', 5) or 5), 1)
    minutes = max(int(policy.get('lockout_minutes', 15) or 15), 1)
    user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= threshold:
        user.locked_until = (datetime.now(UTC) + timedelta(minutes=minutes)).replace(tzinfo=None)
    db.session.add(user)
    db.session.commit()


def reset_login_state(user):
    """Reset lockout counters and mark successful login time."""
    from .extensions import db

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    db.session.add(user)
    db.session.commit()


def revoke_user_sessions(user):
    """Invalidate all JWT/browser sessions for a user by rotating token version."""
    from .extensions import db

    user.auth_token_version = int(user.auth_token_version or 1) + 1
    db.session.add(user)
    db.session.commit()
    return user.auth_token_version


def generate_totp_secret() -> str:
    """Create a random base32 TOTP secret."""
    return base64.b32encode(os.urandom(20)).decode('ascii').rstrip('=')


def build_totp_provisioning_uri(secret: str, email: str, issuer: str = 'AADITECH UFO') -> str:
    """Return otpauth provisioning URI for authenticator apps."""
    label = f'{issuer}:{email}'
    return f'otpauth://totp/{label}?secret={secret}&issuer={issuer}'


def _decode_totp_secret(secret: str) -> bytes:
    normalized = str(secret or '').strip().replace(' ', '').upper()
    padding = '=' * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized + padding, casefold=True)


def verify_totp_code(secret: str, code: str, period: int = 30, window: int = 1) -> bool:
    """Verify a 6-digit TOTP code within a small clock-skew window."""
    normalized = ''.join(ch for ch in str(code or '') if ch.isdigit())
    if len(normalized) != 6:
        return False

    secret_bytes = _decode_totp_secret(secret)
    now_counter = int(datetime.now(UTC).timestamp() // period)
    for offset in range(-window, window + 1):
        counter = now_counter + offset
        msg = counter.to_bytes(8, 'big')
        digest = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
        pos = digest[-1] & 0x0F
        binary = ((digest[pos] & 0x7F) << 24) | (digest[pos + 1] << 16) | (digest[pos + 2] << 8) | digest[pos + 3]
        expected = str(binary % 1_000_000).zfill(6)
        if hmac.compare_digest(expected, normalized):
            return True
    return False


def require_api_key(f):
    """
    Decorator to require API key authentication on endpoints.
    
    Usage:
        @app.route('/api/submit_data', methods=['POST'])
        @require_api_key
        def submit_data():
            # Your code here
            pass
    
    Client must send:
        Headers: {'X-API-Key': 'your-api-key'}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({
                'error': 'API key required',
                'message': 'Please provide X-API-Key in request headers'
            }), 401
        
        if api_key != AGENT_API_KEY:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def hash_password(password: str) -> str:
    """Hash plaintext password for storage."""
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Validate plaintext password against hash."""
    return check_password_hash(password_hash, password)


def _jwt_secret() -> str:
    return current_app.config.get('JWT_SECRET_KEY') or current_app.config.get('SECRET_KEY')


def _jwt_algorithm() -> str:
    return current_app.config.get('JWT_ALGORITHM', 'HS256')


def _make_payload(user, token_type: str, expires_minutes: int) -> dict:
    now = datetime.now(UTC)
    return {
        'sub': str(user.id),
        'email': user.email,
        'organization_id': user.organization_id,
        'token_version': int(user.auth_token_version or 1),
        'type': token_type,
        'jti': str(uuid.uuid4()),
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }


def _user_has_permission(user, permission_code: str) -> bool:
    for role in user.roles:
        for permission in role.permissions:
            if permission.code == permission_code:
                return True
    return False


def tenant_feature_flag_enabled(organization_id: int, flag_key: str, default: bool = False) -> bool:
    """Return effective feature-flag state for a tenant, falling back to default."""
    from .models import TenantFeatureFlag

    row = TenantFeatureFlag.query.filter_by(organization_id=organization_id, flag_key=flag_key).first()
    if row is None:
        return bool(default)
    return bool(row.is_enabled)


def tenant_entitlement_enabled(organization_id: int, entitlement_key: str, default: bool = False) -> bool:
    """Return effective entitlement state for a tenant, falling back to default."""
    from .models import TenantEntitlement

    row = TenantEntitlement.query.filter_by(organization_id=organization_id, entitlement_key=entitlement_key).first()
    if row is None:
        return bool(default)
    return bool(row.is_enabled)


def _bind_authenticated_user(user, payload=None):
    g.current_user = user
    g.jwt_payload = payload
    # Authenticated browser/JWT requests should operate in the user's tenant
    # even when tenant middleware ran earlier without auth context.
    g.tenant = user.organization
    return user


def issue_jwt_tokens(user) -> dict:
    """Create access + refresh JWT tokens for a user."""
    access_minutes = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES_MINUTES', 30)
    refresh_minutes = current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES_MINUTES', 60 * 24 * 7)

    access_payload = _make_payload(user, 'access', access_minutes)
    refresh_payload = _make_payload(user, 'refresh', refresh_minutes)

    secret = _jwt_secret()
    algorithm = _jwt_algorithm()
    access_token = jwt.encode(access_payload, secret, algorithm=algorithm)
    refresh_token = jwt.encode(refresh_payload, secret, algorithm=algorithm)

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'expires_in': access_minutes * 60,
    }


def issue_mfa_challenge_token(user) -> dict:
    """Create a short-lived token for completing MFA login."""
    challenge_minutes = current_app.config.get('JWT_MFA_CHALLENGE_EXPIRES_MINUTES', 5)
    payload = _make_payload(user, 'mfa_pending', challenge_minutes)
    token = jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())
    return {
        'challenge_token': token,
        'token_type': 'Bearer',
        'expires_in': challenge_minutes * 60,
    }


def issue_oidc_state_token(tenant_slug: str, provider_id: int, redirect_uri: str = '', web_session: bool = False) -> dict:
    """Create a short-lived token for OIDC login/callback state."""
    expires_minutes = current_app.config.get('OIDC_STATE_EXPIRES_MINUTES', 10)
    now = datetime.now(UTC)
    payload = {
        'type': 'oidc_state',
        'tenant_slug': tenant_slug,
        'provider_id': int(provider_id),
        'redirect_uri': str(redirect_uri or ''),
        'web_session': bool(web_session),
        'nonce': uuid.uuid4().hex,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=int(expires_minutes or 10))).timestamp()),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())
    return {
        'state_token': token,
        'expires_in': int(expires_minutes or 10) * 60,
    }


def decode_jwt_token(token: str, expected_type: str = 'access') -> dict:
    """Decode and validate JWT token payload."""
    payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])
    if payload.get('type') != expected_type:
        raise jwt.InvalidTokenError('Invalid token type')
    return payload


def _extract_bearer_token() -> str:
    auth_header = request.headers.get('Authorization', '').strip()
    if not auth_header.startswith('Bearer '):
        return ''
    return auth_header.split(' ', 1)[1].strip()


def _authenticate_access_token(optional: bool = False):
    """Authenticate access token and return (user, payload, error_response)."""
    token = _extract_bearer_token()
    if not token:
        if optional:
            return None, None, None
        return None, None, (jsonify({'error': 'Authorization required', 'message': 'Bearer token missing'}), 401)

    try:
        payload = decode_jwt_token(token, expected_type='access')
        if _is_token_revoked(payload.get('jti', '')):
            return None, None, (jsonify({'error': 'Token revoked'}), 401)

        from .models import User
        from .extensions import db

        user = db.session.get(User, int(payload['sub']))
        if not user or not user.is_active:
            return None, None, (jsonify({'error': 'Unauthorized', 'message': 'User not found or inactive'}), 401)
        if int(payload.get('token_version', 1)) != int(user.auth_token_version or 1):
            return None, None, (jsonify({'error': 'Token revoked'}), 401)

        return user, payload, None
    except jwt.ExpiredSignatureError:
        return None, None, (jsonify({'error': 'Token expired'}), 401)
    except jwt.InvalidTokenError as exc:
        return None, None, (jsonify({'error': 'Invalid token', 'message': str(exc)}), 401)


def _authenticate_session_user(optional: bool = False):
    """Authenticate browser session user and return (user, payload, error_response)."""
    user_id = session.get(WEB_SESSION_USER_ID_KEY)
    if not user_id:
        if optional:
            return None, None, None
        return None, None, (jsonify({'error': 'Authorization required', 'message': 'Login required'}), 401)

    from .models import User
    from .extensions import db

    user = db.session.get(User, int(user_id))
    if not user or not user.is_active:
        clear_web_session()
        if optional:
            return None, None, None
        return None, None, (jsonify({'error': 'Unauthorized', 'message': 'Session expired'}), 401)

    tenant_slug = session.get(WEB_SESSION_TENANT_SLUG_KEY)
    if tenant_slug and getattr(user.organization, 'slug', None) != tenant_slug:
        clear_web_session()
        if optional:
            return None, None, None
        return None, None, (jsonify({'error': 'Unauthorized', 'message': 'Tenant mismatch'}), 401)

    payload = {
        'sub': str(user.id),
        'organization_id': user.organization_id,
        'token_version': int(user.auth_token_version or 1),
        'type': 'session',
    }
    session_version = int(session.get(WEB_SESSION_AUTH_VERSION_KEY, user.auth_token_version or 1) or 1)
    if session_version != int(user.auth_token_version or 1):
        clear_web_session()
        if optional:
            return None, None, None
        return None, None, (jsonify({'error': 'Unauthorized', 'message': 'Session revoked'}), 401)

    policy = get_effective_auth_policy(user.organization_id)
    max_age_minutes = max(int(policy.get('session_max_age_minutes', 60 * 24 * 7) or (60 * 24 * 7)), 15)
    started_at = int(session.get(WEB_SESSION_STARTED_AT_KEY, 0) or 0)
    now_ts = int(datetime.now(UTC).timestamp())
    if started_at and now_ts - started_at > max_age_minutes * 60:
        clear_web_session()
        if optional:
            return None, None, None
        return None, None, (jsonify({'error': 'Unauthorized', 'message': 'Session expired'}), 401)
    return user, payload, None


def start_web_session(user):
    """Create browser session for authenticated web user."""
    session.permanent = True
    session[WEB_SESSION_USER_ID_KEY] = user.id
    session[WEB_SESSION_TENANT_SLUG_KEY] = user.organization.slug
    session[WEB_SESSION_AUTH_VERSION_KEY] = int(user.auth_token_version or 1)
    session[WEB_SESSION_STARTED_AT_KEY] = int(datetime.now(UTC).timestamp())


def clear_web_session():
    """Clear browser session authentication state."""
    session.pop(WEB_SESSION_USER_ID_KEY, None)
    session.pop(WEB_SESSION_TENANT_SLUG_KEY, None)
    session.pop(WEB_SESSION_AUTH_VERSION_KEY, None)
    session.pop(WEB_SESSION_STARTED_AT_KEY, None)


def init_auth_context(app):
    """Bind browser session user into request globals when present."""

    @app.before_request
    def _load_browser_session_user():
        g.current_user = None
        g.jwt_payload = None

        user, payload, _ = _authenticate_session_user(optional=True)
        if user is not None:
            _bind_authenticated_user(user, payload)


def _is_token_revoked(jti: str) -> bool:
    from .models import RevokedToken
    from .extensions import db
    return db.session.query(RevokedToken.id).filter_by(jti=jti).first() is not None


def revoke_token(payload: dict):
    """Persist token revocation entry for logout/revocation flows."""
    from .models import RevokedToken
    from .extensions import db

    jti = payload.get('jti')
    if not jti:
        return

    exists = db.session.query(RevokedToken.id).filter_by(jti=jti).first()
    if exists:
        return

    exp_ts = payload.get('exp')
    expires_at = datetime.fromtimestamp(exp_ts, UTC) if exp_ts else None

    db.session.add(RevokedToken(jti=jti, token_type=payload.get('type', 'access'), expires_at=expires_at))
    db.session.commit()


def require_jwt_auth(f):
    """Require valid access token and inject authenticated user into request context."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user, payload, error_response = _authenticate_access_token(optional=False)
        if error_response:
            return error_response

        _bind_authenticated_user(user, payload)
        return f(*args, **kwargs)

    return decorated


def require_refresh_token(f):
    """Require valid refresh token for token renewal endpoint."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({'error': 'Authorization required', 'message': 'Refresh token missing'}), 401

        try:
            payload = decode_jwt_token(token, expected_type='refresh')
            if _is_token_revoked(payload.get('jti', '')):
                return jsonify({'error': 'Token revoked'}), 401

            from .models import User
            from .extensions import db

            user = db.session.get(User, int(payload['sub']))
            if not user or not user.is_active:
                return jsonify({'error': 'Unauthorized', 'message': 'User not found or inactive'}), 401
            if int(payload.get('token_version', 1)) != int(user.auth_token_version or 1):
                return jsonify({'error': 'Token revoked'}), 401

            _bind_authenticated_user(user, payload)
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Refresh token expired'}), 401
        except jwt.InvalidTokenError as exc:
            return jsonify({'error': 'Invalid refresh token', 'message': str(exc)}), 401

    return decorated


def require_permission(permission_code: str):
    """Require authenticated user to have a specific permission via roles."""
    def decorator(f):
        @wraps(f)
        @require_jwt_auth
        def wrapped(*args, **kwargs):
            user = g.current_user
            if _user_has_permission(user, permission_code):
                return f(*args, **kwargs)
            return jsonify({'error': 'Forbidden', 'message': f'Missing permission: {permission_code}'}), 403

        return wrapped

    return decorator


def require_api_key_or_permission(permission_code: str):
    """Allow access with valid API key or JWT token with required permission."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            api_key = request.headers.get('X-API-Key')
            if api_key == AGENT_API_KEY:
                return f(*args, **kwargs)

            user, payload, error_response = _authenticate_access_token(optional=True)
            if error_response:
                return error_response

            if user is None:
                user, payload, error_response = _authenticate_session_user(optional=True)
                if error_response:
                    return error_response

            if user is None:
                if api_key:
                    return jsonify({
                        'error': 'Invalid API key',
                        'message': 'The provided API key is invalid'
                    }), 403
                return jsonify({
                    'error': 'Authorization required',
                    'message': 'Provide X-API-Key or Authorization: Bearer <token>'
                }), 401

            _bind_authenticated_user(user, payload)
            if _user_has_permission(user, permission_code):
                return f(*args, **kwargs)

            return jsonify({'error': 'Forbidden', 'message': f'Missing permission: {permission_code}'}), 403

        return wrapped

    return decorator


def require_web_permission(permission_code: str):
    """Require browser session auth for HTML pages and enforce permission."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user, payload, _ = _authenticate_session_user(optional=True)
            if user is None:
                next_url = request.full_path if request.query_string else request.path
                return redirect(url_for('web.login', next=next_url.rstrip('?')))

            _bind_authenticated_user(user, payload)
            if not _user_has_permission(user, permission_code):
                return redirect(url_for('web.forbidden_page'))

            return f(*args, **kwargs)

        return wrapped

    return decorator


def get_api_key():
    """Get the current API key from environment"""
    return AGENT_API_KEY


def validate_api_key(key):
    """
    Validate an API key.
    
    Args:
        key: API key to validate
    
    Returns:
        True if valid, False otherwise
    """
    return key == AGENT_API_KEY
