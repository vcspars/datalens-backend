import requests, json, time, sys

BASE = 'http://localhost:8008'
TOKEN = requests.post(BASE + '/api/auth/login', json={'email': 'test@test.com', 'password': 'testtest'}).json()['access_token']
HEADERS = {'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'}

print('Logged in OK. Running 6 financial statement tests...')
sys.stdout.flush()

def ask(question):
    print()
    print('=' * 70)
    print('QUESTION:', question)
    print('=' * 70)
    sys.stdout.flush()
    r = requests.post(BASE + '/api/chat/stream', headers=HEADERS, json={'question': question}, stream=True, timeout=180)
    full_response = ''
    sql_query = ''
    for line in r.iter_lines():
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode('utf-8', errors='replace')
        if not line.startswith('data: '):
            continue
        try:
            payload = json.loads(line[6:])
            t = payload.get('type')
            if t == 'done':
                full_response = payload.get('full_response', '')
                sql_query     = payload.get('sql_query', '')
            elif t == 'error':
                print('ERROR EVENT:', payload.get('content'))
        except Exception:
            pass
    print('SQL USED:')
    print(sql_query if sql_query else '(none)')
    print()
    print('FULL RESPONSE:')
    print(full_response if full_response else '(empty)')
    print()
    sys.stdout.flush()
    time.sleep(5)

ask('Show me the balance sheet main grouped for June 2024')
ask('Show me the balance sheet sub grouped for June 2024')
ask('Show me the detailed balance sheet for June 2024')
ask('Show me the P&L main grouped for June 2024')
ask('Show me the P&L sub grouped for June 2024')
ask('Show me the detailed P&L for June 2024')
print('ALL DONE')
sys.stdout.flush()
