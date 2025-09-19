#!/usr/bin/env python3
"""
MentorTrack 更新パッケージ作成スクリプト
開発PC → 本番PC への更新を安全に行います
"""

import os
import shutil
import zipfile
import json
from pathlib import Path
from datetime import datetime

class UpdatePackageCreator:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.version = self.get_version()
        self.package_name = f"MentorTrack_Update_v{self.version}_{self.timestamp}"
        
    def get_version(self):
        """バージョン番号を取得（自動インクリメント）"""
        version_file = Path("version.json")
        if version_file.exists():
            with open(version_file, 'r') as f:
                data = json.load(f)
                version = data.get('version', '1.0.0')
        else:
            version = '1.0.0'
        
        # バージョンをインクリメント
        parts = version.split('.')
        parts[2] = str(int(parts[2]) + 1)  # パッチバージョンを上げる
        new_version = '.'.join(parts)
        
        # バージョンファイルを更新
        with open(version_file, 'w') as f:
            json.dump({
                'version': new_version,
                'updated_at': datetime.now().isoformat(),
                'description': input("この更新の説明を入力してください: ") or "更新"
            }, f, indent=2, ensure_ascii=False)
        
        return new_version
    
    def create_update_package(self):
        """更新パッケージを作成"""
        print(f"🔄 更新パッケージを作成中: {self.package_name}")
        
        package_dir = Path(self.package_name)
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir()
        
        # 更新対象ファイルの選択
        update_files = self.select_update_files()
        
        if not update_files:
            print("❌ 更新するファイルが選択されませんでした。")
            return None
        
        # ファイルをコピー
        self.copy_files(update_files, package_dir)
        
        # 更新スクリプトを作成
        self.create_update_script(package_dir, update_files)
        
        # 更新手順書を作成
        self.create_update_instructions(package_dir, update_files)
        
        # ZIPファイルを作成
        zip_path = f"{self.package_name}.zip"
        self.create_zip(package_dir, zip_path)
        
        print(f"✅ 更新パッケージの作成が完了しました！")
        print(f"📦 パッケージ: {zip_path}")
        
        return zip_path
    
    def select_update_files(self):
        """更新するファイルを選択"""
        print("\n📋 更新するファイルを選択してください:")
        
        file_categories = {
            '1': {
                'name': 'アプリケーションコード',
                'files': ['app.py', 'create_accounts.py'],
                'description': 'メイン機能の更新'
            },
            '2': {
                'name': 'HTMLテンプレート',
                'files': ['templates/'],
                'description': 'UI/画面の更新'
            },
            '3': {
                'name': '静的ファイル（CSS、JS）',
                'files': ['static/'],
                'description': 'スタイル・画像の更新（データは除く）'
            },
            '4': {
                'name': '設定ファイル',
                'files': ['requirements.txt', 'version.json'],
                'description': '依存関係・設定の更新'
            },
            '5': {
                'name': '全ファイル',
                'files': ['app.py', 'create_accounts.py', 'templates/', 'static/', 'requirements.txt'],
                'description': '完全更新（推奨）'
            }
        }
        
        for key, category in file_categories.items():
            print(f"  {key}. {category['name']} - {category['description']}")
        
        print("  0. カスタム選択")
        
        choice = input("\n選択してください (1-5, 0): ").strip()
        
        if choice == '0':
            return self.custom_file_selection()
        elif choice in file_categories:
            return file_categories[choice]['files']
        else:
            print("❌ 無効な選択です。全ファイルを更新します。")
            return file_categories['5']['files']
    
    def custom_file_selection(self):
        """カスタムファイル選択"""
        print("\n📝 更新するファイルのパスを入力してください（空行で終了）:")
        files = []
        while True:
            file_path = input("ファイルパス: ").strip()
            if not file_path:
                break
            if Path(file_path).exists():
                files.append(file_path)
                print(f"  ✅ 追加: {file_path}")
            else:
                print(f"  ❌ ファイルが見つかりません: {file_path}")
        return files
    
    def copy_files(self, update_files, package_dir):
        """ファイルをパッケージディレクトリにコピー"""
        print("\n📄 ファイルをコピー中...")
        
        for item in update_files:
            src = Path(item)
            if src.is_dir():
                # ディレクトリの場合
                dst = package_dir / src.name
                if src.name == 'static':
                    # staticディレクトリの場合、uploadsフォルダは除外
                    self.copy_static_without_uploads(src, dst)
                else:
                    shutil.copytree(src, dst)
                print(f"  ✅ {src.name}/")
            elif src.is_file():
                # ファイルの場合
                dst = package_dir / src.name
                shutil.copy2(src, dst)
                print(f"  ✅ {src.name}")
    
    def copy_static_without_uploads(self, src, dst):
        """staticディレクトリをuploadsフォルダを除いてコピー"""
        dst.mkdir(exist_ok=True)
        
        for item in src.iterdir():
            if item.name == 'uploads':
                continue  # uploadsフォルダはスキップ
            
            dst_item = dst / item.name
            if item.is_dir():
                shutil.copytree(item, dst_item)
            else:
                shutil.copy2(item, dst_item)
    
    def create_update_script(self, package_dir, update_files):
        """更新スクリプトを作成"""
        script_content = f'''@echo off
echo MentorTrack 更新スクリプト v{self.version}
echo ================================

echo ⚠️  重要: 更新前に必ずバックアップを取ってください！
pause

echo 🔄 アプリケーションを停止してください...
echo    （start_mentortrack.bat のウィンドウがあれば閉じてください）
pause

echo 📁 ファイルを更新中...
'''
        
        for item in update_files:
            if Path(item).is_dir():
                script_content += f'''
echo   📁 {item} を更新中...
if exist "{item}" (
    if exist "{item}_backup" rmdir /s /q "{item}_backup"
    move "{item}" "{item}_backup"
)
move "{item}" ../
'''
            else:
                script_content += f'''
echo   📄 {item} を更新中...
if exist "../{item}" (
    copy "../{item}" "../{item}.backup"
)
copy "{item}" "../"
'''
        
        script_content += '''
echo ✅ 更新が完了しました！
echo 
echo 📋 次の手順:
echo   1. ../start_mentortrack.bat を実行してアプリを起動
echo   2. ブラウザで http://127.0.0.1:5000 にアクセス
echo   3. 正常に動作することを確認
echo 
echo ❌ 問題が発生した場合:
echo   - *.backup ファイルから復元してください
echo   - 元の開発者にお問い合わせください
echo 
pause
'''
        
        with open(package_dir / "update.bat", "w", encoding="utf-8") as f:
            f.write(script_content)
        
        print("  ✅ update.bat")
    
    def create_update_instructions(self, package_dir, update_files):
        """更新手順書を作成"""
        instructions = f"""# MentorTrack 更新手順書 v{self.version}

## 📋 この更新に含まれる変更

### 更新ファイル:
"""
        for item in update_files:
            instructions += f"- `{item}`\n"
        
        instructions += f"""
### 更新日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}
### バージョン: {self.version}

## ⚠️ 重要な注意事項

### 更新前の準備
1. **必ずアプリを停止してください**
   - `start_mentortrack.bat` のウィンドウを閉じる
   - ブラウザのタブも閉じる

2. **バックアップを取ってください**
   - MentorTrackフォルダ全体をコピーして保存
   - 特に `instance/` フォルダ（データベース）は重要

## 🚀 更新手順

### 自動更新（推奨）
1. この更新パッケージを展開
2. `update.bat` をダブルクリック
3. 画面の指示に従う

### 手動更新
1. 既存のファイルをバックアップ
2. 新しいファイルを上書きコピー
3. アプリを再起動

## ✅ 更新後の確認

1. `start_mentortrack.bat` を実行
2. ブラウザで `http://127.0.0.1:5000` にアクセス
3. 以下を確認:
   - ログインできるか
   - 既存のデータが表示されるか
   - 新機能が動作するか

## 🆘 トラブルシューティング

### 更新に失敗した場合
1. アプリを停止
2. バックアップから復元
3. 開発者に連絡（エラーメッセージを添付）

### よくある問題
- **ファイルが使用中エラー**: アプリが完全に停止していない
- **権限エラー**: 管理者権限で実行
- **データが消えた**: `instance/` フォルダを復元

---
📞 サポート: 問題があれば開発者にご連絡ください
"""
        
        with open(package_dir / "更新手順書.txt", "w", encoding="utf-8") as f:
            f.write(instructions)
        
        print("  ✅ 更新手順書.txt")
    
    def create_zip(self, package_dir, zip_path):
        """ZIPファイルを作成"""
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    file_path = Path(root) / file
                    arc_path = file_path.relative_to(package_dir)
                    zipf.write(file_path, arc_path)
        
        zip_size = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"📊 更新パッケージサイズ: {zip_size:.2f} MB")

def main():
    """メイン処理"""
    print("🔄 MentorTrack 更新パッケージ作成ツール")
    print("=" * 50)
    
    creator = UpdatePackageCreator()
    
    try:
        zip_path = creator.create_update_package()
        if zip_path:
            print(f"""
🎉 更新パッケージの作成が完了しました！

📦 次のステップ:
1. {zip_path} を会社PCにコピー
2. ZIPファイルを展開
3. update.bat を実行
4. 画面の指示に従って更新

⚠️  注意: 必ず事前にバックアップを取ってください！
""")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        input("Enterキーを押してください...")

if __name__ == "__main__":
    main()
