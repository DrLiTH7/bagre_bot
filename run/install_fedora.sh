#!/bin/bash

# Cores para o terminal
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color
CYAN='\033[0;36m'

echo -e "${CYAN}==============================================${NC}"
echo -e "${CYAN}       INSTALADOR E INICIADOR: BAGRE BOT      ${NC}"
echo -e "${CYAN}               (Fedora Linux)                 ${NC}"
echo -e "${CYAN}==============================================${NC}"
echo ""

# Muda o diretorio de trabalho para a raiz do projeto (um nivel acima de 'run')
cd ..

echo -e "[1/4] Instalando dependencias do sistema via DNF..."
echo "Pode ser solicitada a sua senha de administrador (sudo)."
# sudo dnf update -y  # Comentado para evitar download de atualizações de todo o sistema (pode chegar a gigabytes)
sudo dnf install -y python3 python3-pip python3-virtualenv ffmpeg
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERRO] Falha ao instalar dependencias do sistema com o DNF.${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Dependencias do sistema instaladas.${NC}\n"

if [ ! -f "venv/bin/activate" ]; then
    echo -e "[2/4] Criando a maquina virtual python (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERRO] Falha ao criar a venv.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[OK] Venv criada.${NC}\n"
else
    echo -e "${GREEN}[2/4] Virtual environment ja existe, pulando criacao...${NC}\n"
fi

echo -e "[3/4] Ativando a Virtual Environment..."
source venv/bin/activate
echo -e "${GREEN}[OK] Venv ativada.${NC}\n"

echo -e "[4/4] Instalando pacotes do Python (requirements.txt)..."
python3 -m pip install --upgrade pip >/dev/null 2>&1
pip install -r requirements.txt
pip install imghdr  # Instalando imghdr separadamente como workaround para Python 3.13+
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERRO] Problema ao baixar pacotes. Verifique sua conexao de rede!${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Todas as dependencias do Python instaladas.${NC}\n"

echo -e "${CYAN}==============================================${NC}"
echo -e "${CYAN}        INICIANDO O MOTOR DO BAGRE BOT        ${NC}"
echo -e "${CYAN}==============================================${NC}"
echo -e "[INFO] Para desligar o bot, pressione CTRL + C"
echo ""

python3 bagre.py
