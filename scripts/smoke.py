"""Exercise a running deployment without printing credentials or session cookies."""
import argparse
import json
import time
import urllib.request
import http.cookiejar

parser = argparse.ArgumentParser()
parser.add_argument('--base-url', default='http://localhost:3000')
args = parser.parse_args()
base = args.base_url.rstrip('/')
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def request(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + '/api' + path, data=data, headers={'Content-Type':'application/json'})
    with client.open(req, timeout=30) as response: return json.load(response)


def wait_for(run_id, target):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        run = request('/workflows/' + run_id)
        if run['status'] == target: return run
        if run['status'] in ('failed','interrupted','cancelled'): raise RuntimeError(run['error'])
        time.sleep(0.5)
    raise RuntimeError('Workflow did not reach ' + target)

health = request('/health')
assert health['status'] == 'ok'
request('/auth/demo', {})
project = request('/projects', {'name':'Deployment verification'})
run_id = request('/workflows', {'project_id':project['id'],'prompt':'Create a researched content campaign about electric vehicles in India.','mode':'demo'})['id']
run = wait_for(run_id, 'awaiting_approval')
assert len(run['artifacts']) == 4 and run['revision'] == 1
assert run['links'] and any(c['status'] == 'disputed' for c in run['claims'])
request('/workflows/' + run_id + '/review', {'decision':'approve','acknowledge_warnings':True,'comment':'Deployment smoke test reviewed demo fixtures.'})
finished = wait_for(run_id, 'completed')
exported = request('/workflows/' + run_id + '/export?format=json')
assert len(exported['artifacts']) == 4 and exported['approval']['decision'] == 'approve'
print(json.dumps({'status':'passed','database':health['database'],'queue':health['queue'],'agents':len({e['agent'] for e in finished['executions']}),'events':len(finished['events']),'artifacts':len(exported['artifacts']),'run_id':run_id}))
