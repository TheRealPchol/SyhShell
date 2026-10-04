import quickjs
from ..syhshell import Theme

class JSRuntime():
    def __init__(self):
        self.ctx = quickjs.Context
    def js_eval(self, code: str):
        theme = Theme()
        try:
            self.ctx.eval(code)
        except quickjs.JSException as e:
            print(f"{theme.error}Java Script runtime error: {e}{theme.reset}")
    def js_exec_lines(self, lines: list[str]):
        self.js_eval("\n".join(lines))