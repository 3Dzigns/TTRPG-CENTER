import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app_requirements import app
client = TestClient(app)
# seed a couple entries first
req = {
 'title':'A','version':'1.0.0','description':'d','requirements':{'functional':[], 'non_functional':[]},'author':'x'
}
print(client.post('/api/requirements/submit', json=req, headers={'X-Admin-User':'a'}).status_code)
print(client.post('/api/requirements/submit', json={**req, 'version':'2.0.0'}, headers={'X-Admin-User':'b'}).status_code)
r = client.get('/api/requirements/latest')
print('status', r.status_code)
print(r.text)
