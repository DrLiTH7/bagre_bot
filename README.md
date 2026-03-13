<div align="center">
  <h1>🐟 Bagre Bot</h1>
  <p>Um bot que atua como um YouTube Downloader assíncrono, desenvolvido em Python.</p>
</div>

---

## 🚀 O que o Bagre Bot faz?
Você envia um link (ou vários links) do Youtube no seu chat privado do Telegram ou em um grupo em que o Bot seja ADM, e ele te envia o arquivo de Áudio (MP3/M4A) com as tags corretas, thumbnail do vídeo, autor e título, tudo no formato original mantendo o máximo de qualidade possível.
Se você mandar um link de uma **Playlist** com várias músicas, o bot pergunta se você quer baixar apenas o vídeo solitário ou extrair as músicas listadas nela; em seguida, ele enfileira isso usando manipulações _multi-threaded_ e entrega a música na usa mão.

---

## 🔥 Features

- **Super Veloz**: O bot utiliza `yt-dlp` baixando e unindo trilhas do YouTube usando 10 conexões TCP (threads) simultâneas.
- **Pula Conversões Inúteis**: Sempre tenta extrair a trilha AAC original que a grande maioria dos vídeos gera em seu arquivo nativo (`m4a`), poupando a sua CPU de renderizar em `mp3` e entregando o áudio 2x mais rápido.
- **Fila Flexível (PriorityQueue)**:
  - Links enfileirados de playlists ganham prioridade mínima (Nível 2).
  - Se você jogar um vídeo Solto *enquanto* a sua playlist puxa recursos, o single fura a fila entrando no Nível 1 e é retornado a você primeiro.
- **Limpeza Perfeita de Disco**: Módulos de `TemporaryDirectory` integrados. Nada de MP3 e _webm_ velhos lotando o seu disco, tudo morre ali mesmo no processo local.

---

## 🛠️ Como Instalar (Windows Básico)

Se você estiver em um ambiente Windows:
1. Certifique-se de que o **Python (3.9+)** está baixado da loja da Microsoft/site do Python (e de que "Add to PATH/Variáveis de Ambiente" foi marcado).
2. Tenha o **FFmpeg** configurado no seu sistema. Isso é vital para extrair áudios! [Leia as instruções do FFmpeg abaixo](#-guia-ffmpeg).
3. Clone/baixe este repositório.
4. Entre no arquivo `config.py` pelo seu bloco de notas e altere o `TELEGRAM_TOKEN` com a sua key gerada pelo BotFather. *(NOTA: nunca espalhe isso pela internet!)*
5. Dê dois-cliques no arquivo **`install_and_run.bat`**.
6. Somente isso! Ele vai instalar todos os requirements nativamente pro seu Python, ligar e te avisar assim que puder conversar lá no Telegram!

## 🐧 Como Instalar (Linux / Produção Avançada)

Se quiser subir num servidor GNU/Linux (como Ubuntu ou Debian), você não precisa digitar todos os requirimentos na mão. Criei dois arquivos na pasta `run/` preparados para ambientes de servidor:

### 1. Script de Instalação Automática
Abra o seu terminal na pasta do bot e dê permissão de execução ao script shell que construímos, depois o execute:

```bash
chmod +x run/install_and_run.sh
./run/install_and_run.sh
```
O Script pedirá permissão `sudo` para instalar o **FFmpeg** nativo da distro e pacote de VENV caso você não tenha, e vai levantar o bot sozinho logo na sequência.

### 2. Rodando Perpétuo no Fundo (SystemD Daemon)
Para que o seu bot nunca morra se você fechar o terminal SSH, e reinicie sozinho se o servidor Linux cair (ou atualizar), use o nosso template oficial de SystemD:

1. Edite o arquivo **`run/bagre_bot.service`** colocando os caminhos absolutos corretos de onde você clonou a pasta do bot no seu Linux (Ex: `/home/ubuntu/bagre_bot`), e o seu próprio usuário.
2. Copie ele para a pasta do sistemas de serviços do Linux:
   ```bash
   sudo cp run/bagre_bot.service /etc/systemd/system/
   ```
3. Recarregue os serviços e mande ligar:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable bagre_bot  # Faz iniciar com o Boot do Linux
   sudo systemctl start bagre_bot   # Liga o bot agora
   ```
Pronto! Você pode ver os logs ao vivo a qualquer momento digitando: `sudo journalctl -u bagre_bot -f`.

## ⚠️ Guia FFmpeg (Requisito Especial Exigido pelo Sistema)
O conversor subjacente `yt-dlp` necessita sumariamente do pacote "FFmpeg" para funcionar correntemente no seu sistema local. Se você roda o script `.bat` do Windows e o bot ignora o link gerando uns logs vermelhos sobre FFMPEG não encontrado, você precisará instalar isso:

1. Baixe a build Zipada do Windows para o FFmpeg em algum lugar como: [Gyan FFmpeg Release](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip).
2. Puxe a pasta `bin` existente lá com os 3 EXEs `ffmpeg.exe, ffplay.exe, ffprobe.exe` pra raiz do seu disco local (ex: `C:/ffmpeg/bin`).
3. Digite `Variáveis de Ambiente` no Menu Iniciar do seu Windows -> "Editar as Variáveis de ambiente do sistema".
4. Vá em **Variáveis de Ambiente**. No painel de baixo ou de cima, procure por **Path** e clique na opção **Editar**.
5. Coloque em "Novo", insira o caminho exato (`C:\ffmpeg\bin`), Salve todos os painéis e feche e reabra qualquer terminal. Digite `ffmpeg` num _cmd_ branco e veja os textos subindo na moral (pronto!).

## 🕒 Executando em Background no Windows (Agendador de Tarefas)

Se você deseja que o bot inicie automaticamente com o seu computador de forma invisível (em background), a pasta `run` contém dois arquivos úteis:

1. **`run\run_bagre.bat`**: Inicia o bot usando o executável `pythonw.exe` da nossa Virtual Environment. Esse comando roda o bot na surdina sem abrir nenhuma janela preta incômoda do terminal na sua tela.
2. **`run\q_start.vbs`**: Um script em Visual Basic que chama o arquivo `.bat` acima de forma perfeitamente polida, contornando a tela de comando CMD.

**Como configurar no Agendador de Tarefas:**

1. Abra o **Agendador de Tarefas** do Windows.
2. Clique em **Criar Tarefa Básica...**
3. Dê um nome (ex: "Bagre Bot") e escolha a opção de disparador **"Ao fazer logon"**.
4. Na aba de Ação escolha "Iniciar um programa".
5. Em Programa/script, clique em *Procurar* e selecione o arquivo **`q_start.vbs`** localizado na sua pasta de execução (ex: `C:\Users\Fingolfin\Documents\Projetos\bagre\run\q_start.vbs`).
6. Conclua a tarefa. O seu bot agora acordará silenciosamente na bandeja do sistema sempre que você acessar seu usuário no PC!
=======
# bagre_bot
Youtube audio downloader bot for Telegram
