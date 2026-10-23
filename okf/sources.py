"""Lectura de fuentes: selección de ficheros, limpieza de datos personales y secretos, escaneo previo."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .config import Repo

SKIP_DIRS = {"bin", "obj", ".git", "node_modules", ".vs", "dist", "build", "__pycache__", ".venv"}


def glob_regex(pattern: str) -> re.Pattern:
    """Glob por segmentos: `*` no cruza `/`, `**` sí."""
    rx = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.compile(rx + r"\Z")


def files(repo: Repo, key: str = "include") -> list[Path]:
    """Ficheros del repo que casan con `include` (código) o `docs`; `exclude` se aplica siempre."""
    pats = [glob_regex(p) for p in getattr(repo, key)]
    excl = [glob_regex(p) for p in repo.exclude]
    out = []
    for p in sorted(repo.path.rglob("*")):
        if not p.is_file() or SKIP_DIRS & set(p.relative_to(repo.path).parts):
            continue
        rel = p.relative_to(repo.path).as_posix()
        if any(rx.match(rel) for rx in pats) and not any(rx.match(rel) for rx in excl):
            out.append(p)
    return out


_REDACT = [
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<CLAVE_AWS_REDACTADA>"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "<TOKEN_REDACTADO>"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "<CLAVE_PRIVADA_REDACTADA>"),
    (re.compile(r"(?<![\w.])\+\d{1,3}[\d \-]{8,13}\d(?![\w.])"), "<TELEFONO_REDACTADO>"),
    (re.compile(r"\b[\w.+-]+@(?!example\.)[\w-]+\.[\w.]{2,}\b"), "<EMAIL_REDACTADO>"),
]


def redact(text: str) -> str:
    """Quita teléfonos internacionales, emails, claves y tokens antes de que el texto salga hacia un modelo."""
    for rx, repl in _REDACT:
        text = rx.sub(repl, text)
    return text


def read(path: Path) -> str:
    return redact(path.read_text(encoding="utf-8", errors="replace"))


SECRETS = {
    "clave AWS": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "clave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "token tipo sk-": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "asignación de secreto": re.compile(r"(?i)\b(api[_-]?key|secret|password|token|connectionstring)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"),
    "teléfono": re.compile(r"(?<![\w.])\+?\d[\d \-]{9,14}\d(?![\w.])"),
    "IBAN": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{12,30}\b"),
}


def scan(text: str) -> list[str]:
    hits = []
    for label, rx in SECRETS.items():
        for m in rx.finditer(text):
            if label == "email" and "@example." in m.group(0).lower():
                continue
            if label == "teléfono" and re.match(r"\s*(19|20)\d{2}-\d", m.group(0)):   # fechas (aunque estén mal escritas), no teléfonos
                continue
            hits.append(f"{label}: {m.group(0)[:6]}…")
    return hits


def scan_repo(repo: Repo) -> dict[str, list[str]]:
    """Escaneo ANTES de enviar nada a un modelo: lo que encuentra se redacta, pero conviene revisarlo y excluirlo."""
    found = {}
    for key in ("include", "docs"):
        for f in files(repo, key):
            hits = scan(f.read_text(encoding="utf-8", errors="replace"))
            if hits:
                found[f.relative_to(repo.path).as_posix()] = sorted(set(hits))[:5]
    return found


def snapshot(repo: Repo) -> str:
    """Identificador de la foto: commit si es git; si no, hash del contenido incluido."""
    git = repo.path / ".git"
    if git.exists():
        head = (git / "HEAD").read_text().strip()
        if head.startswith("ref:"):
            ref = git / head.split(" ", 1)[1]
            if ref.exists():
                return ref.read_text().strip()[:12]
        return head[:12]
    h = hashlib.sha256()
    for f in files(repo):
        h.update(f.relative_to(repo.path).as_posix().encode())
        h.update(f.read_bytes())
    return "sha256-" + h.hexdigest()[:12]
