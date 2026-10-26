"""Registro de vigencia (skill validity-register) y confirmación del cliente (skill client-confirmation).

  1. detectar   cada modelo detector lee TODAS las fuentes juntas, en orden cronológico, y registra los valores y reglas
                con su historia, clasificados como consistente | cambio | contradiccion
  2. fusionar   un modelo une lo que encontraron los detectores; si discrepan en el valor vigente, es contradicción
  3. publicar   vigencia/<tema>.md en el repo OKF + vigencia/pendientes.md
  4. preguntar  trabajo/confirmaciones.md (para el experto) + trabajo/respuestas.yaml (donde se contestan)
  5. aplicar    `okf confirm` lee las respuestas, actualiza el registro y vuelve a publicar

En el piloto: sin registro, el agente acertó el 14–36 % de las preguntas con conflicto entre fuentes; con registro, el 68–82 %.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from . import llm, skill
from .okfio import now_iso, slug, write

BATCH_CHARS = 300_000


def corpus_sections(fxs: list[dict], jira_md: list[tuple[str, str]], conf_md: list[tuple[str, str]]) -> list[str]:
    """Secciones en orden cronológico (Jira por fecha), después Confluence y la configuración literal de cada repo."""
    secs = [f"===== JIRA {k} =====\n{t}" for k, t in jira_md]
    secs += [f"===== CONFLUENCE {k} =====\n{t}" for k, t in conf_md]
    for fx in fxs:
        lit = "\n\n".join(f"### `{r}`\n```\n{f['literal']}\n```" for r, f in fx["files"].items() if f.get("literal") and f["kind"] in {"config", "ci"})
        if lit:
            secs.append(f"===== REPO {fx['repo']} (foto {fx['snapshot']}) · configuración =====\n{lit[:40000]}")
    return secs


def _batches(secs: list[str]) -> list[str]:
    out, cur = [], ""
    for s in secs:
        if cur and len(cur) + len(s) > BATCH_CHARS:
            out.append(cur)
            cur = ""
        cur += s + "\n\n"
    return out + ([cur] if cur else [])


def detect(model: str, secs: list[str]) -> list[dict]:
    entries = []
    for b in _batches(secs):
        # 64k: los modelos con razonamiento gastan parte de la salida pensando; con 32k el JSON llegaba cortado
        data = llm.json_call(model, skill("validity-register"), f"FUENTES:\n{b}", max_tokens=64000)
        if not data.get("entradas"):
            print(f"    AVISO: el detector {model} no devolvió entradas en un lote (¿salida cortada?)", flush=True)
        entries += data.get("entradas", [])
    for e in entries:
        e["detectado_por"] = [model]
    return entries


def merge(model: str, found: dict[str, list[dict]]) -> list[dict]:
    found = {m: es for m, es in found.items() if es}
    if len(found) <= 1:
        return next(iter(found.values()), [])
    data = llm.json_call(model, skill("validity-register") + "\n\nAHORA FUSIONAS los registros de varios detectores sobre las mismas fuentes: "
                         "une las entradas que hablan del mismo valor o regla (aunque las nombren distinto), junta sus cronologías sin duplicar, "
                         "y si los detectores proponen un valor vigente distinto o alguno la clasifica como contradicción, clasifícala como "
                         "contradiccion. Conserva las entradas que solo encontró un detector. Añade a cada entrada "
                         '"detectado_por": [modelos]. Devuelve SOLO JSON {"entradas": [...]} con el mismo esquema.',
                         "\n\n".join(f"REGISTRO DEL DETECTOR {m}:\n{json.dumps(es, ensure_ascii=False)}" for m, es in found.items()), max_tokens=64000)
    if not data.get("entradas"):   # si la fusión falla, mejor la unión sin fusionar que perderlo todo
        print("    AVISO: la fusión no devolvió entradas; se publica la unión de los detectores sin fusionar", flush=True)
        return [e for es in found.values() for e in es]
    return data.get("entradas", [])


def _iso(fecha) -> str:
    """Fecha de confirmación (AAAA-MM-DD o completa) en ISO 8601 con desfase UTC explícito, como pide OKF."""
    f = str(fecha or now_iso())
    return f if "T" in f else f"{f[:10]}T00:00:00+00:00"


def _norm(v) -> str:
    return re.sub(r"[^\w.]", "", str(v).lower())


def _chron(c) -> str:
    if isinstance(c, dict):
        return f"{c.get('fecha', '?')} · {c.get('fuente', '?')} · **{c.get('valor', '?')}**" + (f" — {c['detalle']}" if c.get("detalle") else "")
    return str(c)


def _options(e: dict) -> list[str]:
    """Valores distintos que aparecen en las fuentes (cortos y sin duplicados como `250` frente a `250 €`)."""
    seen, out = set(), []
    for c in e.get("cronologia", []):
        v = str(c.get("valor", "")).strip() if isinstance(c, dict) else ""
        if v and _norm(v) not in seen:
            seen.add(_norm(v))
            out.append(v)
    return out or [str(e.get("vigente", ""))]


def render(e: dict) -> str:
    t = e["tema"]
    detalle = f" {e['vigente_detalle']}" if e.get("vigente_detalle") else ""
    if e.get("estado") == "confirmado":
        head = f"**Valor vigente:** `{e['vigente']}`\n\nConfirmado por {e.get('confirmado_por', '?')} el {e.get('fecha_confirmacion', '?')}."
    elif e.get("clase") == "contradiccion":
        head = (f"**⚠ SIN CONFIRMAR.** Las fuentes no coinciden. Propuesta por fecha: **`{e.get('vigente')}`**. Valores que aparecen: "
                + ", ".join(f"`{o}`" for o in _options(e)) + ". Trátalo con cautela: compruébalo en el código o pregunta antes de depender de él."
                + (f"\n\n{e['nota']}" if e.get("nota") else ""))
    else:
        head = f"**Valor vigente:** `{e.get('vigente')}`.{detalle}" + (" Cambió con el tiempo: ver cronología." if e.get("clase") == "cambio" else "")
    body = [f"# Vigencia · {t}", "", head, "", f"## {t} · Cronología", ""] + [f"- {_chron(c)}" for c in e.get("cronologia", [])]
    if e.get("desactualizado_en"):
        body += ["", f"## {t} · Desactualizado en", ""] + [f"- {d}" for d in e["desactualizado_en"]]
    return "\n".join(body)


def publish(entries: list[dict], out: Path, gen: dict) -> None:
    folder = out / "vigencia"
    if folder.exists():
        for p in folder.glob("*.md"):
            p.unlink()
    for e in entries:
        stable = e.get("estado") == "confirmado" or e.get("clase") in {"consistente", "cambio"}
        # OKF: la confirmación de una persona va en `verified` con un actor `human:` (nivel de confianza "revisado por humano")
        verified = ([{"by": f"human:{e.get('confirmado_por') or 'cliente'}", "at": _iso(e.get("fecha_confirmacion"))}]
                    if e.get("estado") == "confirmado" else None)
        write(folder / f"{e['id']}-{slug(e['tema'], 50)}.md", {"type": "Vigencia", "title": f"Vigencia · {e['tema']}",
                                                              "description": f"Valor vigente: {str(e.get('vigente'))[:150]}", "generated": gen,
                                                              "verified": verified, "status": "stable" if stable else "draft"}, render(e))
    pend = [e for e in entries if e.get("clase") == "contradiccion" and e.get("estado") != "confirmado"]
    write(folder / "pendientes.md", {"type": "Vigencia", "title": "Contradicciones sin confirmar", "generated": gen, "status": "draft"},
          "# Vigencia · Contradicciones sin confirmar\n\nValores en los que las fuentes no coinciden y el cliente aún no ha confirmado "
          "cuál rige. Trátalos con cautela.\n\n" + ("\n".join(f"- [{e['tema']}]({e['id']}-{slug(e['tema'], 50)}.md): propuesta por fecha "
                                                             f"`{e.get('vigente')}`" for e in pend) or "Ninguna."))


def questions(entries: list[dict], trabajo: Path, sistema: str) -> int:
    """Una pregunta cerrada por contradicción, con las evidencias y la propuesta por fecha marcada."""
    pend = [e for e in entries if e.get("clase") == "contradiccion" and e.get("estado") != "confirmado"]
    md = [f"# Confirmación de valores vigentes · {sistema}", "",
          "Hemos encontrado valores en los que la documentación, los tickets y la configuración no coinciden. Para cada uno, "
          "marca el que rige hoy en producción (la propuesta por fecha va marcada) o escribe el correcto. Responde en "
          "`respuestas.yaml` (campo `respuesta`) o devuélvenos este documento marcado.", ""]
    ans = []
    for e in pend:
        opts = _options(e)
        md += [f"## {e['id']} · {e['tema']}", ""] + [f"- {_chron(c)}" for c in e.get("cronologia", [])] + ["", "¿Cuál rige hoy?  "
               + "  ".join(f"{'☒' if _norm(o) == _norm(e.get('vigente')) else '☐'} {o}" for o in opts) + "  ☐ Otro: ____", "",
               f"*Propuesta por fecha: {e.get('vigente')}*", ""]
        ans.append({"id": e["id"], "tema": e["tema"], "opciones": opts, "propuesta": e.get("vigente"), "respuesta": "", "confirmado_por": "", "fecha": ""})
    trabajo.mkdir(parents=True, exist_ok=True)
    (trabajo / "confirmaciones.md").write_text("\n".join(md), encoding="utf-8")
    resp = trabajo / "respuestas.yaml"
    old = {a["id"]: a for a in (yaml.safe_load(resp.read_text(encoding="utf-8")) or {}).get("respuestas", [])} if resp.exists() else {}
    ans = [{**a, **{k: old[a["id"]][k] for k in ("respuesta", "confirmado_por", "fecha") if old.get(a["id"], {}).get(k)}} for a in ans]
    resp.write_text(yaml.safe_dump({"sistema": sistema, "respuestas": ans}, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    return len(pend)


def build(secs: list[str], detectors: list[str], fusion: str, out: Path, trabajo: Path, sistema: str, gen: dict) -> dict:
    with ThreadPoolExecutor(len(detectors)) as pool:
        found = dict(zip(detectors, pool.map(lambda m: detect(m, secs), detectors)))
    trabajo.mkdir(parents=True, exist_ok=True)
    (trabajo / "detecciones.json").write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    entries = merge(fusion, found)
    for i, e in enumerate(entries, 1):
        e["id"] = f"v{i:03d}"
        e.setdefault("tema", f"entrada {i}")
    (trabajo / "registro.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    publish(entries, out, gen)
    n = questions(entries, trabajo, sistema)
    clases = {}
    for e in entries:
        clases[e.get("clase", "?")] = clases.get(e.get("clase", "?"), 0) + 1
    return {"entradas": len(entries), "por_clase": clases, "preguntas_al_cliente": n, "por_detector": {m: len(v) for m, v in found.items()}}


def apply_answers(out: Path, trabajo: Path, sistema: str) -> int:
    entries = json.loads((trabajo / "registro.json").read_text(encoding="utf-8"))
    answers = {a["id"]: a for a in (yaml.safe_load((trabajo / "respuestas.yaml").read_text(encoding="utf-8")) or {}).get("respuestas", [])
               if str(a.get("respuesta") or "").strip()}
    for e in entries:
        a = answers.get(e["id"])
        if a:
            e.update({"vigente": str(a["respuesta"]).strip(), "estado": "confirmado", "confirmado_por": a.get("confirmado_por") or "cliente",
                      "fecha_confirmacion": str(a.get("fecha") or now_iso()[:10])})
    (trabajo / "registro.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    publish(entries, out, {"by": "okf confirm (respuestas del cliente)", "at": now_iso()})
    questions(entries, trabajo, sistema)
    return len(answers)
