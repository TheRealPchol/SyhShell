import os
import json
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Исправлено: абсолютный импорт вместо относительного для работы __main__
from consts import *
import zstandard
import tarfile
from pathlib import Path


def get_config():
    if os.path.isfile(CONF_FILE):
        with open(CONF_FILE, "r", encoding="utf-8") as config_file:
            return json.load(config_file)
    return {}

def save_config(config):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(CONF_FILE, "w", encoding="utf-8") as config_file:
        json.dump(config, config_file, ensure_ascii=False, indent=4)

def pack_folder(folder_name: Path, output_file: Path):
    cctx = zstandard.ZstdCompressor(level=10) # Установлен уровень 10
    with open(output_file, "wb") as f_out:
        with cctx.stream_writer(f_out) as zstd_out:
            with tarfile.open(fileobj=zstd_out, mode="w|") as tar:
                for item in folder_name.rglob("*"):
                    # Фильтр, чтобы добавлять только файлы и избежать дублирования
                    if item.is_file():
                        archive_name = item.relative_to(folder_name)
                        tar.add(item, arcname=archive_name)

def unpack_folder(archive_file: Path, extract_to: Path):
    """Функция для обратной распаковки вашего потокового архива"""
    dctx = zstandard.ZstdDecompressor()
    extract_to.mkdir(parents=True, exist_ok=True)
    with open(archive_file, "rb") as f_in:
        with dctx.stream_reader(f_in) as zstd_in:
            # Используем режим "r|" для чтения потокового TAR
            with tarfile.open(fileobj=zstd_in, mode="r|") as tar:
                tar.extractall(path=extract_to)

if __name__ == "__main__":
    # Тест запаковки
    pack_folder(Path("config"), Path("config.tar.zstd"))
    
    # Тест распаковки (раскомментируйте при необходимости)
    # unpack_folder(Path("config.tar.zstd"), Path("extracted_config"))

