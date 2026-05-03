from pathlib import Path
from server.services.agent_release_service import AgentReleaseService

inst = Path(__file__).resolve().parents[1] / 'instance'
src = inst / 'agent_releases' / 'aaditech-agent-0.0.1-test.exe'
print('src exists?', src.exists())
try:
    rel = AgentReleaseService.register_release_file(str(src), '0.0.1-test', {}, str(inst), tenant_slug='tenant1')
    print('registered:', rel.to_dict())
    print('tenant list:', [r.to_dict() for r in AgentReleaseService.list_releases({}, str(inst), tenant_slug='tenant1')])
except Exception as e:
    print('ERROR', e)
