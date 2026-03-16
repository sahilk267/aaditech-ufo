# server/extensions.py
"""
Flask Extensions Initialization
Centralizes all Flask extension setup for modularity and clean imports
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize all extensions (without app binding)
db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)


def init_extensions(app):
    """
    Initialize all Flask extensions with app context.
    
    Args:
        app: Flask application instance
    """
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
