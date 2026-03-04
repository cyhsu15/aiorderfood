"""快速檢查後端連接哪個資料庫"""
import sys
sys.path.insert(0, '.')

from app import db

print("=" * 60)
print("Backend Database Connection Check")
print("=" * 60)
print(f"\nConnected to: {db.DATABASE_URL}")

if 'test' in db.DATABASE_URL.lower():
    print("\nStatus: OK - Using TEST database")
    print("You can run E2E tests now!")
else:
    print("\nStatus: ERROR - Using PRODUCTION database")
    print("\nTo fix:")
    print("1. Stop the backend (Ctrl+C)")
    print("2. PowerShell: $env:TEST_MODE=\"1\"")
    print("3. Run: uvicorn main:app --reload")

print("=" * 60)
