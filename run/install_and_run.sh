#!/bin/bash
# ==========================================================
#        INSTALADOR E INICIADOR: BAGRE BOT (LINUX)
# ==========================================================
# Este script deve ser acionado com bash: ./install_and_run.sh
# E caso peca permissoes nas bibliotecas raiz, pedira sudo.

echo "[INFO] Iniciando verificacao do ambiente Linux..."

# Checa e instala o FFmpeg e pacotes base de Python no Debian/Ubuntu
if ! command -v ffmpeg &> /dev/null || ! command -v python3-venv &> /dev/null; then
    echo "[AVISO] FFmpeg, python3-pip ou venv nao encontrados."
    echo "[INFO] Tentando instalar os requerimentos do sistema via APT..."
    sudo apt-get update -y
    sudo apt-get install python3 python3-pip python3-venv ffmpeg -y
    
    if [ $? -ne 0 ]; then
        echo -e "\e[31m[ERRO]\e[0m Falha ao baixar FFmpeg/Python pelo APT. Instale manualmente ou rode com servicos sudo."
        exit 1
    fi
    echo "[OK] Requerimentos de Sistema (FFmpeg/Base) Instalados!"
else
    echo "[OK] Dependencias nativas do sistema detectadas (FFmpeg incluído)."
fi

# Cria a VENV isolada
if [ ! -d "venv" ]; then
    echo "[INFO] Criando o ambiente virtual Python (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "\e[31m[ERRO]\e[0m Falha ao criar a maquina virtual Python."
        exit 1
    fi
else
    echo "[OK] Virtual environment (venv) ja existe. Pulando."
fi

# Ativa a VENV e prossegue no ambiente isolado
echo "[INFO] Ativando a Virtual Environment..."
source venv/bin/activate

echo "[INFO] Atualizando PIP e instalando /requirements.txt..."
python3 -m pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "\e[31m[ERRO]\e[0m Houve um problema ao baixar as dependencias PIP no requiments.txt."
    exit 1
fi

echo "[OK] Dependencias do Bot prontas!"
echo "=========================================================="
echo "          INICIANDO O MOTOR DO BAGRE BOT"
echo "=========================================================="
echo "[INFO] Pressione CTRL + C a qualquer hora para desligar."
echo ""
python3 bagre.py
