"""Índice de integración entre repos (skill integration-index). En modo búsqueda, además, una ficha por pareja."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import extract, llm, skill
from .okfio import slug, write

CALLS = re.compile(r"fetch\(|axios|HttpClient|requests\.(get|post|put|delete)|httpx|_URL\b|_API_URL|baseURL|baseUrl|invoke\(|\.send\(")


def consumer_material(fx: dict, budget: int = 90_000) -> str:
    files = [r for r, f in fx["files"].items() if f["kind"] == "code" and CALLS.search(fx["texts"][r])]
    files.sort(key=lambda r: -len(CALLS.findall(fx["texts"][r])))
    parts, used = [], 0
    for r in files:
        t = fx["texts"][r]
        if used + len(t) > budget:
            continue
        parts.append(f"### `{r}`\n```\n{t}\n```")
        used += len(t)
    return "\n\n".join(parts)


def provider_material(fx: dict) -> str:
    literals = "\n\n".join(f"### `{r}`\n```\n{f['literal']}\n```" for r, f in fx["files"].items()
                           if f.get("literal") and f["kind"] in {"config", "script"})[:30000]
    return f"INVENTARIO DE CÓDIGO:\n{extract.inventory(fx, {'code'})}\n\nCONFIGURACIÓN (rutas, despliegue):\n{literals}"


def _snippet(text: str, symbol: str, lines: int = 90) -> str:
    m = re.search(rf"(?m)^.*\b{re.escape(symbol)}\b\s*[(=:]", text)
    if not m:
        return ""
    start = text[:m.start()].count("\n")
    return "\n".join(text.splitlines()[start:start + lines])


def build(cons: dict, prov: dict, out: Path, model: str, gen: dict, with_cards: bool) -> int:
    pairs = llm.json_call(model, skill("integration-index"),
                          f"CONSUMIDOR: {cons['repo']}\n{consumer_material(cons)}\n\nPROVEEDOR: {prov['repo']}\n{provider_material(prov)}").get("pairs", [])
    clean = lambda v: None if v in (None, "", "null") else str(v).strip("` ")
    pairs = [{k: clean(v) for k, v in p.items()} for p in pairs]
    rows = [f"| `{p.get('consumer_symbol') or '—'}` (`{p.get('consumer_file')}`) | " + (f"`{p['provider_file']}`" if p.get("provider_file") else "—")
            + f" | {p.get('via') or ''} | {(p.get('why') or '')[:160]} |" for p in pairs]
    name = f"{cons['repo']}--{prov['repo']}"
    write(out / "integracion" / f"{name}.md", {"type": "Integration Index", "title": f"Integración {cons['repo']} → {prov['repo']}",
                                               "description": f"Qué componente de {prov['repo']} atiende cada llamada de {cons['repo']}.",
                                               "sources": [{"resource": f"{cons['repo']}@{cons['snapshot']}"}, {"resource": f"{prov['repo']}@{prov['snapshot']}"}],
                                               "generated": gen, "status": "draft"},
          f"# Integration Index · {cons['repo']} → {prov['repo']}\n\nCada fila: la llamada del consumidor, el fichero del proveedor que la "
          "atiende, por dónde pasa (variable de URL, ruta o SDK) y la evidencia. Úsalo para saber dónde mirar en cada repo.\n\n"
          "| Llamada en el consumidor | Componente del proveedor | Vía | Evidencia |\n|---|---|---|---|\n" + "\n".join(rows))
    if with_cards:   # modo búsqueda: ficha por pareja con lo que envía y lee cada lado
        def card(p):
            if not p.get("provider_file") or p["provider_file"] not in prov["texts"]:
                return
            sym = p.get("consumer_symbol") or ""
            csrc = _snippet(cons["texts"].get(p.get("consumer_file", ""), ""), sym) or cons["texts"].get(p.get("consumer_file", ""), "")[:8000]
            doc = llm.json_call(model, skill("okf-format") + '\nDevuelve SOLO JSON {"title", "description", "body"}.',
                                f"Ficha de integración `{sym}` ({cons['repo']}) ↔ `{p['provider_file']}` ({prov['repo']}). Secciones, cada encabezado "
                                f"empieza por `{sym}`: Qué hace · Componente que lo atiende (vía {p.get('via')}) · Qué envía y qué lee cada lado (marca lo que no "
                                "coincida) · Qué devuelve y qué usa el consumidor · Permisos y errores · Si cambias algo, qué se rompe.\n\n"
                                f"CONSUMIDOR `{p.get('consumer_file')}`:\n```\n{csrc}\n```\n\nPROVEEDOR `{p['provider_file']}`:\n```\n{prov['texts'][p['provider_file']][:14000]}\n```")
            write(out / "integracion" / name / f"{slug(sym)}.md", {"type": "Integration", "title": doc.get("title", sym), "description": doc.get("description", ""),
                                                                   "generated": gen, "status": "draft"}, doc.get("body", ""))
        with ThreadPoolExecutor(8) as pool:
            list(pool.map(card, pairs))
    return len(pairs)
