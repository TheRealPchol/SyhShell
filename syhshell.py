import argparse
from datetime import datetime
import os
import difflib
import json
import shlex
import sys
import time
import traceback
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import InMemoryHistory
import gzip
import shutil
from dataclasses import dataclass
from utils import pyvim
from utils import lua

# ─── Config ───────────────────────────────────────────────

@dataclass
class SyhConfig:
    homedir: str = os.getcwd()
    aliases: dict[str, str] | None = None
    homedir_replace_char: str = "~/"

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = {"cls": "clear"}

# ─── Kaa editor ──────────────────────────────────────────

def run():
    print('Kaa is not installed or not supported.')

try:
    from kaa.cui.main import run
    KAAEDIT = True
except ImportError:
    KAAEDIT = False

# ─── History / aliases / info ────────────────────────────

_history = InMemoryHistory()
aliases = {"cls": "clear"}

class info:
    VERSION = "ss26.09.1"

# ─── Logging ─────────────────────────────────────────────

def log(log_text, config_filename: str = 'config.json'):
    if os.path.isfile(config_filename):
        with open(config_filename, 'r') as fl:
            config = json.load(fl)
        if config.get("debug_level", 0) > 0:
            with open("latest.log", 'a+') as fi:
                fi.write(f'\n[{str(datetime.now()).split(".")[0]}] {log_text}')
        if config.get('debug_level', 0) > 1:
            print(f'\033[1;38m[DEBUG] [{str(datetime.now()).split(".")[0]}] {log_text}\033[0m ')

def log_(func):
    def waper(*args, **kwargs):
        log(f"[DEBUG] Start executing function {str(func.__name__)}.")
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            log(f"[ERROR] Error in executing function {str(func.__name__)} {str(type(e).__name__)}: {e}")
        finally:
            log(f"[DEBUG] End of executing function {str(func.__name__)}")
            return result
    return waper

# ─── Custom exception for clean exit ─────────────────────

class ExitShell(Exception):
    pass

# ─── Tools ───────────────────────────────────────────────

class Tools:
    @staticmethod
    @log_
    def clear_screen():
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    @log_
    def get_time_and_date():
        return str(datetime.now()).split('.')[0]

    @staticmethod
    @log_
    def get_date():
        return str(datetime.now()).split(' ')[0]

    @staticmethod
    @log_
    def get_time():
        return str(datetime.now()).split(' ')[1].split('.')[0]

    @staticmethod
    @log_
    def get_args(text: str, start_char: str, end_char: str) -> str:
        start_idx = text.find(start_char)
        end_idx = text.rfind(end_char)
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return text[start_idx + len(start_char):end_idx]
        return ""

    @staticmethod
    @log_
    def _input(prompt_text: str) -> str:
        formatted = ANSI(prompt_text)
        return prompt(formatted, history=_history)

    @staticmethod
    def compress_to_gz(source_file, output_file):
        """Сжимает source_file в output_file и удаляет исходник."""
        if not os.path.exists(source_file):
            return
        try:
            with open(source_file, "rb") as f_in:
                with gzip.open(output_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(source_file)
        except Exception as e:
            raise Exception(e)

# ─── Shell ───────────────────────────────────────────────

class Shell:
    @log_
    def __init__(self, username='root', hostname='SyhShell'):
        self.commands = [
            "echo", "cls", "clear", "exit",
            "time", "date", "tad", "clock",
            "cd", "ls", "rd",
            "kaaedit", "pyvim",
            "touch",
            "alias", "unalias",
            "py", "tcc", "cpp",
        ]
        self.username = username
        self.hostname = hostname
        self.root = True

    def _fix_slashes(self, args: list[str]) -> list[str]:
        fixed_args = []
        skip = False
        for i in range(len(args)):
            if skip:
                skip = False
                continue
            item = args[i]
            while item.endswith("\\") and (i + 1) < len(args):
                item = item[:-1] + " " + args[i + 1]
                i += 1
                skip = True
            fixed_args.append(item)
        return fixed_args

    def _tcc_run(self, args):
        if not args:
            print("usage: tcc run <file.c> [args...]")
            return
        try:
            from compilers.c import Compiler
            rc = Compiler().run_file(args[0], args[1:])
            if rc:
                print(f"tcc: exit code {rc}")
        except Exception as e:
            print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

    def _tcc_build(self, args):
        infiles = []
        outfile = None
        i = 0
        while i < len(args):
            a = args[i]
            if a in ('-i', '--input') and i + 1 < len(args):
                infiles.append(args[i + 1])
                i += 2
                continue
            if a in ('-o', '--output') and i + 1 < len(args):
                outfile = args[i + 1]
                i += 2
                continue
            i += 1
        if not infiles or outfile is None:
            print("usage: tcc build -i <input.c> -o <output.elf/exe>")
            return
        try:
            from compilers.c import Compiler
            path = Compiler().build(outfile, infiles)
            print(f"Build OK: {path}")
        except Exception as e:
            print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

    def _cpp_run(self, args):
        if not args:
            print("usage: cpp run <file.cpp> [args...]")
            return
        try:
            from compilers.cpp import Compiler
            rc = Compiler().run_file(args[0], args[1:])
            if rc:
                print(f"cpp: exit code {rc}")
        except Exception as e:
            print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

    def _cpp_build(self, args):
        infiles = []
        outfile = None
        i = 0
        while i < len(args):
            a = args[i]
            if a in ('-i', '--input') and i + 1 < len(args):
                infiles.append(args[i + 1])
                i += 2
                continue
            if a in ('-o', '--output') and i + 1 < len(args):
                outfile = args[i + 1]
                i += 2
                continue
            i += 1
        if not infiles or outfile is None:
            print("usage: cpp build -i <input.cpp> -o <output.elf/exe>")
            return
        try:
            from compilers.cpp import Compiler
            path = Compiler().build(outfile, infiles)
            print(f"Build OK: {path}")
        except Exception as e:
            print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

    def shell_env(self):
        print('Welcome to the SisyphShell')
        print(f'Version: {info.VERSION}')
        print(f"Build: 1")
        while True:
            try:
                stat = '#' if self.root else "$"
                prompt_text = (
                    f"\033[1;32m{self.username}@{self.hostname}\033[0m:"
                    f"\033[1;34m{os.getcwd()} \033[1;31m[{Tools.get_time()}]\033[0m {stat} "
                )
                text = Tools._input(prompt_text).strip()
                if not text:
                    continue
                self.execute_line(text)
            except ExitShell:
                break
            except KeyboardInterrupt:
                print()
                break
            except EOFError:
                print()
                break
            except Exception as e:
                print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

    def execute_line(self, line: str):
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        # Разрешение алиасов
        if cmd in aliases:
            alias_value = aliases[cmd]
            try:
                alias_parts = shlex.split(alias_value)
            except ValueError:
                alias_parts = alias_value.split()
            if alias_parts:
                cmd = alias_parts[0].lower()
                args = alias_parts[1:] + args

        # ── exit ──
        if cmd == "exit":
            raise ExitShell()

        # ── alias / unalias ──
        elif cmd == 'alias':
            if args:
                arg_str = ' '.join(args)
                if '=' in arg_str:
                    name, value = arg_str.split('=', 1)
                    aliases[name.strip().lower()] = value.strip().strip("'\"")
                return
            else:
                for name, value in aliases.items():
                    print(f"{name}='{value}'")
                return

        elif cmd == 'unalias':
            for name in args:
                name_lower = name.lower()
                if name_lower in aliases:
                    del aliases[name_lower]
            return

        # ── Основные команды ──
        elif cmd == 'echo':
            print(' '.join(args))

        elif cmd in ('clear', 'cls'):
            Tools.clear_screen()

        elif cmd == 'time':
            print(Tools.get_time())

        elif cmd == 'date':
            print(Tools.get_date())

        elif cmd == 'tad':
            print(Tools.get_time_and_date())

        elif cmd == 'cd':
            args = self._fix_slashes(args)
            if args:
                try:
                    os.chdir(args[0])
                except Exception as e:
                    print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

        elif cmd == 'ls':
            show_hidden = "-a" in args
            pure_args = [a for a in args if a != "-a"]
            pure_args = self._fix_slashes(pure_args)
            target_dir = pure_args[0] if pure_args else os.getcwd()
            try:
                otp = os.listdir(target_dir)
                if not show_hidden:
                    otp = [f for f in otp if not f.startswith('.')]
                if otp:
                    print('\n'.join(otp))
            except Exception as e:
                print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

        elif cmd == 'rd':
            args = self._fix_slashes(args)
            if args:
                try:
                    with open(args[0], 'r', encoding='utf-8') as f:
                        print(f.read())
                except Exception as e:
                    print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

        elif cmd == 'clock':
            try:
                while True:
                    print(Tools.get_time_and_date())
                    time.sleep(1)
            except (EOFError, KeyboardInterrupt):
                pass

        elif cmd == 'kaaedit':
            run()

        elif cmd == 'pyvim':
            t = self._fix_slashes(args)
            if t:
                pyvim.open(t[0])
            else:
                print("usage: pyvim <file>")

        elif cmd == 'touch':
            args = self._fix_slashes(args)
            if args:
                try:
                    with open(args[0], 'x'):
                        pass
                except Exception as e:
                    print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

        elif cmd == 'py':
            args = self._fix_slashes(args)
            viz_zone = {}
            if args:
                if os.path.isfile(args[0]):
                    try:
                        with open(args[0], 'r', encoding='utf-8') as fl:
                            a = fl.read()
                        exec(a, viz_zone)
                    except Exception as e:
                        print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
                else:
                    print(f"File not found: {args[0]}")

        elif cmd == 'tcc':
            args = self._fix_slashes(args)
            if not args:
                print("usage: tcc run <file.c> [args...] | tcc build -i <input.c> -o <output.elf/exe>")
            elif args[0] == 'run':
                self._tcc_run(args[1:])
            elif args[0] == 'build':
                self._tcc_build(args[1:])
            else:
                print("tcc: unknown subcommand; use 'run' or 'build'")

        elif cmd == 'cpp':
            args = self._fix_slashes(args)
            if not args:
                print("usage: cpp run <file.cpp> [args...] | cpp build -i <input.cpp> -o <output.elf/exe>")
            elif args[0] == 'run':
                self._cpp_run(args[1:])
            elif args[0] == 'build':
                self._cpp_build(args[1:])
            else:
                print("cpp: unknown subcommand; use 'run' or 'build'")
        
        elif cmd == "lua":
            args = self._fix_slashes(args)

            if len(args) > 0:
                runtime = lua.LuaInterpreter()
                if os.path.isfile(args[0]):
                    with open(args[0], "r", encoding="utf-8") as ff:
                        content = ff.readlines()
                    runtime.exec_lines(content)
            else:
                print("Usage: lua [filename].lua")

        else:
            matches = difflib.get_close_matches(cmd, self.commands, n=3, cutoff=0.6)
            suggestion = '\n'.join(matches) if matches else 'No suggestions.'
            print(f'\033[1;31mCommand not found: \033[0m{cmd}\n\033[1;31mDid you mean:\033[0m\n{suggestion}')

# ─── Entry point ─────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            from compilers._frozen_dispatch import dispatch
            rc = dispatch(sys.argv)
            if rc is not None:
                sys.exit(rc)
        except ImportError:
            pass
    try:
        Tools.clear_screen()
        shel = Shell()
        shel.shell_env()
    finally:
        Tools.compress_to_gz("latest.log", f"{str(datetime.now()).split('.')[0]}.gz")

