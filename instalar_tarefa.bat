@echo off
REM ============================================
REM  Instala a tarefa de autostart no Task Scheduler
REM  EXECUTE COMO ADMINISTRADOR
REM ============================================

setlocal
set NOME_TAREFA=IA_Servidor_Autostart
set SCRIPT=%~dp0iniciar_headless.bat

echo Removendo tarefa antiga (se existir)...
schtasks /delete /tn "%NOME_TAREFA%" /f >nul 2>nul

echo Criando tarefa "%NOME_TAREFA%"...
schtasks /create ^
    /tn "%NOME_TAREFA%" ^
    /tr "\"%SCRIPT%\"" ^
    /sc onstart ^
    /ru "SYSTEM" ^
    /rl highest ^
    /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Tarefa instalada com sucesso!
    echo    Nome: %NOME_TAREFA%
    echo    Executa: %SCRIPT%
    echo    Gatilho: ao ligar o PC ^(antes do login^)
    echo.
    echo
    echo    schtasks /run /tn "%NOME_TAREFA%"
) else (
    echo.
    echo ❌ Falha ao criar a tarefa. Execute este .bat como Administrador.
)

pause