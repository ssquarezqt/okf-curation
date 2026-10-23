"""Guía de navegación de cada repo (skill repo-guide) y, si se pide, el código tal cual para el caso A."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from . import extract, llm, skill
from .okfio import write

CODE_BUDGET = 60_000
LANG = {".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript", ".cs": "csharp", ".json": "json", ".yaml": "yaml",
        ".yml": "yaml", ".sh": "bash", ".csproj": "xml", ".toml": "toml"}


def _folders(fx: dict) -> str:
    """Mapa determinista de carpetas: cuántos ficheros y de qué tipo, con ejemplos."""
    by = {}
    for rel, f in sorted(fx["files"].items()):
        folder = "/".join(rel.split("/")[:3]) if rel.count("/") >= 3 else str(Path(rel).parent.as_posix())
        by.setdefault(folder, []).append((rel, f["kind"]))
    lines = []
    for folder, items in sorted(by.items()):
        kinds = Counter(k for _, k in items)
        lines.append(f"- `{folder}/`: {len(items)} ficheros ({', '.join(f'{n} {k}' for k, n in kinds.most_common())}); p. ej. "
                     + ", ".join(f"`{Path(r).name}`" for r, _ in items[:3]))
    return "\n".join(lines)


def material(fx: dict) -> str:
    readme = [r for r in fx["texts"] if r.lower().endswith("readme.md")]
    docs = "\n\n".join(f"### {r}\n{fx['texts'][r][:15000]}" for r in readme)
    literals = "\n\n".join(f"### `{r}`\n```\n{f['literal']}\n```" for r, f in fx["files"].items() if f.get("literal") and f["kind"] in {"config", "ci"})[:25000]
    hubs = sorted((r for r, f in fx["files"].items() if f["kind"] == "code"), key=lambda r: -len(fx["files"][r].get("used_by", [])))
    code, used = [], 0
    for r in hubs:
        t = fx["texts"][r]
        if used + len(t) > CODE_BUDGET:
            continue
        code.append(f"### `{r}`\n```\n{t}\n```")
        used += len(t)
    notes = "\n".join(f"- `{r}`: {n}" for r, f in fx["files"].items() for n in f.get("notes", []))[:12000]
    return (f"Repositorio: {fx['repo']}\nContexto: {fx['contexto']}\n\nINVENTARIO COMPLETO:\n{extract.inventory(fx)}\n\n"
            f"CARPETAS:\n{_folders(fx)}\n\nHECHOS GLOBALES:\n{extract.global_facts(fx)}\n\n"
            f"CONFIGURACIÓN LITERAL:\n{literals}\n\nCOMENTARIOS DE ADVERTENCIA Y DECISIÓN:\n{notes}\n\n"
            f"README Y DOCUMENTACIÓN:\n{docs or '(no hay)'}\n\nCÓDIGO DE LOS FICHEROS CENTRALES:\n" + "\n\n".join(code))


def write_guide(fx: dict, out: Path, model: str, gen: dict) -> str:
    doc = llm.json_call(model, skill("okf-format") + "\n\n" + skill("repo-guide"), material(fx))
    body = doc.get("body", f"# Repository Guide · {fx['repo']}\n\n(la guía no se pudo generar)")
    write(out / "repos" / fx["repo"] / "guia.md", {"type": "Repository Guide", "title": doc.get("title", fx["repo"]),
                                                   "description": doc.get("description", ""), "tags": doc.get("tags", []),
                                                   "sources": [{"resource": f"{fx['repo']}@{fx['snapshot']}"}], "generated": gen,
                                                   "status": "draft"}, body)
    return body


def export_code(fx: dict, out: Path, gen: dict) -> int:
    """Caso A: el agente no clona el repo pero sí puede leer ficheros de la KB → el código va tal cual (ya redactado)."""
    n = 0
    for rel, text in fx["texts"].items():
        if fx["files"][rel]["kind"] == "doc":
            body = text
        else:
            body = f"# Source File · {rel}\n\n```{LANG.get(Path(rel).suffix, '')}\n{text}\n```"
        write(out / "repos" / fx["repo"] / "codigo" / (rel + ".md"), {"type": "Source File", "title": rel,
                                                                       "sources": [{"resource": f"{fx['repo']}@{fx['snapshot']}:{rel}"}],
                                                                       "generated": gen, "status": "stable"}, body)
        n += 1
    return n
