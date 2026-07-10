@echo off
REM Verifica rapidamente o status do servidor e do Ollama

echo Verificando Ollama...
curl -s http://127.0.0.1:11434/api/tags >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   [OK] Ollama respondendo
) else (
    echo   [FALHA] Ollama nao responde
)

echo Verificando Servidor IA...
curl -s http://127.0.0.1:5000/api/status >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   [OK] Servidor respondendo
) else (
    echo   [FALHA] Servidor nao responde
)

echo.
echo Logs em: logs\autostart.log
echo Status em: logs\autostart_status.json
echo.
pause