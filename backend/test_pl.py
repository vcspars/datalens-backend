"""
P&L continuation tests — runs from BS-Follow3 through P&L + cross-statement tests.
"""
import requests, json, time, sys, os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE  = 'http://localhost:8007'
CREDS = {'email': 'test@test.com', 'password': 'testtest'}
OUT   = os.path.join(os.path.dirname(__file__), 'test_results_pl.txt')


def login():
    r = requests.post(f'{BASE}/api/auth/login', json=CREDS, timeout=30)
    r.raise_for_status()
    return r.json()['access_token']


def ask(token, question, label='', log_fh=None):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    sep = '=' * 80
    out = f'\n{sep}\n{label}\nQ: {question}\n{sep}\n'
    print(out, flush=True)
    if log_fh:
        log_fh.write(out)
        log_fh.flush()

    full_response = sql_query = ''
    try:
        r = requests.post(
            f'{BASE}/api/chat/stream',
            headers=headers,
            json={'question': question},
            stream=True,
            timeout=180,
        )
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
                    full_response = f'[ERROR]: {payload.get("content", "")}'
            except Exception:
                pass
    except Exception as ex:
        full_response = f'[REQUEST EXCEPTION]: {ex}'

    result = (
        f'SQL:\n{sql_query or "(none)"}\n\n'
        f'RESPONSE:\n{full_response or "(empty)"}\n'
    )
    print(result, flush=True)
    if log_fh:
        log_fh.write(result)
        log_fh.flush()
    time.sleep(4)


TESTS = [
    # ── Balance Sheet follow-ups ─────────────────────────────────────────────
    ('BS-Follow3',      'Grouped balance sheet as of December 2023 and December 2024 side by side'),
    ('BS-Follow4',      'Which section has the highest value and why is it significant?'),

    # ── P&L: Single month ────────────────────────────────────────────────────
    ('PL-Main-Jun2024', 'Show me the grouped P&L statement for June 2024'),
    ('PL-Main-Dec2024', 'Grouped income statement for December 2024 as per template'),
    ('PL-Main-Jan2025', 'Grouped P&L for January 2025'),
    ('PL-Main-Dec2023', 'Grouped P&L statement for December 2023'),

    # ── P&L: Sub grouped ────────────────────────────────────────────────────
    ('PL-Sub-Jun2024',  'Sub grouped P&L statement for June 2024 as per template'),
    ('PL-Sub-Jan2025',  'Sub grouped income statement for January 2025 as per template'),

    # ── P&L: Detailed ───────────────────────────────────────────────────────
    ('PL-Det-Jun2024',  'Detailed P&L statement for June 2024 as per detailed template'),
    ('PL-Det-Jan2025',  'Detailed income statement for January 2025'),
    ('PL-Det-Dec2024',  'Full detailed P&L for December 2024 as per template'),

    # ── P&L: Full year ───────────────────────────────────────────────────────
    ('PL-Main-2024',    'Grouped P&L statement for full year 2024'),
    ('PL-Main-2025',    'Grouped income statement for 2025'),
    ('PL-Sub-2024',     'Sub grouped P&L for 2024'),

    # ── P&L: Multi-month ─────────────────────────────────────────────────────
    ('PL-Main-Multi1',  'Grouped P&L for January 2025 and February 2025 side by side'),
    ('PL-Main-Multi2',  'Compare grouped P&L for June 2024 vs June 2025'),
    ('PL-Sub-Multi1',   'Sub grouped income statement for January and February 2025 in crosstab'),
    ('PL-Det-Multi1',   'Detailed P&L for October 2024 and November 2024 in two columns'),

    # ── P&L: Context follow-ups ──────────────────────────────────────────────
    ('PL-Follow1',      'What is the gross profit margin based on the above P&L?'),
    ('PL-Follow2',      'Which expense category is the highest and what is its percentage of total sales?'),

    # ── Cross-statement context ───────────────────────────────────────────────
    ('Cross1',          'Now give me the grouped balance sheet for December 2024'),
    ('Cross3',          'Show me the sub grouped balance sheet and sub grouped P&L for December 2024 together'),
]

if __name__ == '__main__':
    print(f'Logging to: {OUT}', flush=True)
    token = login()
    print('Logged in OK (executive role)', flush=True)

    with open(OUT, 'w', encoding='utf-8', errors='replace') as fh:
        fh.write('P&L CONTINUATION TEST RESULTS\n')
        fh.write('=' * 80 + '\n\n')

        for label, q in TESTS:
            ask(token, q, label=f'[{label}] {q[:70]}', log_fh=fh)

        fh.write('\nALL P&L TESTS COMPLETE\n')

    print('\nALL P&L TESTS COMPLETE', flush=True)
