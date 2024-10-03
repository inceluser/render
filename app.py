from flask import Flask, render_template, request, jsonify, send_file
from pytube import Search
import yt_dlp
import os
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

DOWNLOAD_FOLDER = 'downloads'
CLEANUP_INTERVAL = 300  # 5 минут
FILE_EXPIRATION_TIME = 300  # Удаляем файлы старше 5 минут
DOWNLOAD_INTERVAL = 10  # Интервал в секундах между загрузками
DOWNLOAD_LIMIT = 1  # Максимальное количество загрузок за интервал

# Словарь для хранения времени загрузок для каждого IP
download_times = {}

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def cleanup_download_folder():
    """Функция для удаления старых файлов из папки downloads."""
    while True:
        now = datetime.now()
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                # Удаляем файл, если он старше FILE_EXPIRATION_TIME
                if now - file_mod_time > timedelta(seconds=FILE_EXPIRATION_TIME):
                    try:
                        os.remove(file_path)
                        print(f"Deleted old file: {filename}")
                    except Exception as e:
                        print(f"Error deleting file {filename}: {str(e)}")
        time.sleep(CLEANUP_INTERVAL)  # Пауза перед следующей проверкой

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = request.form['query']
        search = Search(query)
        videos = search.results[:5]  # Ограничиваем результаты до 5 видео
        return render_template('index.html', videos=videos)
    return render_template('index.html', videos=[])

@app.route('/download/<video_id>', methods=['GET'])
def download(video_id):
    ip_address = request.remote_addr  # Получаем IP-адрес пользователя
    current_time = datetime.now()

    # Проверяем, есть ли записи о загрузках для данного IP-адреса
    if ip_address not in download_times:
        download_times[ip_address] = []

    # Удаляем записи, которые старше DOWNLOAD_INTERVAL
    download_times[ip_address] = [t for t in download_times[ip_address] if current_time - t < timedelta(seconds=DOWNLOAD_INTERVAL)]

    # Проверяем, превышает ли количество загрузок лимит
    if len(download_times[ip_address]) >= DOWNLOAD_LIMIT:
        return jsonify({'success': False, 'error': 'Please wait before downloading again.'})

    # Записываем текущее время загрузки
    download_times[ip_address].append(current_time)

    url = f'https://www.youtube.com/watch?v={video_id}'
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
            'Referer': 'https://www.youtube.com/',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            {
                'key': 'EmbedThumbnail',
            },
            {
                'key': 'FFmpegMetadata',
            }
        ],
        'writethumbnail': True,
        'embedthumbnail': True,
        'addmetadata': True,
        # Добавляем прокси
        'proxy': '212.127.93.185:8081',  # Указываем прокси-сервер
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')

            # Отправляем файл пользователю
            return send_file(filename, as_attachment=True)

    except yt_dlp.DownloadError as e:
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Запускаем поток для очистки папки downloads
    cleanup_thread = threading.Thread(target=cleanup_download_folder, daemon=True)
    cleanup_thread.start()
    
    # Убедитесь, что приложение слушает на нужном хосте и порту
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
