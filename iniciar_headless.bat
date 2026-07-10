@echo off
REM ============================================
REM  Inicia o autostart headless (sem console)
REM  Chamado pelo Task Scheduler no boot
REM ============================================

cd /d "%~dp0"

REM Usa pythonw para não abrir janela de console.
REM
where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" pythonw autostart.py
) else (
    REM Fallback: python normal, mas ainda sem janela visivel
    start /min "" python autostart.py
)