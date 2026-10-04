import argparse
from datetime import datetime
import os
import difflib
import json
import shlex
import sys
import time
import traceback
import inspect
import subprocess
import gzip
import shutil
import glob
import functools
import importlib.util
from dataclasses import dataclass, fields

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import InMemoryHistory

from utils import pyvim
from utils import lua
from compilers import sisyph


# ─── Config ───────────────────────────────────────────────

@dataclass
class SyhConfig:
    homedir: str = os.path.dirname(os.path.abspath(__file__))
    aliases: dict[str, str] | None = None
    homedir_replace_char: str = "~/"
    startup_script: str = ".syhrc"
    ROOT: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "root")
    ROOT_BIN: str = os.path.join(ROOT, "bin")
    ROOT_DATA: str = os.path.join(ROOT, "data")

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = {}


# ─── Themes ──────────────────────────────────────────────

@dataclass
class Theme:
    """Цветовая тема шелла. Все значения — ANSI escape-последовательности."""
    # Prompt foreground
    prompt_user: str = "\033[1;32m"
    prompt_host: str = "\033[1;32m"
    prompt_cwd: str = "\033[1;34m"
    prompt_time: str = "\033[1;31m"
    prompt_root: str = "#"
    prompt_user_sym: str = "$"
    prompt_reset: str = "\033[0m"

    # Prompt background
    prompt_bg: str = ""              # общий фон промпта
    prompt_user_bg: str = ""         # фон секции user@host
    prompt_cwd_bg: str = ""          # фон секции cwd
    prompt_time_bg: str = ""         # фон секции времени
    
    # Global shell background
    shell_bg: str = ""              # общий фон всего терминала

    # Messages
    success: str = "\033[1;32m"
    error: str = "\033[1;31m"
    warning: str = "\033[1;33m"
    debug: str = "\033[1;38m"
    info: str = "\033[1;37m"
    reset: str = "\033[0m"

    @classmethod
    def default(cls) -> "Theme":
        return cls()

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

def load_theme(theme_name: str = "modern") -> Theme:
    if theme_name == "default":
        return Theme.default()
    theme_path = os.path.join(SyhConfig.ROOT_DATA, "themes", f"{theme_name}.json")
    if not os.path.isfile(theme_path):
        log(f"Theme '{theme_name}' not found at {theme_path}, using default")
        return Theme.default()
    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        theme = Theme.from_dict(data)
        log(f"Loaded theme: {theme_name}")
        return theme
    except Exception as e:
        log(f"Failed to load theme '{theme_name}': {e}, using default")
        return Theme.default()


# ─── Kaa editor ──────────────────────────────────────────

def _kaa_stub():
    print('Kaa is not installed or not supported.')

try:
    from kaa.cui.main import run as _kaa_run
    KAAEDIT = True
except ImportError:
    _kaa_run = _kaa_stub
    KAAEDIT = False


# ─── History / aliases / info ────────────────────────────

_history = InMemoryHistory()
aliases = {"cls": "clear"}


class info:
    VERSION = "ss26.09.1"


# ─── Logging ─────────────────────────────────────────────

def log(log_text, config_filename: str = 'config.json'):
    config_path = os.path.join(SyhConfig.ROOT_DATA, config_filename)
    if os.path.isfile(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as fl:
                config = json.load(fl)
        except Exception:
            config = {}
        if config.get("debug_level", 0) > 0:
            with open("latest.log", 'a+') as fi:
                fi.write(f'\n[{str(datetime.now()).split(".")[0]}] {log_text}')
        if config.get('debug_level', 0) > 1:
            print(f'\033[1;38m[DEBUG] [{str(datetime.now()).split(".")[0]}] {log_text}\033[0m ')


def log_(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        log(f"[DEBUG] Start executing function {func.__name__}.")
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            log(f"[ERROR] Error in executing function {func.__name__} {type(e).__name__}: {e}")
            raise
        finally:
            log(f"[DEBUG] End of executing function {func.__name__}")
        return result
    return wrapper


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
        session = PromptSession(history=_history)
        return session.prompt(formatted)

    @staticmethod
    @log_
    def theme_print(text: str, theme: Theme = None, style: str = ""):
        """Выводит текст с учётом темы и стиля.
        
        Args:
            text: Текст для вывода
            theme: Объект темы (если None, используется Theme.default())
            style: Стиль вывода ("success", "error", "warning", "info", "debug")
        """
        if theme is None:
            theme = Theme.default()
        
        if style:
            style_code = getattr(theme, style, "")
            print(f"{style_code}{text}{theme.reset}")
        else:
            print(text)

    @staticmethod
    def compress_to_gz(source_file, output_file):
        if not os.path.exists(source_file):
            return
        try:
            with open(source_file, "rb") as f_in:
                with gzip.open(output_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(source_file)
        except Exception as e:
            raise Exception(e)


# ─── Shell ────────────────────────────────────────────────

class Shell:

    @staticmethod
    @log_
    def _call_function_from_file(file_path, function_name, *args, **kwargs):
        if not os.path.exists(file_path):
            dotted_as_path = file_path.replace(".", os.sep) + ".py"
            candidate = os.path.join(SyhConfig.homedir, dotted_as_path)
            if os.path.isfile(candidate):
                file_path = candidate
            else:
                candidate_root = os.path.join(SyhConfig.ROOT, dotted_as_path)
                if os.path.isfile(candidate_root):
                    file_path = candidate_root
                else:
                    raise ImportError(
                        f"Could not load file from path: {file_path} "
                        f"(also tried: {candidate}, {candidate_root})"
                    )

        module_name = os.path.splitext(os.path.basename(file_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec for: {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, function_name):
            raise AttributeError(f"Function '{function_name}' not found in {file_path}")

        target_function = getattr(module, function_name)

        if target_function is None:
            raise AttributeError(
                f"'{function_name}' exists in {file_path} but is None. "
                f"Available callables: {[n for n in dir(module) if callable(getattr(module, n)) and not n.startswith('_')]}"
            )
        if not callable(target_function):
            raise AttributeError(
                f"'{function_name}' in {file_path} is not callable (type={type(target_function).__name__}). "
                f"Available callables: {[n for n in dir(module) if callable(getattr(module, n)) and not n.startswith('_')]}"
            )

        try:
            sig = inspect.signature(target_function)
            accepts_args = any(
                p.name == "args"
                for p in sig.parameters.values()
                if p.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                    inspect.Parameter.VAR_POSITIONAL,
                )
            )
            if accepts_args:
                return target_function(*args, **kwargs)
            else:
                log(f"'{function_name}' does not accept 'args', calling without")
                return target_function()
        except (ValueError, TypeError):
            try:
                return target_function(*args, **kwargs)
            except TypeError:
                log(f"'{function_name}' rejected args via fallback, calling without")
                return target_function()

    @log_
    def __init__(self, username='root', hostname='SyhShell'):
        self._builtin_commands = [
            "echo", "cls", "clear", "exit",
            "time", "date", "tad", "clock",
            "cd", "ls", "rd", "rm", "rmd", "mkdir",
            "kaaedit", "pyvim",
            "touch",
            "alias", "unalias",
            "py", "tcc", "cpp", "lua", "syh",
            "sss", "reload-configs", "logs", "execute",
            "theme",
        ]

        self._external_apps: dict[str, dict] = {}
        self._load_external_apps()
        self._load_bin_directory()

        self.commands = self._builtin_commands + list(self._external_apps.keys())

        self.username = username
        self.hostname = hostname
        self.root = True
        self.theme = load_theme("default")
        self.session = PromptSession(history=InMemoryHistory())

    def _load_external_apps(self):
        config_path = os.path.join(SyhConfig.ROOT_DATA, "appconfig.json")
        if not os.path.isfile(config_path):
            log(f"App config not found: {config_path}")
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, meta in data.items():
                if not isinstance(meta, dict):
                    log(f"Invalid app entry '{name}': expected dict")
                    continue
                if "command" not in meta:
                    log(f"Invalid app entry '{name}': missing 'command' field")
                    continue
                key = name.strip().lower()
                if key in self._builtin_commands:
                    log(f"External app '{key}' shadows builtin command, skipping")
                    continue
                self._external_apps[key] = meta
                log(f"Registered external app: {key}")
        except Exception as e:
            log(f"Failed to load appconfig.json: {e}")

    def _load_bin_directory(self):
        bin_dir = SyhConfig.ROOT_BIN
        if not os.path.isdir(bin_dir):
            log(f"Bin directory not found: {bin_dir}")
            return
        executable_extensions = {'.py', '.sh', '.bat', '.cmd', '.exe'}
        for entry in os.listdir(bin_dir):
            full_path = os.path.join(bin_dir, entry)
            if not os.path.isfile(full_path):
                continue
            _, ext = os.path.splitext(entry)
            is_executable = os.access(full_path, os.X_OK) or ext.lower() in executable_extensions
            if not is_executable:
                continue
            key = entry.strip().lower()
            if key in self._builtin_commands or key in self._external_apps:
                log(f"Bin executable '{key}' already registered, skipping")
                continue
            self._external_apps[key] = {
                "name": entry,
                "command": full_path,
                "source": "bin_directory",
            }
            log(f"Registered bin executable: {key}")

    def _expand_glob(self, args: list[str]) -> list[str]:
        expanded = []
        for arg in args:
            matches = glob.glob(arg)
            if matches:
                expanded.extend(matches)
            else:
                expanded.append(arg)
        return expanded

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

    def run_sss(self, filename):
        if not os.path.exists(filename):
            return
        try:
            with open(filename, "r", encoding="utf-8") as fff:
                lines = fff.readlines()
        except Exception as e:
            t = self.theme
            print(f"{t.error}Error reading '{filename}': {e}{t.reset}")
            return
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("~~") or stripped.startswith("#"):
                continue
            try:
                self.execute_line(stripped)
            except ExitShell:
                break
            except Exception as e:
                t = self.theme
                print(f"{t.error}{filename}:{line_num}: {e}{t.reset}")

    def _reload_configs(self):
        old_apps = set(self._external_apps.keys())
        self._external_apps.clear()
        self._load_external_apps()
        self._load_bin_directory()
        self.commands = self._builtin_commands + list(self._external_apps.keys())
        new_apps = set(self._external_apps.keys())
        added = new_apps - old_apps
        removed = old_apps - new_apps
        t = self.theme
        print(f"{t.success}Configs reloaded.{t.reset}")
        print(f"  Apps: {len(self._external_apps)} total")
        if added:
            print(f"  {t.success}+ Added:{t.reset} {', '.join(sorted(added))}")
        if removed:
            print(f"  {t.error}- Removed:{t.reset} {', '.join(sorted(removed))}")
        if not added and not removed:
            print(f"  No changes detected.")
        log(f"Configs reloaded: {len(added)} added, {len(removed)} removed")

    def shell_env(self):
        t = self.theme
        
        # Применяем глобальный бэкграунд если установлен
        if t.shell_bg:
            print(f"{t.shell_bg}{t.reset}", end="")
        
        print(f'{t.info}Welcome to the SisyphShell{t.reset}')
        print(f'{t.info}Version: {info.VERSION}{t.reset}')
        print(f"{t.info}Build: 1{t.reset}")

        startup_path = os.path.join(SyhConfig.homedir, SyhConfig.startup_script)
        self.run_sss(startup_path)

        while True:
            try:
                t = self.theme
                stat = t.prompt_root if self.root else t.prompt_user_sym
                cwd = os.getcwd()
                display_cwd = cwd.replace(SyhConfig.homedir, SyhConfig.homedir_replace_char)

                # Формируем промпт с поддержкой глобального бэкграунда
                prompt_parts = []
                
                if t.shell_bg:
                    prompt_parts.append(t.shell_bg)
                
                # Секция user@host
                prompt_parts.append(f"{t.prompt_user_bg}{t.prompt_user}{self.username}@{self.hostname}{t.prompt_reset}")
                
                # Разделитель и cwd
                prompt_parts.append(f":{t.prompt_cwd_bg}{t.prompt_cwd}{display_cwd}{t.prompt_reset}")
                
                # Время
                prompt_parts.append(f" {t.prompt_time_bg}{t.prompt_time}[{Tools.get_time()}]{t.prompt_reset}")
                
                # Символ и сброс
                prompt_parts.append(f" {stat} {t.prompt_reset}")

                prompt_text = ANSI("".join(prompt_parts))

                text = self.session.prompt(prompt_text).strip()
                if not text:
                    continue
                self.execute_line(text)

            except ExitShell:
                break
            except (KeyboardInterrupt, EOFError):
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

        if cmd in aliases:
            alias_value = aliases[cmd]
            try:
                alias_parts = shlex.split(alias_value)
            except ValueError:
                alias_parts = alias_value.split()
            if alias_parts:
                cmd = alias_parts[0].lower()
                args = alias_parts[1:] + args

        t = self.theme

        if cmd == "exit":
            raise ExitShell()

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
                    print(f"{t.error}cd: {e}{t.reset}")

        elif cmd == 'rm':
            args = self._fix_slashes(args)
            args = self._expand_glob(args)
            if not args:
                print("usage: rm <file> [file2 ...]")
            else:
                for target in args:
                    try:
                        if os.path.isdir(target):
                            print(f"{t.error}rm: cannot remove '{target}': Is a directory (use rmd){t.reset}")
                        elif not os.path.exists(target):
                            print(f"{t.error}rm: cannot remove '{target}': No such file{t.reset}")
                        else:
                            os.remove(target)
                    except PermissionError:
                        print(f"{t.error}rm: permission denied: '{target}'{t.reset}")
                    except Exception as e:
                        print(f"{t.error}rm: error removing '{target}': {e}{t.reset}")

        elif cmd == 'rmd':
            args = self._fix_slashes(args)
            args = self._expand_glob(args)
            if not args:
                print("usage: rmd <directory> [dir2 ...]")
            else:
                for target in args:
                    try:
                        if not os.path.exists(target):
                            print(f"{t.error}rmd: cannot remove '{target}': No such directory{t.reset}")
                        elif not os.path.isdir(target):
                            print(f"{t.error}rmd: cannot remove '{target}': Not a directory (use rm){t.reset}")
                        else:
                            shutil.rmtree(target)
                    except PermissionError:
                        print(f"{t.error}rmd: permission denied: '{target}'{t.reset}")
                    except OSError as e:
                        print(f"{t.error}rmd: error removing '{target}': {e}{t.reset}")

        elif cmd == "mkdir":
            args = self._fix_slashes(args)
            if args:
                try:
                    os.makedirs(args[0], exist_ok=True)
                except Exception as e:
                    print(f"{t.error}mkdir: {e}{t.reset}")

        elif cmd == "logs":
            args = self._fix_slashes(args)
            if len(args) > 0:
                if args[0] in ("clear", "clean"):
                    print("cleaning logs")

        elif cmd == 'sss':
            args = self._fix_slashes(args)
            target = args[0] if args else os.path.join(SyhConfig.homedir, SyhConfig.startup_script)
            self.run_sss(target)

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
                print(f"{t.error}ls: {e}{t.reset}")

        elif cmd == 'rd':
            args = self._fix_slashes(args)
            if args:
                try:
                    with open(args[0], 'r', encoding='utf-8') as f:
                        print(f.read())
                except Exception as e:
                    print(f"{t.error}rd: {e}{t.reset}")

        elif cmd == 'clock':
            try:
                while True:
                    print(Tools.get_time_and_date())
                    time.sleep(1)
            except (EOFError, KeyboardInterrupt):
                pass

        elif cmd == 'kaaedit':
            _kaa_run()

        elif cmd == 'pyvim':
            t_args = self._fix_slashes(args)
            if t_args:
                pyvim.open(t_args[0])
            else:
                print("usage: pyvim <file>")

        elif cmd == 'touch':
            args = self._fix_slashes(args)
            if args:
                try:
                    with open(args[0], 'x'):
                        pass
                except FileExistsError:
                    os.utime(args[0], None)
                except Exception as e:
                    print(f"{t.error}touch: {e}{t.reset}")

        elif cmd == 'py':
            args = self._fix_slashes(args)
            if args:
                if os.path.isfile(args[0]):
                    try:
                        with open(args[0], 'r', encoding='utf-8') as fl:
                            code = fl.read()
                        exec(code, {})
                    except Exception as e:
                        print(f"{t.error}py: {e}{t.reset}")
                else:
                    print(f"{t.error}File not found: {args[0]}{t.reset}")

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
                    print(f"{t.error}lua: file not found: {args[0]}{t.reset}")
            else:
                print("Usage: lua <filename.lua>")

        elif cmd == "syh":
            args = self._fix_slashes(args)
            if len(args) > 0:
                try:
                    sisyph.execute_file(args[0])
                except Exception as e:
                    traceback.print_exc()
            else:
                print("Usage: syh <filename.syh>")

        elif cmd == "execute":
            if not args or args[0] != "command":
                print("Usage: execute command \"<cmd>\"")
                return
            prefix = "execute command "
            idx = line.lower().find(prefix)
            if idx == -1:
                print("Usage: execute command \"<cmd>\"")
                return
            rest = line[idx + len(prefix):].strip()
            if rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
                com = rest[1:-1]
            elif rest.startswith("'") and rest.endswith("'") and len(rest) >= 2:
                com = rest[1:-1]
            else:
                com = rest
            if com:
                print(f"Executing: {com}")
            else:
                print("execute command: empty command string")

        elif cmd == 'reload-configs':
            self._reload_configs()

        elif cmd == 'theme':
            if not args:
                themes_dir = os.path.join(SyhConfig.ROOT_DATA, "themes")
                available = ["default"]
                if os.path.isdir(themes_dir):
                    available += [
                        os.path.splitext(f)[0]
                        for f in os.listdir(themes_dir)
                        if f.endswith(".json")
                    ]
                print(f"{t.info}Current theme: default{t.reset}")
                print(f"{t.info}Available: {', '.join(sorted(available))}{t.reset}")
                print(f"Usage: theme <name>")
            else:
                self.theme = load_theme(args[0])
                t = self.theme
                print(f"{t.success}Theme switched to '{args[0]}'{t.reset}")

        elif cmd in self._external_apps:
            app_meta = self._external_apps[cmd]
            command_str = app_meta.get("command", "")
            entry_point_name = app_meta.get("entry_point", "")

            log(f"Executing external app '{cmd}': command='{command_str}', entry_point='{entry_point_name}'")

            if command_str:
                try:
                    safe_args = ' '.join(shlex.quote(a) for a in args)
                    full_cmd = f"{command_str} {safe_args}".strip()
                    log(f"Running shell command: {full_cmd}")
                    rc = os.system(full_cmd)
                    if rc != 0:
                        print(f"{t.warning}{cmd}: shell command exited with code {rc}, skipping entry_point{t.reset}")
                        return
                except Exception as e:
                    print(f"{t.error}{cmd}: shell command failed: {e}{t.reset}")
                    return

            if entry_point_name:
                try:
                    if ":" in entry_point_name:
                        file_path, func_name = entry_point_name.rsplit(":", 1)
                    else:
                        file_path = entry_point_name
                        func_name = "main"

                    if not file_path.endswith(".py"):
                        file_path += ".py"

                    if not os.path.isabs(file_path):
                        candidate = os.path.join(SyhConfig.ROOT_BIN, os.path.basename(file_path))
                        if os.path.isfile(candidate):
                            file_path = candidate
                        else:
                            candidate2 = os.path.join(SyhConfig.homedir, file_path)
                            if os.path.isfile(candidate2):
                                file_path = candidate2

                    result = self._call_function_from_file(
                        file_path=file_path,
                        function_name=func_name,
                        args=args
                    )
                    if result is not None:
                        print(result)

                except (ImportError, AttributeError) as e:
                    print(f"{t.error}{cmd}: loading failed: {e}{t.reset}")
                except Exception as e:
                    print(f"{t.error}{cmd}: entry_point execution failed:{t.reset}")
                    print(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

        else:
            matches = difflib.get_close_matches(cmd, self.commands, n=3, cutoff=0.6)
            suggestion = '\n'.join(matches) if matches else 'No suggestions.'
            print(f'{t.error}Command not found: {t.reset}{cmd}\n{t.error}Did you mean:{t.reset}\n{suggestion}')


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