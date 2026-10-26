"""Escritura y comprobación del repo OKF (v0.2): frontmatter, índices, log, lint y commit."""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import stat
import subprocess
import unicodedata
from pathlib import Path

import yaml

from .sources import scan


def now_iso() -> str:
    """ISO 8601 con desfase UTC explícito, como pide OKF."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


RESERVED = {"index.md", "log.md"}


def slug(s: str, n: int = 60) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n] or "doc"


def write(path: Path, fields: dict, body: str) -> None:
    """Un concepto OKF: frontmatter (type obligatorio) + cuerpo Markdown."""
    assert "type" in fields, "OKF exige type"
    if path.name.lower() in RESERVED:   # index.md y log.md están reservados en OKF: un concepto no puede llamarse así
        path = path.with_name(f"{path.stem}-doc.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump({k: v for k, v in fields.items() if v not in (None, "", [])}, allow_unicode=True, sort_keys=False, width=1000)
    path.write_text(f"---\n{fm}---\n\n{body.strip()}\n", encoding="utf-8")


def split(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    return ((yaml.safe_load(m.group(1)) or {}), m.group(2)) if m else ({}, text)


def rmtree(path: Path) -> None:
    """Borra una salida anterior; en Windows los objetos de .git son de solo lectura."""
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if path.exists():
        shutil.rmtree(path, onerror=onerror)


def build_indexes(out: Path, sistema: str, modo: str) -> None:
    """index.md en cada carpeta (reservado en OKF) y el raíz con okf_version."""
    folders = {p.parent for p in out.rglob("*.md") if ".git" not in p.parts}
    folders |= {a for f in folders for a in f.parents if out in a.parents}
    for folder in sorted(folders):
        if folder == out:
            continue
        items = [f"- [{d.name}/]({d.name}/index.md)" for d in sorted(folder.iterdir()) if d.is_dir() and not d.name.startswith(".")]
        for p in sorted(folder.glob("*.md")):
            if p.name in {"index.md", "log.md"}:
                continue
            fm, _ = split(p.read_text(encoding="utf-8"))
            items.append(f"- [{fm.get('title', p.stem)}]({p.name})" + (f": {fm['description']}" if fm.get("description") else ""))
        (folder / "index.md").write_text(f"# Índice · {folder.relative_to(out).as_posix()}\n\n" + "\n".join(items) + "\n", encoding="utf-8")
    top = [f"- [{d.name}/]({d.name}/index.md)" for d in sorted(out.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    (out / "index.md").write_text(f'---\nokf_version: "0.2"\n---\n\n# Conocimiento · {sistema}\n\nModo de entrega: `{modo}`. '
                                  "Empieza por la guía de cada repo (`repos/<repo>/guia.md`) y, si hay contradicciones entre fuentes, "
                                  "por `vigencia/`.\n\n" + "\n".join(top) + "\n", encoding="utf-8")


def append_log(out: Path, entry: str) -> None:
    """log.md según OKF: entradas agrupadas bajo encabezados `## YYYY-MM-DD`, lo más reciente primero."""
    log, today = out / "log.md", now_iso()[:10]
    lines = (log.read_text(encoding="utf-8") if log.exists() else "# Log\n").splitlines()
    if f"## {today}" in lines:   # mismo día: la entrada nueva va la primera bajo su fecha
        i = lines.index(f"## {today}")
        lines[i + 1:i + 1] = [f"- {entry}"]
    else:                        # día nuevo: su bloque va encima de los anteriores
        i = next((k for k, l in enumerate(lines) if l.startswith("## ")), None)
        if i is None:
            lines += [""] if lines[-1] else []
            i = len(lines)
        lines[i:i] = [f"## {today}", f"- {entry}", ""]
    log.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def lint(out: Path) -> list[str]:
    """Frontmatter con type, H1, enlaces relativos que resuelven y posibles secretos o datos personales."""
    problems = []
    for f in sorted(out.rglob("*.md")):
        if ".git" in f.parts:
            continue
        rel = f.relative_to(out).as_posix()
        fm, body = split(f.read_text(encoding="utf-8"))
        if f.name not in {"index.md", "log.md"} and "type" not in fm:
            problems.append(f"{rel}: sin type en el frontmatter")
        if not re.search(r"(?m)^# ", body):
            problems.append(f"{rel}: sin H1")
        converted = rel.startswith(("jira/", "confluence/"))   # texto original de la fuente: sus enlaces no son de la KB
        for link in [] if converted else re.findall(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)", body):
            if not link.startswith("http") and not (f.parent / link).resolve().exists():
                problems.append(f"{rel}: enlace roto {link}")
        problems += [f"{rel}: posible dato sensible -> {h}" for h in scan(body) if "REDACTAD" not in h]
    return problems


def commit(out: Path, message: str) -> None:
    if not (out / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=out, check=False)
    subprocess.run(["git", "add", "-A"], cwd=out, check=False)
    subprocess.run(["git", "-c", "user.name=okf-curation", "-c", "user.email=okf-curation@example.com", "commit", "-qm", message],
                   cwd=out, check=False)
