#!/usr/bin/env python3
"""
MentorTrack 本番環境セットアップスクリプト
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Pythonバージョンをチェック"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7以上が必要です。現在のバージョン:", sys.version)
        return False
    print("✅ Python バージョン:", sys.version)
    return True

def check_pip():
    """pipが利用可能かチェック"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      check=True, capture_output=True)
        print("✅ pip が利用可能です")
        return True
    except subprocess.CalledProcessError:
        print("❌ pip が見つかりません")
        return False

def create_venv():
    """仮想環境を作成"""
    venv_path = Path("venv")
    if venv_path.exists():
        print("⚠️  仮想環境が既に存在します。削除して再作成しますか？ (y/N)")
        response = input().lower()
        if response == 'y':
            shutil.rmtree(venv_path)
        else:
            print("✅ 既存の仮想環境を使用します")
            return True
    
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ 仮想環境を作成しました")
        return True
    except subprocess.CalledProcessError as e:
        print("❌ 仮想環境の作成に失敗しました:", e)
        return False

def install_requirements():
    """依存関係をインストール"""
    pip_path = "venv/Scripts/pip" if os.name == 'nt' else "venv/bin/pip"
    
    try:
        subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        print("✅ 依存関係をインストールしました")
        return True
    except subprocess.CalledProcessError as e:
        print("❌ 依存関係のインストールに失敗しました:", e)
        return False

def setup_directories():
    """必要なディレクトリを作成"""
    directories = [
        "instance",
        "static/uploads/product_groups",
        "static/uploads/reports"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ ディレクトリを作成: {directory}")

def create_startup_script():
    """起動スクリプトを作成"""
    if os.name == 'nt':  # Windows
        script_content = """@echo off
echo MentorTrack を起動しています...
call venv\\Scripts\\activate
python app.py
pause
"""
        with open("start_mentortrack.bat", "w", encoding="utf-8") as f:
            f.write(script_content)
        print("✅ Windows用起動スクリプト (start_mentortrack.bat) を作成しました")
    else:  # macOS/Linux
        script_content = """#!/bin/bash
echo "MentorTrack を起動しています..."
source venv/bin/activate
python app.py
"""
        with open("start_mentortrack.sh", "w") as f:
            f.write(script_content)
        os.chmod("start_mentortrack.sh", 0o755)
        print("✅ Unix用起動スクリプト (start_mentortrack.sh) を作成しました")

def main():
    """メイン処理"""
    print("🚀 MentorTrack 本番環境セットアップを開始します\n")
    
    # チェック
    if not check_python_version():
        return False
    
    if not check_pip():
        return False
    
    # セットアップ
    setup_directories()
    
    if not create_venv():
        return False
    
    if not install_requirements():
        return False
    
    create_startup_script()
    
    print("\n🎉 セットアップが完了しました！")
    print("\n📋 次の手順:")
    print("1. データベースファイル (mentortrack.db) を instance/ フォルダにコピー")
    print("2. 画像ファイルを static/uploads/ フォルダにコピー")
    if os.name == 'nt':
        print("3. start_mentortrack.bat をダブルクリックして起動")
    else:
        print("3. ./start_mentortrack.sh を実行して起動")
    print("4. ブラウザで http://127.0.0.1:5000 にアクセス")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ セットアップに失敗しました。エラーを確認してください。")
        sys.exit(1)
