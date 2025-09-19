#!/usr/bin/env python3
"""
MentorTrack 移植パッケージ作成スクリプト
"""

import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

def create_deployment_package():
    """移植用パッケージを作成"""
    
    # パッケージ名（日時付き）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = f"MentorTrack_Deployment_{timestamp}"
    package_dir = Path(package_name)
    
    print(f"📦 移植パッケージを作成中: {package_name}")
    
    # パッケージディレクトリを作成
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    
    # 必要なファイルとディレクトリのリスト
    files_to_copy = [
        "app.py",
        "create_accounts.py", 
        "requirements.txt",
        "README.md",
        "DEPLOYMENT_GUIDE.md",
        "setup_production.py",
        "start_mentortrack.bat"
    ]
    
    dirs_to_copy = [
        "templates",
        "static",
        "instance"
    ]
    
    # ファイルをコピー
    print("📄 ファイルをコピー中...")
    for file_name in files_to_copy:
        src = Path(file_name)
        if src.exists():
            dst = package_dir / file_name
            shutil.copy2(src, dst)
            print(f"  ✅ {file_name}")
        else:
            print(f"  ⚠️  {file_name} が見つかりません")
    
    # ディレクトリをコピー
    print("📁 ディレクトリをコピー中...")
    for dir_name in dirs_to_copy:
        src = Path(dir_name)
        if src.exists():
            dst = package_dir / dir_name
            shutil.copytree(src, dst)
            print(f"  ✅ {dir_name}/")
        else:
            print(f"  ⚠️  {dir_name}/ が見つかりません")
    
    # 移植手順書を作成
    create_deployment_instructions(package_dir)
    
    # ZIPファイルを作成
    zip_path = f"{package_name}.zip"
    print(f"🗜️  ZIPファイルを作成中: {zip_path}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                arc_path = file_path.relative_to(package_dir)
                zipf.write(file_path, arc_path)
    
    # パッケージサイズを表示
    zip_size = os.path.getsize(zip_path) / (1024 * 1024)  # MB
    print(f"📊 パッケージサイズ: {zip_size:.2f} MB")
    
    print(f"\n🎉 移植パッケージの作成が完了しました！")
    print(f"📦 パッケージ: {zip_path}")
    print(f"📁 展開先: {package_dir}")
    
    return zip_path, package_dir

def create_deployment_instructions(package_dir):
    """移植手順書を作成"""
    
    instructions = """# MentorTrack 移植手順書 🚀

## 📋 このパッケージに含まれるもの

### 📄 アプリケーションファイル
- `app.py` - メインアプリケーション
- `create_accounts.py` - アカウント作成スクリプト
- `requirements.txt` - 依存関係リスト

### 📁 ディレクトリ
- `templates/` - HTMLテンプレート
- `static/` - 静的ファイル（CSS、画像など）
- `instance/` - データベースファイル

### 🔧 セットアップファイル
- `setup_production.py` - 自動セットアップスクリプト
- `start_mentortrack.bat` - 起動スクリプト（Windows用）
- `DEPLOYMENT_GUIDE.md` - 詳細なガイド

## 🚀 クイックスタート（Windows）

### ステップ1: ファイルの配置
1. このフォルダ全体を会社PCの任意の場所にコピー
2. フォルダ名は「MentorTrack」など分かりやすい名前に変更可能

### ステップ2: 環境構築
1. `setup_production.py` をダブルクリックして実行
2. エラーが出た場合は、コマンドプロンプトから実行：
   ```
   python setup_production.py
   ```

### ステップ3: アプリ起動
1. `start_mentortrack.bat` をダブルクリック
2. ブラウザで `http://127.0.0.1:5000` にアクセス

## ⚠️ 重要な注意事項

### セキュリティ
- 会社のセキュリティポリシーを確認してください
- ファイアウォールの設定が必要な場合があります

### データ
- `instance/` フォルダにデータベースが含まれています
- 定期的にバックアップを取ることをお勧めします

### サポート
- 問題が発生した場合は、エラーメッセージを保存してご相談ください
- `DEPLOYMENT_GUIDE.md` に詳細な情報があります

## 📞 トラブルシューティング

### Python が見つからない
- Python 3.7以上をインストールしてください
- https://www.python.org/downloads/

### 権限エラー
- 管理者権限でコマンドプロンプトを実行してください

### ポートエラー
- ポート5000が使用中の場合は、app.py の最後の行を変更：
  ```python
  app.run(debug=debug_mode, host='0.0.0.0', port=8000)
  ```

---
📅 作成日時: """ + datetime.now().strftime("%Y年%m月%d日 %H:%M:%S") + """
🏷️ バージョン: 移植用パッケージ v1.0
"""
    
    with open(package_dir / "移植手順書.txt", "w", encoding="utf-8") as f:
        f.write(instructions)
    
    print("  ✅ 移植手順書.txt")

if __name__ == "__main__":
    try:
        zip_path, package_dir = create_deployment_package()
        print(f"\n📋 次のステップ:")
        print(f"1. {zip_path} を会社PCにコピー")
        print(f"2. ZIPファイルを展開")
        print(f"3. 移植手順書.txt を参照して実行")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        input("Enterキーを押してください...")
