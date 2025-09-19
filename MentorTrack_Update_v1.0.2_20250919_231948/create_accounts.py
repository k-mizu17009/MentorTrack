#!/usr/bin/env python3
"""
アカウント作成用スクリプト
"""
import requests
import json

# 管理者アカウントを作成
print("管理者アカウントを作成中...")
response = requests.get('http://127.0.0.1:5000/debug/create-admin')
print(f"管理者アカウント作成結果: {response.json()}")

# 管理者でログインしてメンターアカウントを作成
print("\n管理者でログイン中...")
login_data = {
    'email': 'admin@example.com',
    'password': 'admin123'
}
session = requests.Session()
login_response = session.post('http://127.0.0.1:5000/login', data=login_data)
print(f"ログイン結果: {login_response.status_code}")

# メンターアカウントを作成
print("\nメンターアカウントを作成中...")
mentor_response = session.get('http://127.0.0.1:5000/debug/create-mentor')
print(f"メンターアカウント作成結果: {mentor_response.json()}")

# ユーザー一覧を確認
print("\nユーザー一覧を確認中...")
users_response = session.get('http://127.0.0.1:5000/debug/users')
print(f"ユーザー一覧: {users_response.json()}")

print("\n完了！以下のアカウントでログインできます：")
print("管理者: admin@example.com / admin123")
print("メンター: mentor@example.com / password123")
