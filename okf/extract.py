"""Hechos deterministas de un repo (sin LLM): inventario completo y lo que cada fichero define, lee y usa.

Por fichero: kind (code|test|script|config|ci|doc), header, symbols, signatures, env, tables, uses/used_by,
commands, notes (comentarios de advertencia o decisión) y literal (configuración y scripts pequeños, completos).
Lenguajes: Python, TypeScript/JavaScript y C#. Todo el texto pasa por redact().
"""
from __future__ import annotations

import json
import posixpath
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from . import sources
from .config import Repo

LITERAL_MAX = 6_000
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".cs")
CS_TYPE = re.compile(r"\b(?:public|internal)\s+(?:sealed\s+|static\s+|abstract\s+|partial\s+)*(?:class|record|interface|struct|enum)\s+(\w+)")
PY_DEF = re.compile(r"(?m)^(?:async\s+)?(?:def|class)\s+(\w+)")
TS_EXPORT = re.compile(r"(?m)^export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|const|let|class|interface|type|enum)\s+(\w+)")
ENV = re.compile(r"""os\.environ(?:\.get)?\s*[\[(]\s*['"]([A-Z][A-Z0-9_]+)['"]|os\.getenv\(\s*['"]([A-Z][A-Z0-9_]+)['"]"""
                 r"""|GetEnvironmentVariable\(\s*"([A-Z][A-Z0-9_]+)"\)|process\.env\.([A-Z][A-Z0-9_]+)|import\.meta\.env\.([A-Z][A-Z0-9_]+)""")
TABLE = re.compile(r"""\.Table\(\s*['"]([\w\-]+)['"]\s*\)""")
NOTE = re.compile(r"(?i)\b(porque|ojo|importante|nunca|siempre|bug|workaround|deuda|legacy|todo|fixme|hack|decisi[oó]n|en vez de|"
                  r"en lugar de|cuidado|warning|note|why|because|do not|don't)\b|⚠")


def kind_of(rel: str) -> str:
    p = rel.lower()
    if p.endswith(".md"):
        return "doc"
    if "/test" in p or p.startswith("test") or ".test." in p or ".spec." in p or "tests/" in p:
        return "test"
    if p.startswith(".github/") or "azure-pipelines" in p or p.endswith(".gitlab-ci.yml"):
        return "ci"
    if p.endswith((".sh", ".ps1", ".bat")) or (p.startswith("scripts/") and p.endswith(".py")):
        return "script"
    if p.endswith((".yaml", ".yml", ".json", ".toml", ".csproj", ".sln", ".txt", ".cfg", ".ini", ".config", ".xml", ".html")) or "dockerfile" in p:
        return "config"
    return "code"


def declared(rel: str, text: str) -> list[str]:
    if rel.endswith(".cs"):
        return CS_TYPE.findall(text)
    if rel.endswith(".py"):
        return [n for n in PY_DEF.findall(text) if not n.startswith("_")]
    if rel.endswith((".ts", ".tsx", ".js", ".jsx")):
        return list(dict.fromkeys(TS_EXPORT.findall(text)))
    return []


def header(rel: str, text: str) -> str:
    """Docstring del módulo (Python), bloque /** */ (TS/JS) o comentarios // iniciales (C#)."""
    if rel.endswith(".py"):
        m = re.match(r'\s*(?:#.*\n)*\s*("""|\'\'\')(.*?)\1', text, re.S)
        return m.group(2).strip() if m else ""
    if rel.endswith((".ts", ".tsx", ".js", ".jsx")):
        m = re.match(r"\s*(?:import[^\n]*\n|\s)*/\*\*?(.*?)\*/", text, re.S)
        if m:
            return "\n".join(l.strip().lstrip("* ").rstrip() for l in m.group(1).splitlines()).strip()
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("//"):
            lines.append(s.lstrip("/ ").rstrip())
        elif s.startswith("using ") or not s:
            continue
        else:
            break
    return "\n".join(lines).strip()


def signatures(rel: str, text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        s = line.rstrip()
        if rel.endswith(".cs") and re.match(r"^\s*(public|internal)\b", s) and "override" not in s:
            out.append(s.strip().rstrip("{").rstrip())
        elif rel.endswith(".py") and re.match(r"^(async\s+)?(def|class)\s+[A-Za-z]", s):
            out.append(s.rstrip(":"))
        elif rel.endswith((".ts", ".tsx", ".js", ".jsx")) and re.match(r"^export\s", s):
            out.append(s.rstrip("{").rstrip()[:200])
    return out[:60]


def commands(rel: str, text: str, kind: str) -> list[str]:
    cmds = []
    if kind == "script" and rel.endswith(".sh"):
        for line in text.splitlines()[:60]:
            s = line.strip()
            if s.startswith("#") and ("./" in s or "uso" in s.lower() or "usage" in s.lower()):
                cmds.append(s.lstrip("# ").strip())
        cmds += [f"{Path(rel).name} {m}" for m in re.findall(r"^\s*([\w\-|]+)\)\s*$", text, re.M) if m != "*"]
    if kind == "script" and rel.endswith(".py"):
        cmds += [f"python {rel} {m}" for m in re.findall(r"add_argument\(\s*['\"](--[\w\-]+)", text)]
    if kind == "ci":
        cmds += [f"CI: {m.strip()}" for m in re.findall(r"^\s*(?:-\s*)?(?:run|script):\s*(.+)$", text, re.M)]
    return list(dict.fromkeys(c for c in cmds if c))


def notes(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("#", "//", "*")) and NOTE.search(s) and len(s) > 25:
            out.append(s.lstrip("#/* ").strip()[:240])
    return list(dict.fromkeys(out))[:25]


def _uses(rel: str, text: str, texts: dict, owner: dict, py_modules: dict) -> set[str]:
    uses = set()
    if rel.endswith(".cs"):
        uses = {w for t, w in owner.items() if w != rel and re.search(rf"\b{re.escape(t)}\b", text)}
    elif rel.endswith(".py"):
        for m in re.finditer(r"(?m)^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", text):
            mod = m.group(1) or m.group(2)
            uses |= {w for k, w in py_modules.items() if (mod == k or mod.endswith("." + k)) and w != rel}
    elif rel.endswith((".ts", ".tsx", ".js", ".jsx")):   # imports relativos y alias @/ (= src/)
        targets = {posixpath.normpath(posixpath.join(posixpath.dirname(rel), m)) if m.startswith(".") else "src/" + m[2:]
                   for m in re.findall(r"from\s+['\"]((?:\.|@/)[^'\"]+)['\"]", text)}
        uses = {r for t in targets for r in texts if r != rel and re.fullmatch(re.escape(t) + r"(\.\w+|/index\.\w+)", r)}
    return uses


def _projects(repo: Repo, texts: dict) -> list[dict]:
    out = []
    for r in texts:
        p = repo.path / r
        try:
            if r.endswith(".csproj"):
                root = ET.parse(p).getroot()
                tf = [e.text for e in root.iter("TargetFramework")]
                out.append({"name": p.stem, "kind": f".NET {tf[0] if tf else ''}".strip(),
                            "packages": [(e.get("Include"), e.get("Version") or "") for e in root.iter("PackageReference")]})
            elif r.endswith("pyproject.toml"):
                proj = tomllib.loads(p.read_text(encoding="utf-8")).get("project", {})
                out.append({"name": proj.get("name", repo.name), "kind": f"Python {proj.get('requires-python', '')}".strip(),
                            "packages": [(d, "") for d in proj.get("dependencies", [])]})
            elif r == "package.json":
                d = json.loads(p.read_text(encoding="utf-8"))
                out.append({"name": d.get("name", repo.name), "kind": "Node/TS", "packages": list((d.get("dependencies") or {}).items()),
                            "scripts": d.get("scripts", {})})
        except Exception:
            continue
    return out


def build(repo: Repo) -> dict:
    paths = list(dict.fromkeys(sources.files(repo, "include") + sources.files(repo, "docs")))
    texts = {p.relative_to(repo.path).as_posix(): sources.read(p) for p in paths}
    code = [r for r in texts if r.endswith(CODE_EXT)]
    owner = {t: r for r in code if r.endswith(".cs") for t in declared(r, texts[r])}
    py_modules = {r.removesuffix(".py").split("src/", 1)[-1].replace("/", "."): r for r in code if r.endswith(".py")}
    py_modules.update({k.rsplit(".", 1)[-1]: v for k, v in list(py_modules.items()) if k.startswith("shared.")})
    files = {}
    for rel, text in texts.items():
        k = kind_of(rel)
        f = {"kind": k, "size": len(text), "header": header(rel, text)[:600], "symbols": declared(rel, text),
             "signatures": signatures(rel, text), "env": sorted({g for m in ENV.finditer(text) for g in m.groups() if g}),
             "tables": sorted(set(TABLE.findall(text))), "uses": sorted(_uses(rel, text, texts, owner, py_modules)) if rel in code else [],
             "commands": commands(rel, text, k), "notes": notes(text) if k != "doc" else []}
        if k in {"config", "script", "ci"} and len(text) <= LITERAL_MAX:
            f["literal"] = text
        files[rel] = f
    for rel, f in list(files.items()):
        for u in f["uses"]:
            files[u].setdefault("used_by", []).append(rel)
    return {"repo": repo.name, "snapshot": sources.snapshot(repo), "contexto": repo.contexto, "projects": _projects(repo, texts),
            "files": files, "texts": texts}


# ------------------------------------------------------------------ material para los prompts

def inventory(fx: dict, kinds: set[str] | None = None) -> str:
    lines = []
    for rel, f in sorted(fx["files"].items()):
        if kinds and f["kind"] not in kinds:
            continue
        bits = [f"- `{rel}` [{f['kind']}, {f['size']} c]"]
        if f.get("header"):
            bits.append(f["header"].splitlines()[0][:140])
        if f.get("symbols"):
            bits.append("define: " + ", ".join(f["symbols"][:8]))
        if f.get("env"):
            bits.append("env: " + ", ".join(f["env"][:10]))
        if f.get("tables"):
            bits.append("tablas: " + ", ".join(f["tables"]))
        if f.get("used_by"):
            bits.append(f"lo usan {len(f['used_by'])}")
        lines.append(" · ".join(bits))
    return "\n".join(lines)


def global_facts(fx: dict) -> str:
    lines = ["Proyectos y paquetes:"]
    for p in fx["projects"]:
        lines.append(f"- {p['name']} ({p.get('kind', '')}): " + ", ".join(f"{a} {b}".strip() for a, b in p.get("packages", [])[:25]))
        if p.get("scripts"):
            lines.append("  scripts: " + ", ".join(f"{k}: {v}" for k, v in p["scripts"].items()))
    cmds = [c for f in fx["files"].values() for c in f.get("commands", [])]
    if cmds:
        lines.append("Comandos: " + "; ".join(dict.fromkeys(cmds)))
    top = sorted(((len(f.get("used_by", [])), r) for r, f in fx["files"].items()), reverse=True)[:12]
    lines.append("Ficheros más usados: " + ", ".join(f"`{r}` ({n})" for n, r in top if n))
    lines.append("Variables de entorno: " + ", ".join(f"`{e}`" for e in sorted({e for f in fx["files"].values() for e in f.get("env", [])})))
    tables = sorted({t for f in fx["files"].values() for t in f.get("tables", [])})
    if tables:
        lines.append("Tablas: " + ", ".join(f"`{t}`" for t in tables))
    return "\n".join(lines)


def facts_block(files: list[str], fx: dict) -> str:
    out = []
    for rel in files:
        f = fx["files"].get(rel)
        if not f:
            continue
        part = [f"### HECHOS de `{rel}` ({f['kind']})"]
        if f.get("header"):
            part.append(f"Cabecera: {f['header']}")
        for key, label in (("env", "Variables de entorno"), ("tables", "Tablas"), ("commands", "Comandos"), ("uses", "Usa"), ("used_by", "Lo usan")):
            if f.get(key):
                part.append(f"{label}: " + ", ".join(f"`{v}`" for v in f[key][:30]))
        if f.get("notes"):
            part.append("Advertencias y decisiones en comentarios:\n" + "\n".join(f"- {n}" for n in f["notes"]))
        if f.get("signatures"):
            part.append("Firmas públicas:\n" + "\n".join(f"- `{s.strip()}`" for s in f["signatures"][:40]))
        if f.get("literal"):
            part.append(f"Contenido literal:\n```\n{f['literal']}\n```")
        out.append("\n".join(part))
    return "\n\n".join(out)


def required_facts(files: list[str], fx: dict) -> list[str]:
    """Hechos que un documento debe contener literalmente: variables, tablas, comandos cortos y símbolos públicos."""
    req = []
    for rel in files:
        f = fx["files"].get(rel, {})
        req += f.get("env", []) + f.get("tables", []) + [c for c in f.get("commands", []) if len(c) <= 80]
        req += [s for s in f.get("symbols", []) if len(s) > 3][:15]
    return list(dict.fromkeys(req))
