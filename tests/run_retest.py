"""Quick retest of previously failing questions."""
import json, sys, time
sys.path.insert(0, ".")
from tests.run_full_test import login, clear_history, send_chat, evaluate, count_md_rows

API_BASE = "http://127.0.0.1:8000"

RETEST = [
    {"id": 15, "question": "List all product categories and their total sales amount.",
     "expect_data": True, "min_rows": 1, "category": "product"},
    {"id": 21, "question": "Show me current inventory quantity by warehouse for top 10 products.",
     "expect_data": True, "min_rows": 1, "category": "inventory"},
    {"id": 24, "question": "Which products have the most stock on hand?",
     "expect_data": True, "min_rows": 1, "category": "inventory"},
    {"id": 39, "question": "How many credit memos have been issued? Show by year.",
     "expect_data": True, "min_rows": 1, "category": "returns"},
    {"id": 45, "question": "Show me top 20 customers by revenue with their total sales amount.",
     "expect_data": True, "min_rows": 15, "category": "analytics"},
]

def main():
    token = login()
    clear_history(token)
    passed = 0; failed = 0
    for item in RETEST:
        print(f"\n[Q{item['id']}] {item['question'][:70]}")
        res = send_chat(token, item["question"])
        ok, issues = evaluate(item, res)
        sql = (res.get("sql_query") or "")[:250]
        rows = len(res.get("table_data") or []) or count_md_rows(res.get("full_response", ""))
        t = res.get("elapsed_sec", 0)
        if ok:
            passed += 1
            print(f"  PASS | {t:.1f}s | rows={rows}")
        else:
            failed += 1
            print(f"  FAIL | {t:.1f}s | {'; '.join(issues)}")
        print(f"  SQL: {sql}")
        print(f"  Response preview: {(res.get('full_response') or '')[:300]}")
    print(f"\nRetest: {passed} passed, {failed} failed")

if __name__ == "__main__":
    main()
