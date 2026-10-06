import quickjs

# quickjs has no host-side console, so we install one from JS itself.
# Values are formatted with JavaScript semantics (undefined/null/String/JSON).
_PRELUDE = """
(function (write) {
    function fmt(v) {
        var t = typeof v;
        if (t === "undefined") return "undefined";
        if (v === null) return "null";
        if (t === "string") return v;
        if (t === "object") {
            try { return JSON.stringify(v); } catch (e) { return String(v); }
        }
        return String(v);
    }
    function sink() {
        var parts = [];
        for (var i = 0; i < arguments.length; i++) {
            parts.push(fmt(arguments[i]));
        }
        write(parts.join(" "));
    }
    globalThis.console = {
        log: sink, info: sink, debug: sink, warn: sink, error: sink
    };
})(function (text) { __syh_write(text); });
"""


class JSRuntime():
    def __init__(self):
        self.ctx = quickjs.Context()
        self.ctx.add_callable("__syh_write", self._write)
        self.ctx.eval(_PRELUDE)

    @staticmethod
    def _write(text):
        print(text, flush=True)

    def js_eval(self, code: str):
        try:
            return self.ctx.eval(code)
        except quickjs.JSException as e:
            print(f"Java Script runtime error: {e}")
        except Exception as e:
            print(f"Java Script runtime error: {type(e).__name__}: {e}")

    def js_exec_lines(self, lines: list[str]):
        return self.js_eval("\n".join(lines))
