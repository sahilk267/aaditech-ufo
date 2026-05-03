#!/usr/bin/env python3
import json
from pathlib import Path
from server.services.agent_release_service import AgentReleaseService

ROOT = Path(__file__).resolve().parent.parent
INSTANCE = ROOT / 'instance'

releases = AgentReleaseService.list_releases({}, str(INSTANCE))
print(json.dumps([r.to_dict() for r in releases], indent=2))
