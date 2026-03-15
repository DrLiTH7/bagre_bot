@echo off
color 0B
title Bagre Bot Installer ^& Runner
echo ==============================================
echo        INSTALADOR E INICIADOR: BAGRE BOT      
echo ==============================================
echo.

:: Muda o diretorio de trabalho para a raiz do projeto (um nivel acima de 'run')
cd ..

:: Verifica se o Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERRO] Python nao foi encontrado no sistema!
    echo Por favor, instale o Python 3.10 ou superior e marque a opcao "Add Python to PATH".
    echo Pare a execucao, va em python.org e tente novamente.
    pause
    exit /b
)
echo [OK] Python detectado.
echo.

:: Verifica se a Virtual Environment (VENV) ja existe
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Criando a maquina virtual python ^(venv^)...
    python -m venv venv
    if %errorlevel% neq 0 (
        color 0C
        echo [ERRO] Falha ao criar a venv.
        pause
        exit /b
    )
    echo [OK] Venv criada.
) else (
    echo [1/3] Virtual environment ja existe, pulando criacao...
)

echo.
echo [2/3] Ativando a Virtual Environment...
call venv\Scripts\activate.bat

echo.
echo [3/3] Checando dependencias do sistema ^(requirements.txt^)...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %errorlevel% neq 0 (
    color 0C
    echo [ERRO] Problema ao baixar pacotes. Verifique sua conexao de rede!
    pause
    exit /b
)
echo [OK] Todas as dependencias instaladas.
echo.

echo ==============================================
echo        INICIANDO O MOTOR DO BAGRE BOT      
echo ==============================================
echo [INFO] Para desligar o bot, pressione CTRL + C
echo.
python bagre.py

pause
exit /b
