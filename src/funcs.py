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
import io
import itertools
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from queue import PriorityQueue
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Fila de downloads assíncrona para gerenciar prioridades
download_queue = None

def get_queue():
    global download_queue
    if download_queue is None:
        download_queue = asyncio.PriorityQueue()
    return download_queue

queue_counter = itertools.count()  # Empate: contador sequencial garante FIFO

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

def prepare_telegram_thumb(input_bytes_io):
    """Corta a imagem para 1:1, redimensiona para 320x320 e salva num buffer JPG na memória."""
    if not input_bytes_io:
        return None
    try:
        with Image.open(input_bytes_io) as img:
            img = img.convert("RGB")
            
            # Corta a imagem para ser quadrada
            width, height = img.size
            min_dim = min(width, height)
            left = (width - min_dim) / 2
            top = (height - min_dim) / 2
            img = img.crop((left, top, left + min_dim, top + min_dim))
            
            # Redimensiona para 320x320 e salva
            img.thumbnail((320, 320))
            output_io = io.BytesIO()
            img.save(output_io, "JPEG", quality=50, optimize=True)
            output_io.seek(0)
            output_io.name = "thumb_final.jpg"
            return output_io
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

def fetch_yt_audio(url: str):
    """Executa a extração síncrona do urllib e do yt-dlp. Rodará no ThreadPool via asyncio.to_thread."""
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'quiet': True,
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_title = info.get('title', 'audio')
        sanitized_title = sanitize_filename(video_title)
        direct_url = info.get('url')
        headers = info.get('http_headers', {})

    if not direct_url:
        raise ValueError("Não consegui achar o link direto de stream do YouTube.")

    import urllib.request
    req = urllib.request.Request(direct_url, headers=headers)
    audio_buffer = io.BytesIO()
    with urllib.request.urlopen(req) as response:
        audio_buffer.write(response.read())
    
    audio_buffer.seek(0)
    audio_buffer.name = f"{sanitized_title}.m4a"

    thumb_buffer = None
    thumbnails = info.get('thumbnails', [])
    if thumbnails:
        best_thumb_url = thumbnails[-1].get('url')
        if best_thumb_url:
            thumb_req = urllib.request.Request(best_thumb_url, headers=headers)
            try:
                with urllib.request.urlopen(thumb_req) as t_resp:
                    raw_thumb_buffer = io.BytesIO(t_resp.read())
                    thumb_buffer = prepare_telegram_thumb(raw_thumb_buffer)
            except Exception as e:
                logger.error(f"Erro ao processar thumbnail em memória: {e}")
                
    return audio_buffer, thumb_buffer, video_title, info
    
async def worker_download():
    """Tarefa assíncrona que consome a fila nativamente."""
    queue = get_queue()
    while True:
        try:
            priority, count, item_data = await queue.get()
            
            url = item_data['url']
            update = item_data['update']
            context = item_data['context']
            is_playlist_item = item_data['is_playlist_item']
            user_message_id = item_data.get('user_message_id')
            query_message_id = item_data.get('query_message_id')
            
            await _process_download(url, update, context, is_playlist_item, user_message_id, query_message_id)
            
        except Exception as e:
            logger.error(f"Erro no worker: {e}")
        finally:
            queue.task_done()

async def _process_download(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE, is_playlist_item=False, user_message_id=None, query_message_id=None):
    # Processamento 100% em memória usando io.BytesIO via hooks NATIVOS
    chat_id = update.effective_chat.id
    status_message = None

    try:
        if query_message_id:
             status_message = type('Object', (), {'message_id': query_message_id})()
        elif not is_playlist_item:
            try:
                status_message = await context.bot.send_message(chat_id=chat_id, text="⏳ Xo vê aqui...")
            except:
                pass

        if status_message:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message.message_id, text=f"📥 Blz, puxando o áudio...")

        # Envia o fetch pesado pro background
        try:
            audio_buffer, thumb_buffer, video_title, info = await asyncio.to_thread(fetch_yt_audio, url)
        except Exception as e:
            if status_message:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message.message_id, text="❌ Ocorreu um erro baixando. Talvez protegido ou geofenced.")
            return

        if status_message:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_message.message_id, text=f"📦 Baixando para a RAM: {video_title}\n🚀 To mandando aqui...")

        # 4. Envio do Áudio
        caption_text = f"<b>🎧 {video_title}</b>\n👤 <code>{info.get('uploader')}</code>\n\n🔗 <a href='{url}'>Link Original</a>"

        await context.bot.send_audio(
            chat_id=chat_id,
            audio=audio_buffer,
            caption=caption_text,
            parse_mode='HTML',
            title=video_title,
            performer=info.get('uploader'),
            duration=int(info.get('duration', 0)),
            thumb=thumb_buffer,
            read_timeout=180,
            write_timeout=180,
            connect_timeout=180
        )

        if status_message:
            await context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)

    except Exception as e:
        logger.error(f"Erro crítico assíncrono: {e}")

    finally:
        if user_message_id:
            try: await context.bot.delete_message(chat_id=chat_id, message_id=user_message_id)
            except: pass

# --- O RESTO DO CÓDIGO (START, HANDLE_MESSAGE, BUTTON_CALLBACK, MAIN) MANTIDO IGUAL ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(f"Quié?, {update.effective_user.mention_html()}!\n\nManda um link do YouTube.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            await update.message.reply_text('Link de playlist. Quer o que meu fi?', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            # É vídeo normal
            url_limpa = clean_youtube_url(message_text)
            queue = get_queue()
            await queue.put((1, next(queue_counter), {
                'url': url_limpa,
                'update': update,
                'context': context,
                'is_playlist_item': False,
                'user_message_id': update.message.message_id,
                'query_message_id': None
            }))

def fetch_yt_playlist(url: str):
    with yt_dlp.YoutubeDL({'extract_flat': 'in_playlist', 'quiet': True, 'noplaylist': False}) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('entries', [])

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    action, data_id = query.data.split('|', 1)
    url_data = url_cache.get(data_id)
    url = url_data['url'] if url_data else None
    
    if not url:
        if query.message:
            await query.edit_message_text(text="❌ Deu erro aqui k, o link expirou.")
        else:
            await context.bot.send_message(chat_id=query.from_user.id, text="❌ O link expirou, tente mandar de novo pra ver se vai k")
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
            await query.edit_message_text(text="Tá, baixar só esse aí...")
            query_msg_id = query.message.message_id
        else:
            msg = await context.bot.send_message(chat_id=target_chat_id, text="🚀 Xo botar esse na frente aqui...")
            query_msg_id = msg.message_id
        
        url_limpa = clean_youtube_url(url)
        queue = get_queue()
        await queue.put((1, next(queue_counter), {
            'url': url_limpa,
            'update': fake_update,
            'context': context,
            'is_playlist_item': False,
            'user_message_id': url_data.get('msg_id'),
            'query_message_id': query_msg_id
        }))
    
    elif action == 'playlist':
        if query.message:
            await query.edit_message_text(text="🤖 Ok, vou fuçar aqui essa playlist. Guenta que eu vou mandando")
            # Em playlist deleta o comando de link da URL
            if url_data.get('msg_id'):
                try: await context.bot.delete_message(chat_id=target_chat_id, message_id=url_data.get('msg_id'))
                except: pass
        else:
            await context.bot.send_message(chat_id=target_chat_id, text="🤖 Extraindo a playlist...")

        # Roda a extração crua na fila Nível 2
        try:
            entries = await asyncio.to_thread(fetch_yt_playlist, url)
            if entries:
                queue = get_queue()
                for entry in entries:
                    video_url = entry.get('url')
                    if video_url:
                        # Adiciona na fila de playlist com prioridade 2
                        await queue.put((2, next(queue_counter), {
                            'url': video_url,
                            'update': fake_update,
                            'context': context,
                            'is_playlist_item': True,
                            'user_message_id': None,
                            'query_message_id': None
                        }))
                
                if query.message:
                    await query.edit_message_text(text=f"📥 {len(entries)} músicas entraram na fila. Vai indo de pouquin")
                else:
                    await context.bot.send_message(chat_id=target_chat_id, text=f"📥 {len(entries)} músicas prontas para baixar. Vai indo de pouquin")
            else:
                await context.bot.send_message(chat_id=target_chat_id, text="Tem pora ninhuma nessa playlist k")
        except Exception as e:
            logger.error(f"Erro ao extrair playlist: {e}")
            await context.bot.send_message(chat_id=target_chat_id, text="❌ Vish, deu um problema pra ler essa playlist")

    # Após o uso (seja single ou playlist), descarta o cache daquele botão para não ser reutilizado ou ocupar memória.
    if data_id in url_cache:
        del url_cache[data_id]