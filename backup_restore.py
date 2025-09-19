#!/usr/bin/env python3
"""
MentorTrack バックアップ・復元システム
"""

import os
import shutil
import zipfile
import json
from pathlib import Path
from datetime import datetime

class BackupRestore:
    def __init__(self):
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self, backup_type="full"):
        """バックアップを作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"MentorTrack_Backup_{backup_type}_{timestamp}"
        
        print(f"💾 バックアップを作成中: {backup_name}")
        
        if backup_type == "full":
            return self._create_full_backup(backup_name)
        elif backup_type == "data":
            return self._create_data_backup(backup_name)
        elif backup_type == "code":
            return self._create_code_backup(backup_name)
    
    def _create_full_backup(self, backup_name):
        """完全バックアップ"""
        backup_path = self.backup_dir / f"{backup_name}.zip"
        
        exclude_dirs = {'venv', '__pycache__', 'backups', '.git'}
        exclude_files = {'.gitignore', '*.pyc', '*.log'}
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk('.'):
                # 除外ディレクトリをスキップ
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    if not any(file.endswith(ext.replace('*', '')) for ext in exclude_files if '*' in ext):
                        file_path = Path(root) / file
                        zipf.write(file_path, file_path)
        
        size = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"✅ 完全バックアップ作成完了: {backup_path} ({size:.2f} MB)")
        return backup_path
    
    def _create_data_backup(self, backup_name):
        """データのみバックアップ"""
        backup_path = self.backup_dir / f"{backup_name}.zip"
        
        data_paths = [
            'instance/',
            'static/uploads/'
        ]
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for data_path in data_paths:
                path = Path(data_path)
                if path.exists():
                    if path.is_dir():
                        for file_path in path.rglob('*'):
                            if file_path.is_file():
                                zipf.write(file_path, file_path)
                    else:
                        zipf.write(path, path)
        
        size = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"✅ データバックアップ作成完了: {backup_path} ({size:.2f} MB)")
        return backup_path
    
    def _create_code_backup(self, backup_name):
        """コードのみバックアップ"""
        backup_path = self.backup_dir / f"{backup_name}.zip"
        
        code_paths = [
            'app.py',
            'create_accounts.py',
            'templates/',
            'static/',
            'requirements.txt'
        ]
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for code_path in code_paths:
                path = Path(code_path)
                if path.exists():
                    if path.is_dir():
                        for file_path in path.rglob('*'):
                            if file_path.is_file() and 'uploads' not in str(file_path):
                                zipf.write(file_path, file_path)
                    else:
                        zipf.write(path, path)
        
        size = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"✅ コードバックアップ作成完了: {backup_path} ({size:.2f} MB)")
        return backup_path
    
    def list_backups(self):
        """バックアップ一覧を表示"""
        backups = list(self.backup_dir.glob("*.zip"))
        if not backups:
            print("📁 バックアップファイルがありません")
            return []
        
        print("📋 バックアップ一覧:")
        for i, backup in enumerate(sorted(backups, reverse=True), 1):
            size = os.path.getsize(backup) / (1024 * 1024)
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            print(f"  {i}. {backup.name} ({size:.2f} MB) - {mtime.strftime('%Y/%m/%d %H:%M')}")
        
        return sorted(backups, reverse=True)
    
    def restore_backup(self, backup_path):
        """バックアップから復元"""
        if not Path(backup_path).exists():
            print(f"❌ バックアップファイルが見つかりません: {backup_path}")
            return False
        
        print(f"🔄 バックアップから復元中: {backup_path}")
        
        # 確認
        response = input("⚠️  現在のファイルは上書きされます。続行しますか？ (y/N): ")
        if response.lower() != 'y':
            print("❌ 復元をキャンセルしました")
            return False
        
        try:
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall('.')
            
            print("✅ 復元が完了しました")
            return True
        
        except Exception as e:
            print(f"❌ 復元に失敗しました: {e}")
            return False

def main():
    """メイン処理"""
    backup_restore = BackupRestore()
    
    while True:
        print("\n🛠️  MentorTrack バックアップ・復元ツール")
        print("=" * 40)
        print("1. 完全バックアップ作成")
        print("2. データのみバックアップ作成")
        print("3. コードのみバックアップ作成")
        print("4. バックアップ一覧表示")
        print("5. バックアップから復元")
        print("0. 終了")
        
        choice = input("\n選択してください (0-5): ").strip()
        
        if choice == '1':
            backup_restore.create_backup("full")
        
        elif choice == '2':
            backup_restore.create_backup("data")
        
        elif choice == '3':
            backup_restore.create_backup("code")
        
        elif choice == '4':
            backup_restore.list_backups()
        
        elif choice == '5':
            backups = backup_restore.list_backups()
            if backups:
                try:
                    index = int(input("復元するバックアップの番号を入力: ")) - 1
                    if 0 <= index < len(backups):
                        backup_restore.restore_backup(backups[index])
                    else:
                        print("❌ 無効な番号です")
                except ValueError:
                    print("❌ 数字を入力してください")
        
        elif choice == '0':
            print("👋 終了します")
            break
        
        else:
            print("❌ 無効な選択です")

if __name__ == "__main__":
    main()
