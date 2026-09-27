from lupa import LuaRuntime


class LuaInterpreter:
    """A simple wrapper around Lupa for executing Lua code from Python."""

    def __init__(self, unpack_returned_tuples=True):
        self.lua = LuaRuntime(unpack_returned_tuples=unpack_returned_tuples)

    def eval(self, code):
        """Evaluates a Lua expression string and returns the result."""
        return self.lua.eval(code)

    def execute(self, code):
        """Executes a Lua script (file or string). Returns what the script returns."""
        return self.lua.execute(code)

    def exec_lines(self, lines):
        """Takes a list of Lua code lines, joins them, and executes as a single script."""
        code = "\n".join(lines)
        return self.lua.execute(code)

    def set(self, name, value):
        """Passes a Python object into the Lua global namespace."""
        self.lua.globals()[name] = value
        return self

    def get(self, name):
        """Reads a global variable value from Lua."""
        return self.lua.globals()[name]

    def call(self, func_name, *args):
        """Calls a Lua function by name with arbitrary arguments."""
        func = self.lua.globals()[func_name]
        if func is None:
            raise NameError(f"Lua function '{func_name}' not found")
        return func(*args)

