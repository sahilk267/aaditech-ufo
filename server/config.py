"""
Configuration classes for different environments
Development, Testing, and Production configurations
"""

import os
from datetime import timedelta


class Config:
    """Base configuration with common settings"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = False
    TESTING = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///toolboxgalaxy.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT = '200/day,50/hour'
    
    # API Security
    API_KEY_HEADER = 'X-API-Key'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request size

    # Multi-tenant routing
    TENANT_HEADER = os.getenv('TENANT_HEADER', 'X-Tenant-Slug')
    DEFAULT_TENANT_SLUG = os.getenv('DEFAULT_TENANT_SLUG', 'default')
    
    # Agent configuration
    AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'default-key-change-this')
    
    # Backup configuration
    BACKUP_DIR = os.getenv('BACKUP_DIR', 'backups/')
    
    # Logging configuration
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


class DevelopmentConfig(Config):
    """Development environment configuration"""
    
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True
    SESSION_COOKIE_SECURE = False
    LOG_LEVEL = 'DEBUG'
    
    # Development database (SQLite)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///toolboxgalaxy.db'
    )


class TestingConfig(Config):
    """Testing environment configuration"""
    
    DEBUG = True
    TESTING = True
    
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Use simpler rate limiting for tests
    RATELIMIT_STORAGE_URL = 'memory://'
    
    # Use simple password hashing for tests
    BCRYPT_LOG_ROUNDS = 4


class ProductionConfig(Config):
    """Production environment configuration"""
    
    DEBUG = False
    TESTING = False
    
    # Enforce secure settings in production
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    LOG_LEVEL = 'INFO'
    
    # Production database must be specified via environment
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://user:password@localhost/aaditech_ufo'
    )
    
    # Use Redis for rate limiting in production
    RATELIMIT_STORAGE_URL = os.getenv(
        'REDIS_URL',
        'redis://localhost:6379/0'
    )


def get_config():
    """Get configuration class based on environment"""
    
    env = os.getenv('FLASK_ENV', 'development').lower()
    
    if env == 'testing':
        return TestingConfig
    elif env == 'production':
        return ProductionConfig
    else:
        return DevelopmentConfig
