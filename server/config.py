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

    # Redis + queue (Phase 1 Week 8 foundation)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
    QUEUE_ENABLE_BEAT = os.getenv('QUEUE_ENABLE_BEAT', 'True').lower() == 'true'
    AUDIT_RETENTION_DAYS = int(os.getenv('AUDIT_RETENTION_DAYS', '90'))

    # API gateway readiness
    ENABLE_PROXY_FIX = os.getenv('ENABLE_PROXY_FIX', 'True').lower() == 'true'
    PROXY_FIX_X_FOR = int(os.getenv('PROXY_FIX_X_FOR', '1'))
    PROXY_FIX_X_PROTO = int(os.getenv('PROXY_FIX_X_PROTO', '1'))
    PROXY_FIX_X_HOST = int(os.getenv('PROXY_FIX_X_HOST', '1'))
    PROXY_FIX_X_PORT = int(os.getenv('PROXY_FIX_X_PORT', '1'))
    PROXY_FIX_X_PREFIX = int(os.getenv('PROXY_FIX_X_PREFIX', '1'))
    
    # API Security
    API_KEY_HEADER = 'X-API-Key'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request size

    # Multi-tenant routing
    TENANT_HEADER = os.getenv('TENANT_HEADER', 'X-Tenant-Slug')
    DEFAULT_TENANT_SLUG = os.getenv('DEFAULT_TENANT_SLUG', 'default')
    
    # Agent configuration
    AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'default-key-change-this')

    # JWT configuration (Week 6)
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_MINUTES', '30'))
    JWT_REFRESH_TOKEN_EXPIRES_MINUTES = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES_MINUTES', str(60 * 24 * 7)))

    # Alert notification settings (Phase 2 Week 9-10)
    ALERT_EMAIL_ENABLED = os.getenv('ALERT_EMAIL_ENABLED', 'False').lower() == 'true'
    ALERT_EMAIL_FROM = os.getenv('ALERT_EMAIL_FROM', 'alerts@aaditech.local')
    ALERT_EMAIL_TO = os.getenv('ALERT_EMAIL_TO', '')
    ALERT_SMTP_HOST = os.getenv('ALERT_SMTP_HOST', 'localhost')
    ALERT_SMTP_PORT = int(os.getenv('ALERT_SMTP_PORT', '25'))
    ALERT_WEBHOOK_ENABLED = os.getenv('ALERT_WEBHOOK_ENABLED', 'False').lower() == 'true'
    ALERT_WEBHOOK_URL = os.getenv('ALERT_WEBHOOK_URL', '')
    ALERT_NOTIFICATION_EMAIL_RETRIES = int(os.getenv('ALERT_NOTIFICATION_EMAIL_RETRIES', '2'))
    ALERT_NOTIFICATION_WEBHOOK_RETRIES = int(os.getenv('ALERT_NOTIFICATION_WEBHOOK_RETRIES', '2'))
    ALERT_DEDUP_ENABLED = os.getenv('ALERT_DEDUP_ENABLED', 'True').lower() == 'true'
    ALERT_ESCALATION_REPEAT_THRESHOLD = int(os.getenv('ALERT_ESCALATION_REPEAT_THRESHOLD', '3'))

    # Automation settings (Phase 2 Week 11-12)
    AUTOMATION_DEFAULT_DRY_RUN = os.getenv('AUTOMATION_DEFAULT_DRY_RUN', 'True').lower() == 'true'
    AUTOMATION_ALLOWED_SERVICES = os.getenv('AUTOMATION_ALLOWED_SERVICES', '')
    AUTOMATION_SERVICE_RESTART_BINARY = os.getenv('AUTOMATION_SERVICE_RESTART_BINARY', 'systemctl')
    AUTOMATION_COMMAND_TIMEOUT_SECONDS = int(os.getenv('AUTOMATION_COMMAND_TIMEOUT_SECONDS', '8'))
    AUTOMATION_SERVICE_STATUS_ADAPTER = os.getenv('AUTOMATION_SERVICE_STATUS_ADAPTER', 'linux_test_double')
    AUTOMATION_LINUX_SERVICE_STATUS_TEST_DOUBLE = os.getenv('AUTOMATION_LINUX_SERVICE_STATUS_TEST_DOUBLE', '')
    AUTOMATION_SERVICE_DEPENDENCY_ADAPTER = os.getenv('AUTOMATION_SERVICE_DEPENDENCY_ADAPTER', 'linux_test_double')
    AUTOMATION_LINUX_SERVICE_DEPENDENCY_TEST_DOUBLE = os.getenv('AUTOMATION_LINUX_SERVICE_DEPENDENCY_TEST_DOUBLE', '')
    AUTOMATION_SERVICE_FAILURE_ADAPTER = os.getenv('AUTOMATION_SERVICE_FAILURE_ADAPTER', 'linux_test_double')
    AUTOMATION_LINUX_SERVICE_FAILURE_TEST_DOUBLE = os.getenv('AUTOMATION_LINUX_SERVICE_FAILURE_TEST_DOUBLE', '')
    AUTOMATION_COMMAND_EXECUTOR_ADAPTER = os.getenv('AUTOMATION_COMMAND_EXECUTOR_ADAPTER', 'linux_test_double')
    AUTOMATION_LINUX_COMMAND_EXECUTOR_TEST_DOUBLE = os.getenv('AUTOMATION_LINUX_COMMAND_EXECUTOR_TEST_DOUBLE', '')
    LOG_INGESTION_ADAPTER = os.getenv('LOG_INGESTION_ADAPTER', 'linux_test_double')
    LOG_INGESTION_ALLOWED_SOURCES = os.getenv('LOG_INGESTION_ALLOWED_SOURCES', '')
    LOG_LINUX_INGESTION_TEST_DOUBLE = os.getenv('LOG_LINUX_INGESTION_TEST_DOUBLE', '')
    LOG_INGESTION_MAX_ENTRIES = int(os.getenv('LOG_INGESTION_MAX_ENTRIES', '25'))
    LOG_EVENT_QUERY_ADAPTER = os.getenv('LOG_EVENT_QUERY_ADAPTER', 'linux_test_double')
    LOG_LINUX_EVENT_QUERY_TEST_DOUBLE = os.getenv('LOG_LINUX_EVENT_QUERY_TEST_DOUBLE', '')
    LOG_CORRELATION_MIN_GROUP_SIZE = int(os.getenv('LOG_CORRELATION_MIN_GROUP_SIZE', '2'))
    LOG_DRIVER_MONITOR_ADAPTER = os.getenv('LOG_DRIVER_MONITOR_ADAPTER', 'linux_test_double')
    LOG_DRIVER_ERROR_ADAPTER = os.getenv('LOG_DRIVER_ERROR_ADAPTER', 'linux_test_double')
    LOG_DRIVER_ALLOWED_HOSTS = os.getenv('LOG_DRIVER_ALLOWED_HOSTS', '')
    LOG_LINUX_DRIVER_MONITOR_TEST_DOUBLE = os.getenv('LOG_LINUX_DRIVER_MONITOR_TEST_DOUBLE', '')
    LOG_LINUX_DRIVER_ERROR_TEST_DOUBLE = os.getenv('LOG_LINUX_DRIVER_ERROR_TEST_DOUBLE', '')
    LOG_EVENT_STREAM_ADAPTER = os.getenv('LOG_EVENT_STREAM_ADAPTER', 'linux_test_double')
    LOG_LINUX_EVENT_STREAM_TEST_DOUBLE = os.getenv('LOG_LINUX_EVENT_STREAM_TEST_DOUBLE', '')
    LOG_EVENT_STREAM_BATCH_SIZE = int(os.getenv('LOG_EVENT_STREAM_BATCH_SIZE', '25'))
    LOG_SEARCH_ADAPTER = os.getenv('LOG_SEARCH_ADAPTER', 'linux_test_double')
    LOG_LINUX_SEARCH_TEST_DOUBLE = os.getenv('LOG_LINUX_SEARCH_TEST_DOUBLE', '')
    LOG_SEARCH_MAX_RESULTS = int(os.getenv('LOG_SEARCH_MAX_RESULTS', '25'))
    RELIABILITY_HISTORY_ADAPTER = os.getenv('RELIABILITY_HISTORY_ADAPTER', 'linux_test_double')
    RELIABILITY_ALLOWED_HOSTS = os.getenv('RELIABILITY_ALLOWED_HOSTS', '')
    RELIABILITY_LINUX_HISTORY_TEST_DOUBLE = os.getenv('RELIABILITY_LINUX_HISTORY_TEST_DOUBLE', '')
    RELIABILITY_HISTORY_MAX_RECORDS = int(os.getenv('RELIABILITY_HISTORY_MAX_RECORDS', '25'))
    RELIABILITY_CRASH_DUMP_ADAPTER = os.getenv('RELIABILITY_CRASH_DUMP_ADAPTER', 'linux_test_double')
    RELIABILITY_ALLOWED_DUMP_ROOTS = os.getenv('RELIABILITY_ALLOWED_DUMP_ROOTS', r'C:\CrashDumps')
    RELIABILITY_CRASH_DUMP_ROOT = os.getenv('RELIABILITY_CRASH_DUMP_ROOT', r'C:\CrashDumps')
    RELIABILITY_LINUX_CRASH_DUMP_TEST_DOUBLE = os.getenv('RELIABILITY_LINUX_CRASH_DUMP_TEST_DOUBLE', '')
    RELIABILITY_EXCEPTION_IDENTIFIER_ADAPTER = os.getenv('RELIABILITY_EXCEPTION_IDENTIFIER_ADAPTER', 'linux_test_double')
    RELIABILITY_LINUX_EXCEPTION_TEST_DOUBLE = os.getenv('RELIABILITY_LINUX_EXCEPTION_TEST_DOUBLE', '')
    RELIABILITY_STACK_TRACE_ADAPTER = os.getenv('RELIABILITY_STACK_TRACE_ADAPTER', 'linux_test_double')
    RELIABILITY_LINUX_STACK_TRACE_TEST_DOUBLE = os.getenv('RELIABILITY_LINUX_STACK_TRACE_TEST_DOUBLE', '')
    RELIABILITY_SCORER_ADAPTER = os.getenv('RELIABILITY_SCORER_ADAPTER', 'linux_test_double')
    RELIABILITY_LINUX_SCORER_TEST_DOUBLE = os.getenv('RELIABILITY_LINUX_SCORER_TEST_DOUBLE', '')
    RELIABILITY_TREND_ADAPTER = os.getenv('RELIABILITY_TREND_ADAPTER', 'linux_test_double')
    RELIABILITY_LINUX_TREND_TEST_DOUBLE = os.getenv('RELIABILITY_LINUX_TREND_TEST_DOUBLE', '')
    RELIABILITY_TREND_WINDOW_SIZE = int(os.getenv('RELIABILITY_TREND_WINDOW_SIZE', '6'))
    RELIABILITY_PREDICTION_ADAPTER = os.getenv('RELIABILITY_PREDICTION_ADAPTER', 'linux_test_double')
    RELIABILITY_LINUX_PREDICTION_TEST_DOUBLE = os.getenv('RELIABILITY_LINUX_PREDICTION_TEST_DOUBLE', '')
    RELIABILITY_PREDICTION_WINDOW_SIZE = int(os.getenv('RELIABILITY_PREDICTION_WINDOW_SIZE', '6'))
    RELIABILITY_PREDICTION_HORIZON = int(os.getenv('RELIABILITY_PREDICTION_HORIZON', '2'))
    RELIABILITY_PATTERN_ADAPTER = os.getenv('RELIABILITY_PATTERN_ADAPTER', 'linux_test_double')
    RELIABILITY_LINUX_PATTERN_TEST_DOUBLE = os.getenv('RELIABILITY_LINUX_PATTERN_TEST_DOUBLE', '')
    RELIABILITY_PATTERN_WINDOW_SIZE = int(os.getenv('RELIABILITY_PATTERN_WINDOW_SIZE', '6'))
    UPDATE_MONITOR_ADAPTER = os.getenv('UPDATE_MONITOR_ADAPTER', 'linux_test_double')
    UPDATE_ALLOWED_HOSTS = os.getenv('UPDATE_ALLOWED_HOSTS', '')
    UPDATE_LINUX_MONITOR_TEST_DOUBLE = os.getenv('UPDATE_LINUX_MONITOR_TEST_DOUBLE', '')
    UPDATE_MONITOR_MAX_ENTRIES = int(os.getenv('UPDATE_MONITOR_MAX_ENTRIES', '25'))
    OLLAMA_ADAPTER = os.getenv('OLLAMA_ADAPTER', 'linux_test_double')
    OLLAMA_ENDPOINT = os.getenv('OLLAMA_ENDPOINT', 'http://localhost:11434/api/generate')
    OLLAMA_ALLOWED_MODELS = os.getenv('OLLAMA_ALLOWED_MODELS', 'llama3.2')
    OLLAMA_DEFAULT_MODEL = os.getenv('OLLAMA_DEFAULT_MODEL', 'llama3.2')
    OLLAMA_LINUX_TEST_DOUBLE_RESPONSES = os.getenv('OLLAMA_LINUX_TEST_DOUBLE_RESPONSES', '')
    OLLAMA_TIMEOUT_SECONDS = int(os.getenv('OLLAMA_TIMEOUT_SECONDS', '8'))
    OLLAMA_PROMPT_MAX_CHARS = int(os.getenv('OLLAMA_PROMPT_MAX_CHARS', '4000'))
    OLLAMA_RESPONSE_MAX_CHARS = int(os.getenv('OLLAMA_RESPONSE_MAX_CHARS', '4000'))
    AI_ROOT_CAUSE_MAX_EVIDENCE_POINTS = int(os.getenv('AI_ROOT_CAUSE_MAX_EVIDENCE_POINTS', '8'))
    AI_RECOMMENDATION_MAX_ITEMS = int(os.getenv('AI_RECOMMENDATION_MAX_ITEMS', '3'))
    AI_TROUBLESHOOT_MAX_CONTEXT_ITEMS = int(os.getenv('AI_TROUBLESHOOT_MAX_CONTEXT_ITEMS', '10'))
    AI_TROUBLESHOOT_MAX_STEPS = int(os.getenv('AI_TROUBLESHOOT_MAX_STEPS', '5'))
    AI_TROUBLESHOOT_MAX_QUESTION_CHARS = int(os.getenv('AI_TROUBLESHOOT_MAX_QUESTION_CHARS', '1200'))
    AI_LEARNING_MAX_TAGS = int(os.getenv('AI_LEARNING_MAX_TAGS', '8'))
    AI_ANOMALY_ANALYSIS_MAX_ITEMS = int(os.getenv('AI_ANOMALY_ANALYSIS_MAX_ITEMS', '10'))
    ALERT_SILENCE_MAX_DURATION_HOURS = int(os.getenv('ALERT_SILENCE_MAX_DURATION_HOURS', '72'))
    ALERT_PATTERN_MIN_OCCURRENCES = int(os.getenv('ALERT_PATTERN_MIN_OCCURRENCES', '3'))
    ALERT_PATTERN_WINDOW_SIZE = int(os.getenv('ALERT_PATTERN_WINDOW_SIZE', '10'))
    # Phase 2 Week 15-16 — remaining features
    SCHEDULED_JOB_MAX_PER_TENANT = int(os.getenv('SCHEDULED_JOB_MAX_PER_TENANT', '50'))
    SELF_HEALING_DRY_RUN = os.getenv('SELF_HEALING_DRY_RUN', 'true').lower() != 'false'
    SELF_HEALING_MAX_DEPTH = int(os.getenv('SELF_HEALING_MAX_DEPTH', '10'))
    AUTOMATION_EXECUTOR_ADAPTER = os.getenv('AUTOMATION_EXECUTOR_ADAPTER', 'linux_test_double')
    REMOTE_EXEC_ADAPTER = os.getenv('REMOTE_EXEC_ADAPTER', 'linux_test_double')
    REMOTE_EXEC_ALLOWED_HOSTS = os.getenv('REMOTE_EXEC_ALLOWED_HOSTS', '')
    REMOTE_EXEC_ALLOWED_COMMANDS = os.getenv('REMOTE_EXEC_ALLOWED_COMMANDS', '')
    REMOTE_EXEC_TIMEOUT_SECONDS = int(os.getenv('REMOTE_EXEC_TIMEOUT_SECONDS', '10'))
    CONFIDENCE_ADAPTER = os.getenv('CONFIDENCE_ADAPTER', 'linux_test_double')
    CONFIDENCE_ALLOWED_HOSTS = os.getenv('CONFIDENCE_ALLOWED_HOSTS', '')
    CONFIDENCE_ALLOWED_MODELS = os.getenv('CONFIDENCE_ALLOWED_MODELS', 'llama3.2')
    CONFIDENCE_LINUX_TEST_DOUBLE_SCORES = os.getenv('CONFIDENCE_LINUX_TEST_DOUBLE_SCORES', '')
    DASHBOARD_ALLOWED_HOSTS = os.getenv('DASHBOARD_ALLOWED_HOSTS', '')
    
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
    # Disable rate limiting entirely during tests to prevent limit exhaustion
    RATELIMIT_ENABLED = False
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
