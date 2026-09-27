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

    editor = Editor()
    editor.load_initial_files([abs_path])
    editor.run()

