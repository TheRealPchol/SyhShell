from datetime import datetime
import os
import difflib
import json
import shlex
import sys
import time
import traceback
import inspect
import gzip
import shutil
import glob
import functools
import importlib.util
from dataclasses import dataclass, fields
import sqlite3
import hashlib
import hmac
import getpass

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import InMemoryHistory

from utils import pyvim
from utils import lua
from compilers import sisyph
from compilers.js import JSRuntime

# ─── Config ───────────────────────────────────────────────

@dataclass
class SyhConfig:
    homedir: str = os.path.dirname(os.path.abspath(__file__))
    aliases: dict[str, str] | None = None
    homedir_replace_char: str = "~"
    startup_script: str = f"{homedir}.syhrc"
    ROOT: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "root")
    ROOT_BIN: str = os.path.join(ROOT, "bin")
    ROOT_DATA: str = os.path.join(ROOT, "data")
    ROOT_HOME: str = os.path.join(ROOT, "home")
    CONFIG_FILE = os.path.join(ROOT_DATA, "config.json")
    SYHSHELL_DB = os.path.join(ROOT_DATA, "syhshell.db")
    

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
    chtoto: str = "\033[36m"

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
    VERSION = "ss26.10.1"
    BUILD = 3

# ─── Logging ─────────────────────────────────────────────

def log(log_text, config_filename: str = 'config.json'):
    config_path = os.path.join(SyhConfig.ROOT_DATA, config_filename)
    if os.path.isfile(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as fl:
                config = json.load(fl)
        except Exception:
            config = {}
        if config.get("logging", {}).get("enable"):
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

# ─── Context ─────────────────────────────────────────────

class Context:
    ROOT_PERM_LEVEL = 0
    DEFAULT_PERM_LEVEL = 1
    DEFAULT_GROUP = "users"
    ADMIN_GROUP = "root"
    MAX_AUTH_ATTEMPTS = 3

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        db_path = SyhConfig.SYHSHELL_DB
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.conn = conn if conn is not None else sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()

        self.user_id: int | None = None
        self.username: str | None = None
        self.user: str | None = None
        self.home: str | None = None
        self.perm_level: int | None = None
        self.groups: list[str] = []

        self._ensure_schema()

    def _ensure_schema(self):
        self.conn.executescript('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PK,
    username TEXT UNIQUE,
    passwd TEXT,
    salt TEXT,
    home TEXT,
    perm_level INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS users_id_unique ON users(id);
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS user_groups (
    user_id INTEGER,
    group_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (group_id) REFERENCES groups(id)
);
CREATE TABLE IF NOT EXISTS commands (
    command TEXT PRIMARY KEY,
    perm_type INTEGER,
    target TEXT
);
CREATE TABLE IF NOT EXISTS file_perms (
    filepath TEXT PRIMARY KEY,
    owner_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    group_id INTEGER REFERENCES groups(id) ON DELETE RESTRICT,
    mode INTEGER NOT NULL DEFAULT 644
) WITHOUT ROWID;
''')
        self.conn.commit()

    @staticmethod
    def _validate_name(value: str, kind: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{kind} must be a string")
        value = value.strip()
        if not value:
            raise ValueError(f"{kind} cannot be empty")
        if value in (".", "..") or "/" in value or "\\" in value or "\x00" in value:
            raise ValueError(f"Invalid {kind}: {value!r}")
        return value

    def _next_user_id(self) -> int:
        row = self.cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM users").fetchone()
        return int(row[0])

    def _get_user_row(self, username: str) -> sqlite3.Row | None:
        self.cursor.execute(
            "SELECT id, username, passwd, salt, home, perm_level FROM users WHERE username = ?",
            (username,),
        )
        return self.cursor.fetchone()

    def _group_id(self, name: str, create: bool = True) -> int | None:
        self.cursor.execute("SELECT id FROM groups WHERE name = ?", (name,))
        row = self.cursor.fetchone()
        if row is not None:
            return int(row["id"])
        if not create:
            return None
        self.cursor.execute("INSERT INTO groups (name) VALUES (?)", (name,))
        return int(self.cursor.lastrowid)

    def _bind_user(self, row: sqlite3.Row) -> "Context":
        self.user_id = int(row["id"]) if row["id"] is not None else None
        self.username = row["username"]
        self.user = self.username
        self.home = row["home"] or os.path.join(SyhConfig.ROOT_HOME, self.username)
        self.perm_level = (
            int(row["perm_level"])
            if row["perm_level"] is not None
            else self.DEFAULT_PERM_LEVEL
        )
        self.groups = self.get_user_groups(self.username)
        return self

    def count_users(self) -> int:
        return int(self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def get_usr(self, username: str) -> dict | None:
        row = self._get_user_row(username)
        if row is None:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "home": row["home"],
            "perm_level": row["perm_level"],
            "groups": self.get_user_groups(username),
        }

    def list_users(self) -> list[dict]:
        rows = self.cursor.execute("SELECT id, username, home, perm_level FROM users ORDER BY id").fetchall()
        return [
            {
                "id": row["id"],
                "username": row["username"],
                "home": row["home"],
                "perm_level": row["perm_level"],
                "groups": self.get_user_groups(row["username"]),
            }
            for row in rows
        ]

    def add_usr(
        self,
        username: str,
        group: str = DEFAULT_GROUP,
        password: str | None = None,
        *,
        perm_level: int = DEFAULT_PERM_LEVEL,
        home: str | None = None,
    ) -> int:
        username = self._validate_name(username, "username")
        group = self._validate_name(group, "group")
        if not password:
            raise ValueError("Password cannot be empty")
        if self._get_user_row(username) is not None:
            raise ValueError(f"User already exists: {username}")

        hashed_pwd, salt = Tools.hash_string(password)
        home = home or os.path.join(SyhConfig.ROOT_HOME, username)
        user_id = self._next_user_id()

        try:
            self.cursor.execute(
                "INSERT INTO users (id, username, passwd, salt, home, perm_level) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, hashed_pwd, salt, home, perm_level),
            )
            group_id = self._group_id(group)
            self.cursor.execute(
                "INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)",
                (user_id, group_id),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        try:
            os.makedirs(home, exist_ok=True)
        except OSError as e:
            log(f"Failed to create home directory for '{username}': {e}")
        return user_id

    def del_usr(self, username: str) -> None:
        row = self._get_user_row(username)
        if row is None:
            raise ValueError(f"User not found: {username}")
        try:
            self.cursor.execute("DELETE FROM user_groups WHERE user_id = ?", (row["id"],))
            self.cursor.execute("DELETE FROM users WHERE id = ?", (row["id"],))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        if self.username == username:
            self._clear_identity()

    def add_group(self, name: str) -> int:
        name = self._validate_name(name, "group")
        group_id = self._group_id(name)
        self.conn.commit()
        return int(group_id)

    def get_group(self, name: str) -> dict | None:
        self.cursor.execute("SELECT id, name FROM groups WHERE name = ?", (name,))
        row = self.cursor.fetchone()
        return dict(row) if row is not None else None

    def list_groups(self) -> list[dict]:
        rows = self.cursor.execute("SELECT id, name FROM groups ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def del_group(self, name: str) -> None:
        self.cursor.execute("SELECT id FROM groups WHERE name = ?", (name,))
        row = self.cursor.fetchone()
        if row is None:
            raise ValueError(f"Group not found: {name}")
        try:
            self.cursor.execute("DELETE FROM user_groups WHERE group_id = ?", (row["id"],))
            self.cursor.execute("DELETE FROM groups WHERE id = ?", (row["id"],))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def add_user_to_group(self, username: str, group: str) -> None:
        row = self._get_user_row(username)
        if row is None:
            raise ValueError(f"User not found: {username}")
        group_id = self._group_id(self._validate_name(group, "group"))
        self.cursor.execute(
            "SELECT 1 FROM user_groups WHERE user_id = ? AND group_id = ?",
            (row["id"], group_id),
        )
        if self.cursor.fetchone() is None:
            self.cursor.execute(
                "INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)",
                (row["id"], group_id),
            )
            self.conn.commit()
        if self.username == username:
            self.groups = self.get_user_groups(username)

    def remove_user_from_group(self, username: str, group: str) -> None:
        row = self._get_user_row(username)
        if row is None:
            raise ValueError(f"User not found: {username}")
        group_id = self._group_id(group, create=False)
        if group_id is not None:
            self.cursor.execute(
                "DELETE FROM user_groups WHERE user_id = ? AND group_id = ?",
                (row["id"], group_id),
            )
            self.conn.commit()
        if self.username == username:
            self.groups = self.get_user_groups(username)

    def get_user_groups(self, username: str | None = None) -> list[str]:
        target = username or self.username
        if not target:
            return []
        rows = self.cursor.execute(
            """
            SELECT g.name
            FROM groups AS g
            JOIN user_groups AS ug ON ug.group_id = g.id
            JOIN users AS u ON u.id = ug.user_id
            WHERE u.username = ?
            ORDER BY g.name
            """,
            (target,),
        ).fetchall()
        return [row["name"] for row in rows]

    def set_password(self, username: str, password: str) -> None:
        row = self._get_user_row(username)
        if row is None:
            raise ValueError(f"User not found: {username}")
        if not password:
            raise ValueError("Password cannot be empty")
        hashed_pwd, salt = Tools.hash_string(password)
        self.cursor.execute(
            "UPDATE users SET passwd = ?, salt = ? WHERE id = ?",
            (hashed_pwd, salt, row["id"]),
        )
        self.conn.commit()

    def verify_password(self, username: str, password: str) -> bool:
        row = self._get_user_row(username)
        if row is None or not row["passwd"] or not row["salt"]:
            return False
        return Tools.verify_hash(password, row["passwd"], row["salt"])

    @property
    def is_admin(self) -> bool:
        return self.perm_level == self.ROOT_PERM_LEVEL or self.ADMIN_GROUP in self.groups

    def _clear_identity(self):
        self.user_id = None
        self.username = None
        self.user = None
        self.home = None
        self.perm_level = None
        self.groups = []

    def logout(self) -> None:
        self._clear_identity()
        self.close()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def __enter__(self) -> "Context":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _create_first_user(self, username: str | None, password: str | None) -> "Context":
        print("\033[1;33mNo users found. Creating the first administrator.\033[0m")
        if username is None:
            username = Tools._input("\033[1;36mAdministrator login [root]: \033[0m").strip() or "root"
        username = self._validate_name(username, "username")

        if password is None:
            while True:
                password = getpass.getpass("New password: ")
                if not password:
                    print("\033[1;31mPassword cannot be empty.\033[0m")
                    continue
                confirmation = getpass.getpass("Repeat password: ")
                if password != confirmation:
                    print("\033[1;31mPasswords do not match.\033[0m")
                    continue
                break
        if not password:
            raise ValueError("Password cannot be empty")

        self.add_usr(
            username,
            self.ADMIN_GROUP,
            password,
            perm_level=self.ROOT_PERM_LEVEL,
        )
        print(f"\033[1;32mAdministrator '{username}' created.\033[0m")
        return self._bind_user(self._get_user_row(username))

    @staticmethod
    def auth(
        username: str | None = None,
        password: str | None = None,
        max_attempts: int = MAX_AUTH_ATTEMPTS,
    ) -> "Context | None":
        """Авторизует пользователя и возвращает Context.

        Если пользователей в базе нет, создаёт первого администратора через
        add_usr(). Недостающие логин/пароль запрашиваются интерактивно.
        """
        ctx = Context()
        try:
            if ctx.count_users() == 0:
                return ctx._create_first_user(username, password)

            interactive = username is None or password is None
            attempts = max(1, int(max_attempts)) if interactive else 1
            for attempt in range(1, attempts + 1):
                current_username = username
                if current_username is None:
                    current_username = Tools._input("\033[1;36mLogin: \033[0m").strip()
                current_password = password
                if current_password is None:
                    current_password = getpass.getpass("Password: ")

                if ctx.verify_password(current_username, current_password):
                    return ctx._bind_user(ctx._get_user_row(current_username))

                if not interactive:
                    break
                print(f"\033[1;31mInvalid username or password ({attempt}/{attempts}).\033[0m")
                password = None

            ctx.close()
            return None
        except (KeyboardInterrupt, EOFError):
            print()
            ctx.close()
            return None
        except Exception:
            ctx.close()
            raise

# ─── Tools ───────────────────────────────────────────────

class Tools:
    PBKDF2_ITERATIONS = 100000

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
    def theme_print(text: str, theme: Theme | None = None, style: str = ""):
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
    
    @staticmethod
    @log_
    def hash_string(text: str) -> tuple[str, str]:
        salt_bytes = os.urandom(16)

        hash_bytes = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=text.encode("utf-8"),
            salt=salt_bytes,
            iterations=Tools.PBKDF2_ITERATIONS,
        )

        hash_str = hash_bytes.hex()
        salt_str = salt_bytes.hex()

        return (hash_str, salt_str)

    @staticmethod
    @log_
    def verify_hash(text: str, hash_str: str, salt_str: str) -> bool:
        try:
            salt_bytes = bytes.fromhex(salt_str)
        except (TypeError, ValueError):
            return False

        hash_bytes = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=text.encode("utf-8"),
            salt=salt_bytes,
            iterations=Tools.PBKDF2_ITERATIONS,
        )
        return hmac.compare_digest(hash_bytes.hex(), hash_str)


# ─── Shell ────────────────────────────────────────────────

class Shell:
    _self = None
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
            "py", "tcc", "cpp", "lua", "syh", "qjs",
            "sss", "reload-configs", "logs", "execute",
            "theme", "fetch",
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
        Shell._self = self
    def get_self(self):
        return self
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
            print("  No changes detected.")
        log(f"Configs reloaded: {len(added)} added, {len(removed)} removed")

    @log_
    def fetch(self):
        t = self.theme
        output = [
            "",
            f"{t.chtoto}                                  {t.reset}SisyphShell fetch",
            "",
            f"{t.chtoto}▄▀▀▀ ▄  ▄ █▄▄  ▄▀▀▀ █▄▄   ▄▄  █ █ {t.reset} Sisyph shell version: {info.VERSION}",
            f"{t.chtoto} ▀▀▄ █  █ █  █  ▀▀▄ █  █ █▀▀▀ █ █ {t.reset} Sisyph shell build: {info.BUILD}",
            f"{t.chtoto}▀▀▀   ▀▀█ ▀  ▀ ▀▀▀  ▀  ▀  ▀▀▀ ▀ ▀ {t.reset} Commands count: {len(self.commands)}",
            f"{t.chtoto}      ▀▀                          {t.reset} {self.username}@{self.hostname}",
            f"{t.chtoto}                                  {t.reset} Current dir: {os.getcwd()}",
        ]
        print("\n".join(output))

    def shell_env(self):
        t = self.theme
        
        # Применяем глобальный бэкграунд если установлен
        if t.shell_bg:
            print(f"{t.shell_bg}{t.reset}", end="")
        
        print(f'{t.info}Welcome to the SisyphShell{t.reset}')
        print(f'{t.info}Version: {info.VERSION}{t.reset}')
        print(f"{t.info}Build: {info.BUILD}{t.reset}")

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
        elif cmd == 'fetch':
            self.fetch()
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
                except Exception:
                    traceback.print_exc()
            else:
                print("Usage: syh <filename.syh>")
        elif cmd == "qjs":
            args = self._fix_slashes(args)
            if args:
                jsruntime = JSRuntime()
                if os.path.isfile(args[0]):
                    with open(args[0], "r", encoding="utf-8") as f:
                        code = f.read()
                    jsruntime.js_eval(code)
                else:
                    print(f"File '{args[0]}' is not found")
            if not args:
                print("Usage: qjs <filename.js>")
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
                print("Usage: theme <name>")
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
        try:
            from root.bin import syhapi
            syhapi.Shell = Shell
            syhapi.Tools = Tolls
            syhapi.info = info
            syhapi.SyhConfig = SyhConfig
        except:
            pass
        shel = Shell()
        shel.shell_env()
    finally:
        Tools.compress_to_gz("latest.log", f"{str(datetime.now()).split('.')[0]}.gz")
