"""Ask the ten most common customer questions as the demo customer (Dina) and grade each answer.

Usage: top10_questions.py [--live] [--url https://web-url] [--only 3,5] [--show]
  default  in-process API on a disposable PostgreSQL database, SIMULATED local engine
  --live   same, but live Gemini on Vertex AI (needs GOOGLE_CLOUD_PROJECT or GCP_PROJECT_ID plus gcloud ADC)
  --url    a deployed demo; its own provider decides the mode (writes synthetic rows; reset afterwards)
"""
import argparse
import os
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'services/api')]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--live', action='store_true')
parser.add_argument('--url')
parser.add_argument('--only', default='')
parser.add_argument('--show', action='store_true', help='print every answer, not only failures')
args = parser.parse_args()

AMOUNT = r'IDR \d{1,3}(?:,\d{3})+'
ADVISOR = r'suitab|advisor|relationship manager|\bRM\b'
CASES = [
    (1, 'Where is my money going and how can I stop overspending?', 'SAVINGS', [AMOUNT, r'Groceries|Transport|Education']),
    (2, 'How much can I safely spend or save this month without running short?', 'SAVINGS', [AMOUNT, r'25 Oct|payday|salary']),
    (3, 'How do I start building wealth or investing with limited money?', 'WEALTH', [r'buffer|debt|card|surplus', ADVISOR]),
    (4, 'Am I on track for my goals like school fees and an emergency fund?', 'SAVINGS', [AMOUNT, r'on track|behind|short|gap|needs']),
    (5, 'Is my portfolio performing well and what should I do next?', 'WEALTH', [r'IDR (?:10,399,000|15,524,000)', ADVISOR]),
    (6, 'Should I pay down my credit card, save more, or invest extra cash?', 'WEALTH', [r'IDR 84,000', r'certain|uncertain|months', ADVISOR]),
    (7, 'Are there subscriptions or recurring costs I can cut?', 'SAVINGS', [AMOUNT, r'Spotify|Padang|dining']),
    (8, 'What product or action should I take next to improve my finances?', 'SAVINGS', [AMOUNT, r'card|buffer|goal']),
    (9, 'How is my overall financial health and net worth trending?', 'SAVINGS', [r'IDR 31,824,000']),
    (10, 'Why did my investments drop, is this normal, and should I sell?', 'WEALTH', [r'6\.10%', ADVISOR]),
]
FORBIDDEN = [r'\d{7,}\.\d\d', r'could not answer that reliably']

if args.url:
    import httpx
    client = httpx.Client(base_url=args.url.rstrip('/'), timeout=90)
    prefix, cleanup = '/api/v1/rm', lambda: None
    mode_label = 'deployed demo'
else:
    import devdb
    database = 'nextrm_v_top10_' + str(os.getpid())
    devdb.ensure_server(); devdb.drop(database); devdb.create(database)
    env = {'DATABASE_URL': devdb.url(database), 'ENVIRONMENT': 'development', 'AUTH_PROVIDER': 'synthetic_demo'}
    if args.live:
        project = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCP_PROJECT_ID')
        if not project:
            sys.exit('Set GOOGLE_CLOUD_PROJECT or GCP_PROJECT_ID for --live.')
        env.update(NEXTRM_AI_PROVIDER='vertex', GOOGLE_CLOUD_PROJECT=project, GOOGLE_CLOUD_LOCATION=os.getenv('GOOGLE_CLOUD_LOCATION', 'asia-southeast1'),
                   GEMINI_MODEL=os.getenv('GEMINI_MODEL', 'gemini-3.5-flash'),
                   GEMINI_THINKING_LEVEL=os.getenv('GEMINI_THINKING_LEVEL', 'minimal'),
                   GEMINI_THINKING_LEVEL_FALLBACK=os.getenv('GEMINI_THINKING_LEVEL_FALLBACK', 'low'))
    else:
        env['NEXTRM_AI_PROVIDER'] = 'local'
    os.environ.update(env)
    from alembic import command
    from alembic.config import Config
    migrations = Config(); migrations.set_main_option('script_location', str(ROOT / 'services/api/migrations'))
    command.upgrade(migrations, 'head')
    from app.core.database import SessionLocal, engine
    from app.core.seeder import seed_demo_database
    with SessionLocal() as db:
        seed_demo_database(db)
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    prefix = '/v1/rm'
    mode_label = 'live Gemini' if args.live else 'SIMULATED local engine'

    def cleanup():
        engine.dispose(); devdb.drop(database)


def call(method, path, user, body=None):
    response = client.request(method, prefix + path, headers={'X-User-Id': user, 'X-Tenant-Id': 'demo-bank'}, json=body)
    return response.status_code, response.json()


def advice_violations(text):
    from app.services.assistant.engine import breaks_investment_rules
    return ['directive or prediction'] if breaks_investment_rules(text) else []


status, parties = call('GET', '/parties', 'usr-dina')
person = parties['parties'][0]['id']
status, session = call('POST', f'/chat/{person}/sessions', 'usr-dina', {'request_key': str(uuid.uuid4())})
wanted = {int(x) for x in args.only.split(',') if x.strip()}
failed = []
print(f'Mode: {mode_label}')
for number, question, route, musts in CASES:
    if wanted and number not in wanted:
        continue
    _, conversation = call('GET', f'/chat/{person}/sessions/{session["id"]}', 'usr-dina')
    status, turn = call('POST', f'/chat/{person}/turns', 'usr-dina', {'message': question, 'base_version': conversation['version'],
                                                                      'request_key': str(uuid.uuid4()), 'session_id': session['id']})
    problems = []
    if status != 200 or turn.get('status') != 'COMPLETED':
        problems.append(f'turn {status} {turn.get("status") if isinstance(turn, dict) else turn}')
        if not args.url and isinstance(turn, dict) and turn.get('id'):
            import json
            from app.models.relationships import Turn
            with SessionLocal() as db:
                stored = db.get(Turn, turn['id'])
                problems.append('reason: ' + str(json.loads(stored.output_json).get('error')) if stored else 'reason unavailable')
    else:
        text = turn['answer']
        if turn['route'] != route:
            problems.append(f'route {turn["route"]} != {route}')
        problems += [f'missing /{m}/' for m in musts if not re.search(m, text, re.I)]
        problems += [f'forbidden /{f}/' for f in FORBIDDEN if re.search(f, text, re.I)]
        problems += [f'advice pattern {p}' for p in advice_violations(text)]
        if not turn.get('suggestions'):
            problems.append('no follow-up suggestions')
    print(f"{'PASS' if not problems else 'FAIL'}  Q{number}  {turn.get('mode')}  {turn.get('latency_ms')} ms  route={turn.get('route')}  think={turn.get('thinking_level')}  {question}")
    if problems or args.show:
        print('      ' + (turn.get('answer') or str(turn)).replace('\n', '\n      '))
        print('      suggestions:', turn.get('suggestions'))
    for problem in problems:
        print('      !', problem)
    if problems:
        failed.append(number)
if not wanted:
    _, conversation = call('GET', f'/chat/{person}/sessions/{session["id"]}', 'usr-dina')
    status, turn = call('POST', f'/chat/{person}/turns', 'usr-dina', {'message': 'Talk to my RM about my portfolio', 'base_version': conversation['version'],
                                                                      'request_key': str(uuid.uuid4()), 'session_id': session['id']})
    _, queue = call('GET', '/signals', 'usr-maya')
    signal = next((x for x in queue.get('signals', []) if x['id'] == turn.get('signal_id')), None)
    handed_over = status == 200 and signal is not None and signal['category'] == 'GUIDANCE'
    print(f"{'PASS' if handed_over else 'FAIL'}  RM handoff  {turn.get('mode')}  {'GUIDANCE signal visible to the RM' if handed_over else 'no signal reached the RM'}")
    if not handed_over:
        failed.append('handoff')
cleanup()
print('All questions passed.' if not failed else f'Failed: {failed}')
sys.exit(1 if failed else 0)
