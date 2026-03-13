import os
import re
import logging
import json
import yt_dlp
import uuid
from PIL import Image
import sys
import shutil
import time
import tempfile
import threading
import itertools
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from queue import PriorityQueue
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# Fila de downloads global para gerenciar prioridades (Nível 1 = Single, Nível 2 = Playlist)
download_queue = PriorityQueue()
queue_counter = itertools.count()  # Empate: contador sequencial garante FIFO e evita erro de dict < dict

# Dicionário para links de playlists: guarda dict com 'url', 'time' e 'msg_id'
url_cache = {}
CACHE_EXPIRATION_SECONDS = 3600  # 1 hora

def clean_url_cache():
    """Remove entradas do cache que já expiraram."""
    current_time = time.time()
    expired_keys = [k for k, v in url_cache.items() if current_time - v['time'] > CACHE_EXPIRATION_SECONDS]
    for k in expired_keys:
        del url_cache[k]
        logger.info(f"Limpo do cache: {k}")

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)

logger = logging.getLogger(__name__)
YTDLP_LOGGER = logging.getLogger('yt_dlp')

# --- FUNÇÕES AUXILIARES ---

def prepare_telegram_thumb(input_path):
    """Corta a imagem para 1:1, redimensiona para 320x320 e salva como JPG leve."""
    output_path = "thumb_final.jpg"
    try:
        if not os.path.exists(input_path):
            return None
            
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            
            # Corta a imagem para ser quadrada
            width, height = img.size
            min_dim = min(width, height)
            left = (width - min_dim) / 2
            top = (height - min_dim) / 2
            img = img.crop((left, top, left + min_dim, top + min_dim))
            
            # Redimensiona para 320x320e salva
            img.thumbnail((320, 320))
            img.save(output_path, "JPEG", quality=100)
            
        return output_path
    except Exception as e:
        logger.error(f"Erro no Pillow: {e}")
        return None

def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[^\w\s-]', '', name)
    sanitized = re.sub(r'\s+', '_', sanitized).strip()
    return sanitized[:100]

def is_youtube_url(url: str) -> bool:
    return bool(re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$', url))

# --- FUNÇÃO DE DOWNLOAD ---

def clean_youtube_url(url: str) -> str:
    """Remove list e index da URL para forçar download como single video."""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    query_params.pop('list', None)
    query_params.pop('index', None)
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))

def worker_download():
    """Thread em background que processa a PriorityQueue infinitamente."""
    while True:
        try:
            # Pega o próximo item pela prioridade (menor número = maior prioridade)
            priority, count, item_data = download_queue.get()
            
            url = item_data['url']
            update = item_data['update']
            context = item_data['context']
            is_playlist_item = item_data['is_playlist_item']
            user_message_id = item_data.get('user_message_id')
            query_message_id = item_data.get('query_message_id')  # ID da msg do bot pra apagar depois
            
            _process_download(url, update, context, is_playlist_item, user_message_id, query_message_id)
            
        except Exception as e:
            logger.error(f"Erro no worker: {e}")
        finally:
            download_queue.task_done()

def _process_download(url: str, update: Update, context: CallbackContext, is_playlist_item=False, user_message_id=None, query_message_id=None):
    # A implementação pesada original que baixa e manda o audio.
    chat_id = update.effective_chat.id
    status_message = None

    try:
        if query_message_id:
             status_message = type('Object', (), {'message_id': query_message_id})()
        elif not is_playlist_item:
            try:
                status_message = context.bot.send_message(chat_id=chat_id, text="⏳ Xo vê aqui...")
            except:
                pass

        # Cria um diretório temporário para este download específico
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Extrai informações e define nomes
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', 'audio')
                sanitized_title = sanitize_filename(video_title)
                final_audio_path = os.path.join(temp_dir, f"{sanitized_title}.m4a")

            if status_message:
                context.bot.edit_message_text(chat_id=chat_id, message_id=status_message.message_id, text=f"📥 Blz, baixando: {video_title}")

            # 2. Configurações de alta velocidade do yt-dlp
            ydl_opts = {
                'format': 'm4a/bestaudio/best', # Tenta baixar em M4A.
                'writethumbnail': False,
                'ignoreerrors': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(temp_dir, f'{sanitized_title}.%(ext)s'),
                'noplaylist': True,
            }

            # Baixa o áudio
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Baixa a Thumbnail
            thumb_original = None
            thumb_pronta = None
            try:
                thumbnails = info.get('thumbnails', [])
                if thumbnails:
                    best_thumb_url = thumbnails[-1].get('url')
                    if best_thumb_url:
                        ext = best_thumb_url.split('.')[-1].split('?')[0]
                        if not ext.isalpha(): ext = "jpg"
                        
                        import urllib.request
                        thumb_original = os.path.join(temp_dir, f"thumb_manual.{ext}")
                        urllib.request.urlretrieve(best_thumb_url, thumb_original)
            except Exception as e:
                logger.error(f"Erro ao baixar thumb manualmente: {e}")

            # 4. CHECKER da Thumbnail
            if thumb_original:
                if thumb_original.lower().endswith(('.jpg', '.jpeg')):
                    thumb_pronta = os.path.join(temp_dir, "thumb_final.jpg")
                    shutil.copy(thumb_original, thumb_pronta)
                    logger.info("Thumb já era JPG, apenas copiada.")
                else:
                    current_dir = os.getcwd()
                    os.chdir(temp_dir)
                    try:
                        thumb_basename = prepare_telegram_thumb(os.path.basename(thumb_original))
                        if thumb_basename:
                           thumb_pronta = os.path.join(temp_dir, thumb_basename)
                    finally:
                        os.chdir(current_dir)
                    logger.info("Thumb convertida via Pillow.")

            if not os.path.exists(final_audio_path):
                # Fallback caso o yt-dlp tenha salvo como mp3 ou webm
                fallback_path = final_audio_path.replace(".m4a", ".mp3")
                if os.path.exists(fallback_path):
                    final_audio_path = fallback_path
                else:
                    raise FileNotFoundError(f"O arquivo de Áudio não foi criado no disco: {final_audio_path}")

            if status_message:
                context.bot.edit_message_text(chat_id=chat_id, message_id=status_message.message_id, text="🚀 To mandando aqui...")

            # 5. Envio do Áudio
            caption_text = f"<b>🎧 {video_title}</b>\n👤 <code>{info.get('uploader')}</code>\n\n🔗 <a href='{url}'>Link Original</a>"

            with open(final_audio_path, 'rb') as audio_file:
                thumb_handle = None
                if thumb_pronta and os.path.exists(thumb_pronta):
                    thumb_handle = open(thumb_pronta, 'rb')
                
                context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    caption=caption_text,
                    parse_mode='HTML',
                    title=video_title,
                    performer=info.get('uploader'),
                    duration=int(info.get('duration', 0)),
                    thumb=thumb_handle,
                    timeout=180
                )
                if thumb_handle:
                    thumb_handle.close()

            if status_message:
                context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)

    except Exception as e:
        logger.error(f"Erro: {e}")

    finally:
        # 6. LIMPEZA TOTAL
        
        if user_message_id:
            try: context.bot.delete_message(chat_id=chat_id, message_id=user_message_id)
            except: pass

# --- O RESTO DO CÓDIGO (START, HANDLE_MESSAGE, BUTTON_CALLBACK, MAIN) MANTIDO IGUAL ---

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_html(f"Quié?, {update.effective_user.mention_html()}!\n\nManda um link do YouTube.")

def handle_message(update: Update, context: CallbackContext) -> None:
    message_text = update.message.text.strip()
    if is_youtube_url(message_text) and len(message_text.split()) == 1:
        clean_url_cache()  # Limpa links vehlos a cada nova mensagem
        if 'list=' in message_text:
            link_id = str(uuid.uuid4())[:8] 
            url_cache[link_id] = {'url': message_text, 'time': time.time(), 'msg_id': update.message.message_id}
            keyboard = [
                [InlineKeyboardButton("🎵 Baixar só esse vídeo", callback_data=f"single|{link_id}")],
                [InlineKeyboardButton("🎶 Baixar a playlist toda", callback_data=f"playlist|{link_id}")],
            ]
            update.message.reply_text('Link de playlist. Quer o que meu fi?', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            # É vídeo normal
            url_limpa = clean_youtube_url(message_text)
            download_queue.put((1, next(queue_counter), {
                'url': url_limpa,
                'update': update,
                'context': context,
                'is_playlist_item': False,
                'user_message_id': update.message.message_id,
                'query_message_id': None
            }))

def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    action, data_id = query.data.split('|', 1)
    url_data = url_cache.get(data_id)
    url = url_data['url'] if url_data else None
    
    if not url:
        if query.message:
            query.edit_message_text(text="❌ Deu erro aqui k, o link expirou.")
        else:
            context.bot.send_message(chat_id=query.from_user.id, text="❌ O link expirou, tente mandar de novo pra ver se vai k")
        return

    # Se query.message é None, o clique veio do modo Inline
    if query.message:
        chat_obj = query.message.chat
        msg_obj = query.message
        target_chat_id = query.message.chat_id
    else:
        # No modo inline, manda pro privado do usuário que clicou
        chat_obj = query.from_user 
        msg_obj = None
        target_chat_id = query.from_user.id

    # Criamos o objeto fake_update adaptado
    fake_update = type('FakeUpdate', (object,), {
        'effective_chat': chat_obj, 
        'message': msg_obj,
        'effective_user': query.from_user
    })()

    if action == 'single':
        query_msg_id = None
        if query.message:
            query.edit_message_text(text="Tá, baixar só esse aí...")
            query_msg_id = query.message.message_id
        else:
            msg = context.bot.send_message(chat_id=target_chat_id, text="🚀 Xo botar esse na frente aqui...")
            query_msg_id = msg.message_id
        
        url_limpa = clean_youtube_url(url)
        download_queue.put((1, next(queue_counter), {
            'url': url_limpa,
            'update': fake_update,
            'context': context,
            'is_playlist_item': False,
            'user_message_id': url_data.get('msg_id'),
            'query_message_id': query_msg_id
        }))
    
    elif action == 'playlist':
        if query.message:
            query.edit_message_text(text="🤖 Ok, vou fuçar aqui essa playlist. Guenta que eu vou mandando")
            # Em playlist deleta o comando de link da URL
            if url_data.get('msg_id'):
                try: context.bot.delete_message(chat_id=target_chat_id, message_id=url_data.get('msg_id'))
                except: pass
        else:
            context.bot.send_message(chat_id=target_chat_id, text="🤖 Extraindo a playlist...")

        # Roda a extração crua na fila Nível 2
        try:
            with yt_dlp.YoutubeDL({'extract_flat': 'in_playlist', 'quiet': True, 'noplaylist': False}) as ydl:
                info = ydl.extract_info(url, download=False)
                entries = info.get('entries', [])
                
                if entries:
                    for entry in entries:
                        video_url = entry.get('url')
                        if video_url:
                            # Adiciona na fila de playlist com prioridade 2
                            download_queue.put((2, next(queue_counter), {
                                'url': video_url,
                                'update': fake_update,
                                'context': context,
                                'is_playlist_item': True,
                                'user_message_id': None,
                                'query_message_id': None
                            }))
                    
                    if query.message:
                        query.edit_message_text(text=f"📥 {len(entries)} músicas entraram na fila. Vai indo de pouquin")
                    else:
                        context.bot.send_message(chat_id=target_chat_id, text=f"📥 {len(entries)} músicas prontas para baixar. Vai indo de pouquin")
                else:
                    context.bot.send_message(chat_id=target_chat_id, text="Tem pora ninhuma nessa playlist k")
        except Exception as e:
            logger.error(f"Erro ao extrair playlist: {e}")
            context.bot.send_message(chat_id=target_chat_id, text="❌ Vish, deu um problema pra ler essa playlist")

    # Após o uso (seja single ou playlist), descarta o cache daquele botão para não ser reutilizado ou ocupar memória.
    if data_id in url_cache:
        del url_cache[data_id]