import os
import subprocess
import sys
import tempfile
from pathlib import Path

_HELPER = Path(__file__).with_name('_cpp_run_helper.py')


class Compiler():
    def __init__(self, compiler_=None):
        self.comp = compiler_

    def run_file(self, filepath: str, argv=None) -> int:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"file not found: {filepath}")
        cmd = [sys.executable]
        if getattr(sys, 'frozen', False):
            cmd.append('--cpp-run')
        else:
            cmd.append(str(_HELPER))
        cmd += [filepath] + list(argv or [])
        proc = subprocess.run(cmd)
        return proc.returncode

    def run(self, c_code: str, argv=None) -> int:
        with tempfile.NamedTemporaryFile(
                suffix='.cpp', mode='w', encoding='utf-8', delete=False) as tmp:
            tmp.write(c_code)
            tmp_path = tmp.name
        try:
            return self.run_file(tmp_path, argv)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def build(self, outfile: str, infiles, auto_add_suffix: bool = False) -> str:
        if isinstance(infiles, str):
            infiles = [infiles]
        for f in infiles:
            if not os.path.isfile(f):
                raise FileNotFoundError(f"file not found: {f}")
        cmd = [sys.executable]
        if getattr(sys, 'frozen', False):
            cmd.append('--zig-c++')
            cmd += ['c++', '-O2', '-std=c++17', '-o', outfile] + list(infiles)
        else:
            cmd += ['-m', 'ziglang', 'c++',
                    '-O2', '-std=c++17', '-o', outfile] + list(infiles)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or 'zig c++ failed')
        return outfile