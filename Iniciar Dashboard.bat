@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   Gestão de Projetos
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no seu computador.
    echo Instale o Python em https://www.python.org/downloads/
    echo Durante a instalacao, marque a opcao "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Primeira execucao: criando ambiente e instalando dependencias...
    echo Isso pode levar alguns minutos, dependendo da sua internet.
    echo.
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERRO] Falha ao instalar as dependencias. Verifique sua conexao com a internet e tente novamente.
        pause
        exit /b 1
    )
    echo.
    echo Dependencias instaladas com sucesso!
    echo.
)

echo Iniciando o dashboard...
echo Uma aba sera aberta automaticamente no seu navegador.
echo Para encerrar o programa, feche esta janela ou pressione Ctrl+C.
echo.

".venv\Scripts\python.exe" -m streamlit run app.py

pause
