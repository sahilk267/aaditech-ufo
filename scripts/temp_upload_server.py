from flask import Flask, request, jsonify
from pathlib import Path

app = Flask(__name__)
BASE = Path('instance') / 'agent_releases'


@app.route('/api/agent/releases/upload', methods=['POST'])
def upload():
    tenant = request.headers.get('X-Tenant-Slug') or 'default'
    version = request.form.get('version') or ''
    f = request.files.get('release_file')
    if not f:
        return jsonify({'error': 'no file provided'}), 400
    dest_dir = BASE / tenant
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f.filename
    f.save(str(dest))
    return jsonify({'saved': str(dest), 'version': version}), 201


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001)
