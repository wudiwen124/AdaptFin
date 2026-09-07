@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)

echo Starting AdaptFin UI on http://localhost:8501 ...
start "AdaptFin Server" cmd /k "python -m streamlit run app/ui/streamlit_app.py --server.headless true --server.port 8501"

powershell -NoProfile -Command "$u='http://127.0.0.1:8501'; $ok=$false; for($i=0;$i -lt 90;$i++){ try { $r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 2; if($r.StatusCode -ge 200){ $ok=$true; break } } catch {}; Start-Sleep -Seconds 1 }; if($ok){ Start-Process $u } else { Write-Host 'Server did not become ready in 90s.' }"

endlocal
