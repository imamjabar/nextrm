"""Warm-up and measurement script for NextRM Cloud Run demo.
Usage: python scripts/gcp/warm_demo.py https://<web-url>
"""
import json
import sys
import time
import urllib.error
import urllib.request

if len(sys.argv) < 2:
    print('Usage: python warm_demo.py https://<web-url>')
    sys.exit(1)

WEB = sys.argv[1].rstrip('/')


def request_once(path: str, user: str):
    url = f"{WEB}/api/v1/{path.lstrip('/')}"
    headers = {
        'Content-Type': 'application/json',
        'X-User-Id': user,
        'X-Tenant-Id': 'demo-bank',
    }
    req = urllib.request.Request(url, headers=headers, method='GET')
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            ms = round((time.perf_counter() - start) * 1000)
            data = json.loads(raw) if raw[:1] in (b'{', b'[') else raw.decode()
            return resp.status, ms, data
    except urllib.error.HTTPError as err:
        ms = round((time.perf_counter() - start) * 1000)
        return err.code, ms, None
    except Exception:
        ms = round((time.perf_counter() - start) * 1000)
        return 0, ms, None


def call_pair(path: str, user: str):
    status1, ms1, data1 = request_once(path, user)
    status2, ms2, _ = request_once(path, user)
    status = status2 if status2 != 0 else status1
    print(f"{user} {path} {ms1}ms {ms2}ms {status}")
    if status1 != 200 or status2 != 200:
        sys.exit(1)
    return data1


def main():
    for cust in ['usr-dina', 'usr-aditya', 'usr-nabila']:
        call_pair('auth/me', cust)
        parties_data = call_pair('rm/parties', cust)
        if not parties_data or not parties_data.get('parties'):
            print(f"ERROR: No parties returned for {cust}")
            sys.exit(1)
        pid = parties_data['parties'][0]['id']
        call_pair(f'rm/chat/{pid}', cust)
        call_pair(f'rm/chat/{pid}/sessions', cust)
        call_pair(f'rm/chat/{pid}/engagement', cust)
        call_pair(f'rm/chat/{pid}/requests', cust)

    call_pair('auth/me', 'usr-maya')
    today_data = call_pair('rm/today', 'usr-maya')
    dina_pid = None
    if today_data and isinstance(today_data, dict):
        for item in today_data.get('customers', []):
            if item.get('party', {}).get('name') == 'Dina Rahma':
                dina_pid = item['party']['id']
                break
    if not dina_pid:
        print("ERROR: Could not find Dina Rahma party id in rm/today")
        sys.exit(1)
    call_pair(f'rm/parties/{dina_pid}/snapshot', 'usr-maya')
    call_pair('rm/copilot/context', 'usr-maya')

    call_pair('auth/me', 'usr-aiadmin')
    call_pair('rm/quality', 'usr-aiadmin')
    call_pair('rm/quality/sessions', 'usr-aiadmin')
    call_pair('rm/quality-assistant/context', 'usr-aiadmin')


if __name__ == '__main__':
    main()
