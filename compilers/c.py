import ctypes
from ctypes import POINTER, c_char_p, c_int
import os
import re

from pytcc import TCC, CCode

_compiler = TCC()

_MAIN_VOID = re.compile(r'\bmain\s*\(\s*(?:void\s*)?\)')


def _main_has_args(c_code: str) -> bool:
    return _MAIN_VOID.search(c_code) is None


def _main_func(binary, has_args):
    if 'main' not in binary:
        raise RuntimeError("compiled C code has no 'main' entry point")
    if has_args:
        main_type = ctypes.CFUNCTYPE(c_int, c_int, POINTER(c_char_p))
    else:
        main_type = ctypes.CFUNCTYPE(c_int)
    return main_type(binary['main'])


class Compiler():
    def __init__(self, compiler_: TCC = None):
        self.comp = compiler_ if compiler_ is not None else _compiler

    def _invoke_main(self, binary, argv=None, has_args=True):
        main_func = _main_func(binary, has_args)
        try:
            if not has_args:
                return main_func()
            argv = list(argv or [])
            cargs = (c_char_p * (len(argv) + 1))()
            for i, arg in enumerate(argv):
                cargs[i] = arg.encode('utf-8')
            cargs[len(argv)] = None
            return main_func(len(argv), cargs)
        finally:
            binary.close()

    def run(self, c_code: str, argv=None) -> int:
        has_args = _main_has_args(c_code)
        binary = self.comp.build_to_mem(CCode(c_code))
        return self._invoke_main(binary, argv, has_args)

    def run_file(self, filepath: str, argv=None) -> int:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"file not found: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as fl:
            return self.run(fl.read(), argv)

    def build(self, outfile: str, infiles, auto_add_suffix: bool = False) -> str:
        if isinstance(infiles, str):
            infiles = [infiles]
        for f in infiles:
            if not os.path.isfile(f):
                raise FileNotFoundError(f"file not found: {f}")
        binary = self.comp.build_to_exe(
            outfile, *infiles, auto_add_suffix=auto_add_suffix)
        return str(binary.path)