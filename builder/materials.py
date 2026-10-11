"""The case materials as text, whatever their format, and the tool API among them.

Input forms: files, a folder (read recursively), or a .zip (extracted to a temporary folder; the source is never
changed). A command-line argument starting with http(s):// is the bank mock's base URL.

Markdown, text, CSV, JSON and YAML are read as they are. Word (.docx), PDF, Excel (.xlsx/.xlsm/.xls) and PowerPoint
(.pptx) are converted to text that keeps where each part came from ("[file X, page 3]", "[file X, sheet Rates]").
A file that cannot be read is never skipped silently: it is returned in `unread` with the reason, the trace lists it
and the run cannot end COMPLETE.
"""
import json
import pathlib
import shutil
import subprocess
import tempfile
import zipfile

TEXT = {".md", ".markdown", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml", ".html", ".htm", ".xml"}
SKIP = {".ds_store", "thumbs.db"}


def expand(args):
    """(files, mock_url, temp_dirs). Folders are walked in sorted order; zips are extracted."""
    files, mock, temps = [], None, []
    for a in args:
        if str(a).lower().startswith(("http://", "https://")):
            mock = str(a).rstrip("/")
            continue
        p = pathlib.Path(a)
        if p.is_dir():
            files += [str(x) for x in sorted(p.rglob("*")) if x.is_file() and x.name.lower() not in SKIP
                      and not any(part.startswith("__MACOSX") for part in x.parts)]
        elif p.suffix.lower() == ".zip" and p.is_file():
            d = tempfile.mkdtemp(prefix="case_")
            temps.append(d)
            with zipfile.ZipFile(p) as z:
                z.extractall(d)
            sub, m2, t2 = expand([d])
            files += sub
        else:
            files.append(str(p))
    return files, mock, temps


def load_api(path):
    """The OpenAPI document in a JSON or YAML file (it has 'paths'), or None."""
    try:
        raw = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        if path.lower().endswith((".yaml", ".yml")):
            import yaml
            d = yaml.safe_load(raw)
        elif path.lower().endswith(".json"):
            d = json.loads(raw)
        else:
            return None
    except Exception:
        return None
    return d if isinstance(d, dict) and isinstance(d.get("paths"), dict) else None


def _pdf(path):
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            parts = [f"[page {i}]", text]
            for t in tables:
                parts.append("\n".join(" | ".join("" if c is None else str(c) for c in row) for row in t))
            out.append("\n".join(parts))
    text = "\n\n".join(out)
    if len(text.replace("[page", "").strip()) < 20:            # a scanned PDF has no text layer
        try:
            text = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=60).stdout
        except Exception:
            pass
    return text


def _xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            if row is None or all(v is None for v in row):
                continue
            rows.append(" | ".join("" if v is None else str(v) for v in row))
        out.append(f"[sheet {ws.title}]\n" + "\n".join(rows))
    return "\n\n".join(out)


def _xls(path):
    import pandas as pd
    sheets = pd.read_excel(path, sheet_name=None, header=None)
    return "\n\n".join(f"[sheet {name}]\n" + df.fillna("").astype(str).to_csv(sep="|", index=False, header=False)
                       for name, df in sheets.items())


def _docx(path):
    try:
        from markitdown import MarkItDown
        return MarkItDown().convert(path).text_content
    except Exception:
        import docx
        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            parts.append("\n".join(" | ".join(c.text for c in r.cells) for r in t.rows))
        return "\n".join(parts)


def _other(path):
    from markitdown import MarkItDown
    return MarkItDown().convert(path).text_content


def read(path):
    """(text, problem). problem is None when the file was read."""
    ext = pathlib.Path(path).suffix.lower()
    try:
        if ext in TEXT:
            raw = pathlib.Path(path).read_bytes()
            text = raw.decode("utf-8", errors="replace")
            bad = text.count("�")
            return text, (f"{bad} byte(s) not UTF-8 (shown as �)" if bad else None)
        if ext == ".pdf":
            text = _pdf(path)
        elif ext in (".xlsx", ".xlsm"):
            text = _xlsx(path)
        elif ext == ".xls":
            text = _xls(path)
        elif ext == ".docx":
            text = _docx(path)
        elif ext in (".pptx", ".doc", ".rtf", ".odt"):
            text = _other(path)
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"):
            return "", "image: no text reader (its content is not in the reading)"
        else:
            raw = pathlib.Path(path).read_bytes()
            if b"\x00" in raw[:4096]:
                return "", f"binary file of unknown type ({ext or 'no extension'})"
            return raw.decode("utf-8", errors="replace"), None
    except Exception as e:
        return "", f"could not be read ({type(e).__name__}: {str(e)[:120]})"
    if not str(text or "").strip():
        return "", "no text could be extracted"
    return text, None


def gather(args):
    """Everything the builder needs from the command line: (openapi, api_path, docs, mock_url, unread, notes).
    docs: [(name, text)] with a header naming the source file; unread: ["name: reason"]."""
    files, mock, temps = expand(args)
    apis = [(f, load_api(f)) for f in files]
    apis = [(f, d) for f, d in apis if d is not None]
    api_path, openapi = (apis[0] if len(apis) == 1 else (None, None))
    notes, docs, unread = [], [], []
    if len(apis) > 1:
        notes.append("more than one OpenAPI document: " + ", ".join(f for f, _ in apis))
    roots = [pathlib.Path(a) for a in args if not str(a).lower().startswith("http") and pathlib.Path(a).is_dir()] + \
        [pathlib.Path(t) for t in temps]
    for f in files:
        if api_path and f == api_path:
            continue
        name = f
        for r in roots:
            try:
                name = str(pathlib.Path(f).relative_to(r))
                break
            except ValueError:
                pass
        text, problem = read(f)
        if problem and not text:
            unread.append(f"{name}: {problem}")
            continue
        if problem:
            notes.append(f"{name}: {problem}")
        docs.append((name, f"[file {name}]\n{text}"))
    for t in temps:
        shutil.rmtree(t, ignore_errors=True)
    return openapi, api_path, docs, mock, unread, notes
