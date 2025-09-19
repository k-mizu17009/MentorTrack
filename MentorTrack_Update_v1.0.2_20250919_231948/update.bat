@echo off
echo MentorTrack 更新スクリプト v1.0.2
echo ================================

echo ⚠️  重要: 更新前に必ずバックアップを取ってください！
pause

echo 🔄 アプリケーションを停止してください...
echo    （start_mentortrack.bat のウィンドウがあれば閉じてください）
pause

echo 📁 ファイルを更新中...

echo   📄 app.py を更新中...
if exist "../app.py" (
    copy "../app.py" "../app.py.backup"
)
copy "app.py" "../"

echo   📄 create_accounts.py を更新中...
if exist "../create_accounts.py" (
    copy "../create_accounts.py" "../create_accounts.py.backup"
)
copy "create_accounts.py" "../"

echo   📁 templates/ を更新中...
if exist "templates/" (
    if exist "templates/_backup" rmdir /s /q "templates/_backup"
    move "templates/" "templates/_backup"
)
move "templates/" ../

echo   📁 static/ を更新中...
if exist "static/" (
    if exist "static/_backup" rmdir /s /q "static/_backup"
    move "static/" "static/_backup"
)
move "static/" ../

echo   📄 requirements.txt を更新中...
if exist "../requirements.txt" (
    copy "../requirements.txt" "../requirements.txt.backup"
)
copy "requirements.txt" "../"

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
