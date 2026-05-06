@echo off
echo HACS 3D Viewer を起動中...
start "" "http://localhost:8080/viewer.html"
python -m http.server 8080
