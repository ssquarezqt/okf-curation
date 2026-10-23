"""Orquesta la curación completa: fuentes → repo OKF. Ver METODOLOGIA.md para el porqué de cada paso.

  1. escanear   datos sensibles en las fuentes (informe en trabajo/; lo que se encuentre se redacta igualmente)
  2. extraer    hechos deterministas de cada repo
  3. guías      una guía de navegación por repo                       (LLM redactor)
  4. código     caso A (exportar_codigo): el código tal cual en la KB
  5. fichas     modo búsqueda: ficha por componente + catálogos       (LLM redactor)
  6. atlassian  Jira y Confluence → Markdown sin resumir               (sin LLM)
  7. integra    índice entre repos (+ fichas en modo búsqueda)         (LLM redactor)
  8. vigencia   registro de vigencia + preguntas al cliente           (2 detectores fuertes + fusión)
  9. publicar   index.md, log.md, lint y commit
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

from . import convert, extract, guides, integration, llm, validity
from .config import Config
from .okfio import append_log, build_indexes, commit, lint, now_iso, rmtree
from .sources import scan_repo

PASOS = ("guias", "codigo", "fichas", "atlassian", "integracion", "vigencia")


def run(cfg: Config, pasos: set[str] | None = None, offline: bool = False) -> dict:
    """offline=True: solo los pasos sin modelo (extraer, código, Atlassian, publicar). Sirve de prueba sin claves."""
    t0 = time.time()
    pasos = set(pasos or PASOS)
    if offline:
        pasos -= {"guias", "fichas", "integracion", "vigencia"}
    out, trabajo = cfg.salida, cfg.trabajo
    keep_git = (out / ".git").exists()
    if out.exists() and pasos >= set(PASOS) - {"codigo", "fichas"}:   # curación completa: se regenera entero, conservando el historial git
        for p in out.iterdir():
            if p.name != ".git":
                rmtree(p) if p.is_dir() else p.unlink()
    out.mkdir(parents=True, exist_ok=True)
    trabajo.mkdir(parents=True, exist_ok=True)
    gen = {"by": f"okf-curation ({cfg.modelo('redactor')})", "at": now_iso()}
    info = {"sistema": cfg.sistema, "modo": cfg.modo}

    print("[1/9] escaneo de datos sensibles", flush=True)
    scans = {r.name: scan_repo(r) for r in cfg.repos}
    (trabajo / "escaneo-fuentes.json").write_text(json.dumps(scans, ensure_ascii=False, indent=1), encoding="utf-8")
    info["ficheros_con_avisos"] = {k: len(v) for k, v in scans.items()}

    print("[2/9] extracción de hechos", flush=True)
    fxs = {r.name: extract.build(r) for r in cfg.repos}
    info["ficheros"] = {k: len(v["files"]) for k, v in fxs.items()}

    if "guias" in pasos:
        print("[3/9] guías de cada repo", flush=True)
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda fx: guides.write_guide(fx, out, cfg.modelo("redactor"), gen), fxs.values()))
    if "codigo" in pasos and cfg.exportar_codigo:
        print("[4/9] código tal cual (caso A)", flush=True)
        info["codigo_exportado"] = sum(guides.export_code(fx, out, gen) for fx in fxs.values())
    if "fichas" in pasos and cfg.modo == "busqueda":
        print("[5/9] digest del repo: fichas, flujos, restricciones y catálogos (modo búsqueda)", flush=True)
        from . import cards
        info["fichas"] = {k: cards.build(fx, out, cfg.modelo("redactor"), gen) for k, fx in fxs.items()}

    jira_md, conf_md = [], []
    if "atlassian" in pasos or "vigencia" in pasos:
        if cfg.jira:
            issues = sorted(convert.load_jira(cfg.jira), key=lambda i: i["fields"].get("resolutiondate") or i["fields"].get("created") or "")
            jira_md = [(i["key"], convert.issue_md(i)) for i in issues]
        if cfg.confluence:
            pages = convert.load_confluence(cfg.confluence)
            conf_md = [(p["id"], convert.page_md(p, x)) for p, x in pages]
    if "atlassian" in pasos:
        print("[6/9] Jira y Confluence a Markdown", flush=True)
        if cfg.jira:
            info["jira"] = convert.write_jira(convert.load_jira(cfg.jira), out, gen)
        if cfg.confluence:
            info["confluence"] = convert.write_confluence(convert.load_confluence(cfg.confluence), out, gen)

    if "integracion" in pasos and cfg.integraciones:
        print("[7/9] índice de integración entre repos", flush=True)
        info["integracion"] = {f"{c}->{p}": integration.build(fxs[c], fxs[p], out, cfg.modelo("redactor"), gen, cfg.modo == "busqueda")
                               for c, p in cfg.integraciones}

    if "vigencia" in pasos and (jira_md or conf_md):
        print(f"[8/9] registro de vigencia ({', '.join(cfg.detectores())})", flush=True)
        secs = validity.corpus_sections(list(fxs.values()), jira_md, conf_md)
        info["vigencia"] = validity.build(secs, cfg.detectores(), cfg.modelo("fusion"), out, trabajo, cfg.sistema,
                                          {"by": f"okf-curation vigencia ({', '.join(cfg.detectores())})", "at": now_iso()})

    print("[9/9] publicar", flush=True)
    build_indexes(out, cfg.sistema, cfg.modo)
    append_log(out, f"curación ({cfg.modo}; pasos: {', '.join(sorted(pasos))})")
    info["lint"] = lint(out)
    info["documentos"] = sum(1 for p in out.rglob("*.md") if ".git" not in p.parts)
    info["minutos"] = round((time.time() - t0) / 60, 1)
    info["uso_modelos"] = dict(llm.usage)
    (trabajo / "informe.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    commit(out, f"Curación {cfg.sistema} ({cfg.modo})" + (" [regenerada]" if keep_git else ""))
    return info
