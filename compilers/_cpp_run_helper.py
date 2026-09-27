import re
import sys

_MAIN_VOID = re.compile(r'\bmain\s*\(\s*(?:void\s*)?\)')


def main():
    filepath = sys.argv[1]
    argv = sys.argv[2:]
    try:
        with open(filepath, 'r', encoding='utf-8') as fl:
            c_code = fl.read()
        import cppyy
        cppyy.cppdef(c_code)
        if not hasattr(cppyy.gbl, 'main'):
            print("cpp: compiled code has no 'main' entry point",
                  file=sys.stderr)
            return 1
        if _MAIN_VOID.search(c_code):
            return int(cppyy.gbl.main())
        return int(cppyy.gbl.main(len(argv), argv))
    except SyntaxError as e:
        print(f"cpp: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"cpp: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())