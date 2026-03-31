# server/auth.py
"""
API Authentication Module
Handles API key validation for secure endpoint access
"""

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
        'type': 'session',
    }
    return user, payload, None


def start_web_session(user):
    """Create browser session for authenticated web user."""
    session.permanent = True
    session[WEB_SESSION_USER_ID_KEY] = user.id
    session[WEB_SESSION_TENANT_SLUG_KEY] = user.organization.slug


def clear_web_session():
    """Clear browser session authentication state."""
    session.pop(WEB_SESSION_USER_ID_KEY, None)
    session.pop(WEB_SESSION_TENANT_SLUG_KEY, None)


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
