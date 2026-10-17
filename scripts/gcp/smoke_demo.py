"""Post-deploy smoke test for the public synthetic demo: usage smoke_demo.py <web-url>.
Calls live Gemini once per chat turn and writes a few synthetic rows; run reset-demo-data.sh afterwards for a pristine demo.
"""
import json
import re
import sys
import urllib.error
import urllib.request
import uuid

WEB = sys.argv[1].rstrip('/')
failures = []


def call(path, user=None, body=None, base=WEB):
    headers = {'Content-Type': 'application/json'}
    if user:
        headers.update({'X-User-Id': user, 'X-Tenant-Id': 'demo-bank'})
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, headers=headers, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw[:1] in (b'{', b'[') else raw.decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:200]


def check(name, ok, detail=''):
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  {detail}' if detail else ''))
    if not ok:
        failures.append(name)


API = '/api/v1/rm'
status, _ = call('/demo')
check('demo page', status == 200, status)
status, config = call('/api/config')
check('runtime config', status == 200 and config.get('demoMode') is True, status)
status, _ = call(API + '/home', 'usr-maya')
check('RM home', status == 200, status)
status, _ = call(API + '/home', 'usr-dina')
check('customer cannot open RM home', status == 403, status)
status, prospects = call(API + '/prospects', 'usr-maya')
check('acquisition list', status == 200 and len(prospects['prospects']) > 0, status)
status, _ = call('/api/v1/unlisted-route', 'usr-maya')
check('proxy rejects routes outside its allowlist', status == 404, status)

status, parties = call(API + '/parties', 'usr-dina')
person = parties['parties'][0]['id']
status, session = call(f'{API}/chat/{person}/sessions', 'usr-dina', {'request_key': str(uuid.uuid4())})
check('chat session created', status == 200, status)
status, conversation = call(f'{API}/chat/{person}/sessions/{session["id"]}', 'usr-dina')
status, turn = call(f'{API}/chat/{person}/turns', 'usr-dina', {
    'message': 'Why has my spending increased?', 'base_version': conversation['version'],
    'request_key': str(uuid.uuid4()), 'session_id': session['id']})
check('chat turn completed by live Gemini', status == 200 and turn['status'] == 'COMPLETED' and turn['mode'] == 'LIVE',
      f"{status} {turn.get('mode')} {turn.get('model')} {turn.get('latency_ms')}ms" if isinstance(turn, dict) else status)
check('amounts are readable', bool(re.search(r'IDR \d{1,3}(,\d{3})+', turn['answer'])) and not re.search(r'\d+\.\d{2} IDR', turn['answer']))
check('follow-up suggestions present', 1 <= len(turn.get('suggestions', [])) <= 3, turn.get('suggestions'))
status, sessions = call(f'{API}/chat/{person}/sessions', 'usr-dina')
check('new session is persisted', status == 200 and any(item['id'] == session['id'] for item in sessions['sessions']), status)
status, feed = call(f'{API}/chat/{person}/engagement', 'usr-dina')
check('engagement feed with insights', status == 200 and len(feed['insights']) > 0, status)
status, brief = call(f'{API}/parties/{person}/ai-brief', 'usr-maya', {})
check('RM AI brief from live Gemini', status == 200 and brief.get('mode') == 'LIVE', status)

if failures:
    sys.exit('Smoke failed: ' + ', '.join(failures))
print('Smoke passed.')
