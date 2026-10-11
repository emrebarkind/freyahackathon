"""Export the full model session log of one builder run as its trace (the organisers ask for the Claude Code session
log of the run when the builder runs Claude Code; the builder's model calls go through the Claude Agent SDK, which runs
Claude Code and records each session as JSONL under ~/.claude/projects/<cwd>/).

Every session of the run is included: the JSONL files whose entries fall between the run's START and END in
traces/<slot>.trace.log. Entries are kept in order and unchanged except for the redactions listed in the note
(personal e-mail address and organisation id of the account; secrets are checked and must be absent).
    python3 scripts/export_session_log.py <slot> [--redact TEXT=LABEL ...]"""
import datetime, glob, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
slot = sys.argv[1]
redact = [a.split("=", 1) for a in sys.argv[2:] if "=" in a]
trace = (ROOT / "traces" / f"{slot}.trace.log").read_text()
start = re.search(r"START (\S+)", trace).group(1)
end = re.search(r"END (\S+)", trace).group(1)
t0 = datetime.datetime.fromisoformat(start.replace("+0000", "+00:00"))
t1 = datetime.datetime.fromisoformat(end.replace("+0000", "+00:00"))
calls = int(re.search(r"model_calls=(\d+)", trace).group(1))

entries, files = [], []
for f in glob.glob(os.path.expanduser("~/.claude/projects/-tmp-builder-claude-*/*.jsonl")):
    rows = []
    for line in open(f, encoding="utf-8"):
        d = json.loads(line)
        ts = d.get("timestamp")
        if ts:
            t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if not (t0 - datetime.timedelta(seconds=5) <= t <= t1 + datetime.timedelta(seconds=5)):
                continue
        rows.append((ts or "", line))
    if any(ts for ts, _ in rows):
        files.append((min(ts for ts, _ in rows if ts), f, rows))
files.sort()                                  # sessions in the order they started; lines keep their original order
entries = [r for _, _, rows in files for r in rows]
files = [f for _, f, _ in files]
text = "".join(line for _, line in entries)
counts = {}
for label_src, label in redact:
    counts[label] = text.count(label_src)
    text = text.replace(label_src, label)
for pat in (r"fak_[A-Za-z0-9]{8}", r"sk-ant-[A-Za-z0-9]"):
    if re.search(pat, text):
        sys.exit(f"secret pattern {pat} found: not exported")
for v in (os.environ.get("FREYA_API_KEY"), os.environ.get("FREYA_BANK_TEAM_KEY")):
    if v and v in text:
        sys.exit("a configured secret value is in the session log: not exported")
out = ROOT / "traces" / f"{slot}.session.jsonl"
out.write_text(text, encoding="utf-8")
results = sum(1 for l in text.splitlines() if '"structured_output"' in l)
note = ROOT / "traces" / f"{slot}.session.NOTE.md"
note.write_text(
    f"# Session log of builder run `{slot}`\n\n"
    f"* Run window (from traces/{slot}.trace.log): {start} to {end}; the trace counts {calls} model call(s).\n"
    f"* Session files merged ({len(files)}): " + ", ".join(pathlib.Path(f).parent.name + "/" + pathlib.Path(f).name for f in files) + "\n"
    f"* Entries: {len(entries)}; entries carrying a structured model answer: {results}.\n"
    "* Changes to the original lines: only these redactions (label: occurrences): "
    + (", ".join(f"{k}: {v}" for k, v in counts.items()) or "none") + ". Prompts, errors and model answers are unchanged.\n"
    "* Secret scan: no Freya key, team key or API-key pattern in the file.\n", encoding="utf-8")
print(f"{out.relative_to(ROOT)}: {len(entries)} entries from {len(files)} session file(s); model calls in trace {calls}; "
      f"structured answers {results}; redactions {counts}")
