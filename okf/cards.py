"""Modo búsqueda: el digest del repo (skill repo-digest) cuando el agente no puede leer el código.

  componentes/   una ficha por componente, contrato primero (skill component-card)
  flujos/        3–6 procesos de negocio de punta a punta
  restricciones-trampas.md
  catalogos/     variables de entorno, tablas, comandos y configuración (deterministas)

Solo se generan si el agente recibe trozos de un buscador (Foundry IQ). En el piloto, esta estructura fija (M6) subió el
acierto de 43–52 % a 60–67 % frente a resumir por grupos, y fue estable entre ejecuciones.
"""
from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import extract, llm, skill
from .okfio import slug, write

ENTRY_STEMS = {"handler", "index", "main", "app", "lambda_function", "program", "function"}


def component_name(rel: str) -> str:
    p = Path(rel)
    return p.parent.name if p.stem.lower() in ENTRY_STEMS else f"{p.parent.name}/{p.stem}"


def group_of(rel: str) -> str:
    parts = rel.split("/")
    return "-".join(parts[1:3]) if parts[0] == "src" and len(parts) > 3 else parts[1] if parts[0] == "src" and len(parts) > 2 else parts[0] if len(parts) > 1 else "raiz"


def catalogs(fx: dict, out: Path, gen: dict) -> int:
    base, src, made = out / "repos" / fx["repo"] / "catalogos", [{"resource": f"{fx['repo']}@{fx['snapshot']}"}], 0
    env, tab = defaultdict(list), defaultdict(list)
    for r, f in fx["files"].items():
        for e in f.get("env", []):
            env[e].append(r)
        for t in f.get("tables", []):
            tab[t].append(r)
    if env:
        write(base / "variables-entorno.md", {"type": "Catalog", "title": f"Variables de entorno de {fx['repo']}", "sources": src, "generated": gen, "status": "stable"},
              f"# Catalog · Variables de entorno de {fx['repo']}\n\n" + "\n".join(f"- `{e}`: la leen {', '.join(f'`{r}`' for r in sorted(rs))}" for e, rs in sorted(env.items())))
        made += 1
    if tab:
        write(base / "tablas.md", {"type": "Catalog", "title": f"Tablas de {fx['repo']}", "sources": src, "generated": gen, "status": "stable"},
              f"# Catalog · Tablas de {fx['repo']}\n\n" + "\n".join(f"- `{t}`: la usan {', '.join(f'`{r}`' for r in sorted(rs))}" for t, rs in sorted(tab.items())))
        made += 1
    cmds = [(r, c) for r, f in fx["files"].items() for c in f.get("commands", [])]
    lit = [(r, f["literal"]) for r, f in fx["files"].items() if f.get("literal") and f["kind"] in {"config", "ci"}]
    if cmds or lit:
        body = [f"# Catalog · Comandos y configuración de {fx['repo']}", ""] + [f"- `{c}` (en `{r}`)" for r, c in cmds]
        for r, t in lit:
            body += ["", f"## Configuración literal de `{r}` ({fx['repo']})", "", "```", t, "```"]
        write(base / "comandos-configuracion.md", {"type": "Catalog", "title": f"Comandos y configuración de {fx['repo']}", "sources": src,
                                                   "generated": gen, "status": "stable"}, "\n".join(body))
        made += 1
    return made


def _spec(rel: str, fx: dict) -> dict:
    name = component_name(rel)
    tests = [r for r, f in fx["files"].items() if f["kind"] == "test" and name.split("/")[-1] in r][:2]
    return {"rel": rel, "name": name, "files": [rel] + tests, "path": f"repos/{fx['repo']}/componentes/{group_of(rel)}/{slug(name)}.md"}


def _write_card(s: dict, fx: dict, out: Path, model: str, gen: dict) -> None:
    system = skill("okf-format") + "\n\n" + skill("component-card")
    src = "\n\n".join(f"### `{r}`\n```\n{fx['texts'][r][:20000]}\n```" for r in s["files"])
    user = (f"Repositorio: {fx['repo']}. Contexto: {fx['contexto']}\nFicha del componente `{s['name']}` (`{s['rel']}`).\n\n"
            f"HECHOS:\n{extract.facts_block(s['files'], fx)}\n\nFUENTES:\n{src}")
    doc = llm.json_call(model, system, user)
    body = doc.get("body", "")
    missing = [h for h in extract.required_facts(s["files"], fx) if h not in body][:40]
    if missing:   # verificación con corrección: los hechos del fichero deben aparecer literalmente
        fixed = llm.json_call(model, system, f"Esta ficha omite hechos que debe incluir LITERALMENTE: {missing}\n\nHECHOS:\n"
                              f"{extract.facts_block(s['files'], fx)}\n\nFICHA ACTUAL:\n{body}\n\nDevuelve la ficha completa corregida (mismo JSON).")
        body = fixed.get("body", body)
    write(out / s["path"], {"type": "API", "title": doc.get("title", s["name"]), "description": doc.get("description", ""), "tags": doc.get("tags", []),
                            "sources": [{"resource": f"{fx['repo']}@{fx['snapshot']}:{r}"} for r in s["files"]], "generated": gen, "status": "draft"}, body)


def _sources(files: list[str], fx: dict, budget: int = 60_000) -> str:
    parts, used = [], 0
    for r in files:
        t = fx["texts"].get(r)
        if t is None or used + len(t) > budget:
            continue
        parts.append(f"### `{r}`\n```\n{t}\n```")
        used += len(t)
    return "\n\n".join(parts)


def flows(fx: dict, out: Path, model: str, gen: dict, parallel: int = 6) -> int:
    """3–6 procesos de negocio de punta a punta (skill repo-digest): juntan lo que está repartido entre ficheros."""
    system = skill("okf-format") + "\n\n" + skill("repo-digest")
    code = [r for r, f in fx["files"].items() if f["kind"] == "code"]
    plan = llm.json_call(model, system, f"Repositorio: {fx['repo']}. Contexto: {fx['contexto']}\n\nINVENTARIO:\n{extract.inventory(fx, {'code', 'script', 'config'})}\n\n"
                         f"HECHOS GLOBALES:\n{extract.global_facts(fx)}\n\nElige los flujos. Devuelve SOLO JSON "
                         '{"flows": [{"name": "nombre de negocio", "files": ["rutas exactas del inventario, en orden"], "question": "¿Qué pasa cuando …?"}]}').get("flows", [])[:6]

    def one(f):
        files = [r for r in f.get("files", []) if r in fx["texts"]] or code[:3]
        doc = llm.json_call(model, system, f"Repositorio: {fx['repo']}. Escribe el flujo «{f['name']}» ({f.get('question', '')}).\n\n"
                            f"HECHOS:\n{extract.facts_block(files, fx)}\n\nFUENTES:\n{_sources(files, fx)}")
        write(out / "repos" / fx["repo"] / "flujos" / f"{slug(f['name'])}.md",
              {"type": "Flow", "title": doc.get("title", f["name"]), "description": doc.get("description", ""), "tags": doc.get("tags", []),
               "sources": [{"resource": f"{fx['repo']}@{fx['snapshot']}:{r}"} for r in files], "generated": gen, "status": "draft"}, doc.get("body", ""))

    with ThreadPoolExecutor(parallel) as pool:
        list(pool.map(one, plan))
    return len(plan)


def restrictions(fx: dict, out: Path, model: str, gen: dict) -> None:
    """Lo que hay que saber para no romper nada, a partir de los comentarios de advertencia y del código central."""
    notes = "\n".join(f"- `{r}`: {n}" for r, f in fx["files"].items() for n in f.get("notes", []))[:20000]
    hubs = sorted((r for r, f in fx["files"].items() if f["kind"] == "code"), key=lambda r: -len(fx["files"][r].get("used_by", [])))
    doc = llm.json_call(model, skill("okf-format") + "\n\n" + skill("repo-digest"),
                        f"Repositorio: {fx['repo']}. Escribe el documento de restricciones y trampas.\n\nCOMENTARIOS DE ADVERTENCIA Y DECISIÓN:\n{notes}\n\n"
                        f"HECHOS GLOBALES:\n{extract.global_facts(fx)}\n\nCÓDIGO CENTRAL:\n{_sources(hubs, fx, 50_000)}")
    write(out / "repos" / fx["repo"] / "restricciones-trampas.md", {"type": "Reference", "title": doc.get("title", f"Restricciones y trampas de {fx['repo']}"),
                                                                     "description": doc.get("description", ""), "generated": gen, "status": "draft",
                                                                     "sources": [{"resource": f"{fx['repo']}@{fx['snapshot']}"}]}, doc.get("body", ""))


def build(fx: dict, out: Path, model: str, gen: dict, parallel: int = 10) -> dict:
    """Digest completo del modo búsqueda: fichas por componente, flujos, restricciones y catálogos (la guía va aparte)."""
    specs = [_spec(r, fx) for r, f in sorted(fx["files"].items()) if f["kind"] == "code"]
    with ThreadPoolExecutor(parallel) as pool:
        list(pool.map(lambda s: _write_card(s, fx, out, model, gen), specs))
    n_flows = flows(fx, out, model, gen)
    restrictions(fx, out, model, gen)
    return {"fichas": len(specs), "flujos": n_flows, "catalogos": catalogs(fx, out, gen), "restricciones": 1}
