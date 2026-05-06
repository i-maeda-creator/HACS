@echo off
echo HACS Live Dashboard 起動中...
echo.
echo ブラウザで開きます: http://localhost:8080/live_dashboard.html
echo 終了するには Ctrl+C を押してください
echo.
cd /d "%~dp0web"
python -m http.server 8080
