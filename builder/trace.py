"""Plain-text trace of one builder run (required for submission). Never writes secrets."""
import os
import re
import sys
import time

SECRET = re.compile(r"(fak_[A-Za-z0-9]+|sk-ant-[A-Za-z0-9_\-]+)")


class Trace:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.f = open(path, "w")
        self.t0 = time.time()
        self.cost = 0.0
        self.calls = 0
        self.line(f"START {time.strftime('%Y-%m-%dT%H:%M:%S%z')}")

    def line(self, text):
        text = SECRET.sub("[redacted]", str(text))
        stamp = f"[{time.time() - self.t0:7.1f}s] "
        out = "\n".join(stamp + l for l in text.splitlines() or [""])
        self.f.write(out + "\n")
        self.f.flush()
        print(out, file=sys.stderr, flush=True)

    def model_call(self, model, purpose, seconds, cost):
        self.calls += 1
        self.cost += cost or 0.0
        self.line(f"MODEL CALL #{self.calls} model={model} seconds={seconds:.1f} cost_usd={cost or 0:.3f} purpose: {purpose}")

    def note(self, text):
        self.line("NOTE " + text)

    def step(self, text):
        self.line("STEP " + text)

    def test(self, name, ok, detail=""):
        self.line(f"TEST {'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail else ""))

    def end(self):
        self.line(f"END {time.strftime('%Y-%m-%dT%H:%M:%S%z')} total_seconds={time.time() - self.t0:.1f} "
                  f"model_calls={self.calls} model_cost_usd={self.cost:.2f}")
        self.f.close()
