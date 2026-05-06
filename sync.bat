@echo off
cd /d "C:\Users\kyomi\Desktop\hacs"
git add .
git diff --cached --quiet && exit /b 0
git commit -m "auto backup: %date% %time%"
git push origin main
