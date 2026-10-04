import os
import asyncio
from pyvim.editor import Editor


def open(filepath):
    abs_path = os.path.abspath(filepath)

    # Python 3.12+ не создаёт event loop автоматически
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    # ─── Кроссплатформенная подмена пути конфига ───
    # pyvim использует os.path.expanduser('~/.pyvimrc') и os.path.expanduser('~/.pyvim')
    # Патчим expanduser только на время работы редактора
    _real_expanduser = os.path.expanduser

    # Путь к нашей директории с конфигами (относительно utils/pyvim.py)
    _base_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'root', 'data', 'appdata'
    )

    def _fake_expanduser(path):
        if path.startswith('~/.pyvim'):
            return path.replace('~/.pyvim', _base_dir, 1)
        return _real_expanduser(path)

    os.path.expanduser = _fake_expanduser

    try:
        editor = Editor()
        editor.load_initial_files([abs_path])
        editor.run()
    finally:
        os.path.expanduser = _real_expanduser

