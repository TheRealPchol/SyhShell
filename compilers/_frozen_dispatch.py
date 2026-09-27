import os
import re
import sys


def _find_zig() -> str:
    base = getattr(sys, '_MEIPASS', None)
    if base:
        candidate = os.path.join(base, 'ziglang', 'zig')
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    try:
        import ziglang
    except Exception:
        return ''
    candidate = os.path.join(os.path.dirname(ziglang.__file__), 'zig')
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return ''


def _cpp_run(argv):
    if not argv:
        return 1
    filepath, rest = argv[0], list(argv[1:])
    try:
        with open(filepath, 'r', encoding='utf-8') as fl:
            c_code = fl.read()
        import cppyy
        cppyy.cppdef(c_code)
        if not hasattr(cppyy.gbl, 'main'):
            print("cpp: compiled code has no 'main' entry point",
                  file=sys.stderr)
            return 1
        if re.search(r'\bmain\s*\(\s*(?:void\s*)?\)', c_code):
            return int(cppyy.gbl.main())
        return int(cppyy.gbl.main(len(rest), rest))
    except SyntaxError as e:
        print(f"cpp: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"cpp: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


def _zig_cxx(argv):
    zig = _find_zig()
    if not zig:
        print("cpp build: bundled zig interpreter not found",
              file=sys.stderr)
        return 1
    try:
        os.execv(zig, [zig] + list(argv))
    except OSError as e:
        print(f"cpp build: cannot execute zig: {e}", file=sys.stderr)
        return 1
    return 1


def dispatch(argv):
    if len(argv) < 2:
        return None
    if argv[1] == '--cpp-run':
        return _cpp_run(argv[2:])
    if argv[1] == '--zig-c++':
        return _zig_cxx(argv[2:])
    return None