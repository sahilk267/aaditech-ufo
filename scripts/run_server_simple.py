"""Run the Flask app without applying DB migrations (useful for local file-only checks).

This script creates the app and starts the development server without calling
`apply_database_migrations`. It is intended for quick local verification when
Postgres or other infra is not available.
"""
from server.app import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=False)
