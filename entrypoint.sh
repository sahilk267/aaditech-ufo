#!/bin/bash
set -e
set -o pipefail

# Wait for any services to be ready
sleep 2

# Apply migrations and seed baseline data
if ! flask --app server.app db upgrade; then
    echo "WARNING: Alembic upgrade failed or did not complete; falling back to schema initialization"
fi

python << 'PYTHON_EOF'
from sqlalchemy import inspect, text
from server.app import app
from server.extensions import db
from server.models import Organization, User, Role, Permission
from server.auth import hash_password

required_permissions = [
    ('tenant.manage', 'Manage tenant settings and users'),
    ('dashboard.view', 'View dashboard data'),
    ('system.submit', 'Submit or refresh local system data'),
    ('backup.manage', 'Create and restore backups'),
    ('automation.manage', 'Create and execute automation workflows'),
]

with app.app_context():
    inspector = inspect(db.engine)
    missing_schema = []
    if not inspector.has_table('organizations'):
        missing_schema.append('organizations')
    if not inspector.has_table('alembic_version'):
        missing_schema.append('alembic_version')
    if missing_schema:
        print(f"WARNING: Missing expected schema objects: {missing_schema}. Applying fallback create_all() and stamping Alembic head.")
        db.create_all()
        db.session.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(255) NOT NULL)"
        ))
        db.session.execute(text("DELETE FROM alembic_version"))
        db.session.execute(text(
            "INSERT INTO alembic_version (version_num) VALUES ('025_oidc_external_maturity')"
        ))
        db.session.commit()
        print("Fallback schema creation and Alembic stamp complete")

    # Check if default organization exists
    org = Organization.query.filter_by(slug='default').first()
    if not org:
        org = Organization(
            name='Default Organization',
            slug='default',
            is_active=True
        )
        db.session.add(org)
        db.session.commit()
        print("Created default organization")
    
    # Create admin role if it doesn't exist (prefer canonical lowercase name)
    admin_role = Role.query.filter_by(name='admin', organization_id=org.id).first()
    if not admin_role:
        admin_role = Role.query.filter_by(name='Admin', organization_id=org.id).first()
    if not admin_role:
        admin_role = Role(
            organization_id=org.id,
            name='admin',
            description='Full system access',
            is_system=True
        )
        db.session.add(admin_role)
        db.session.commit()
        print("Created admin role")

    # Ensure role has required permissions
    existing_codes = {permission.code for permission in admin_role.permissions}
    permissions_added = 0
    for code, description in required_permissions:
        permission = Permission.query.filter_by(code=code).first()
        if not permission:
            permission = Permission(code=code, description=description)
            db.session.add(permission)
            db.session.flush()
        if code not in existing_codes:
            admin_role.permissions.append(permission)
            permissions_added += 1
    if permissions_added:
        db.session.commit()
        print(f"Added {permissions_added} admin permissions")
    
    # Create demo user if it doesn't exist
    user = User.query.filter_by(email='admin@toolboxgalaxy.local').first()
    if not user:
        user = User(
            organization_id=org.id,
            email='admin@toolboxgalaxy.local',
            full_name='Admin User',
            password_hash=hash_password('Admin123!'),
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        print("Created admin user")

    # Ensure user is linked to admin role
    if admin_role not in user.roles:
        user.roles.append(admin_role)
        db.session.commit()
        print("Linked admin role to admin user")
    
    print("Database initialization complete!")
PYTHON_EOF

# Start Flask
echo "Starting Flask application..."
exec flask --app server.app run --host 0.0.0.0 --port 5000
