"""Banco de pruebas: mide si una base de conocimiento sirve a un agente de código.

Preguntas (YAML: {"questions": [{"id", "question", "answer", ...}]}):
  preguntas   genera preguntas sobre un repo leyendo su código (Claude Haiku) y las verifica contra el código (Claude Sonnet):
                --tipo componente   contrato de cada componente (entradas, errores, variables, datos)
                --tipo sistema      flujos, roles y relaciones que exigen juntar varios ficheros
Medida (responde gpt-5.4-mini; juzga Claude Haiku: 2 correcta, 1 parcial, 0 incorrecta o "no lo sé"):
  agente      el agente explora con list_files / grep / read_file sobre un corpus:
                --kb       el repo OKF generado (guías, Jira, Confluence, vigencia, índices…)
                --codigo   el código de los repos de la configuración (= tenerlos clonados)
                --guias    mete las guías de la KB en el prompt (tipo AGENTS.md)
  busqueda    búsqueda de 5 trozos de 2.000 caracteres sobre la KB (BM25 + embeddings, RRF), como Foundry IQ sin agente

Uso:
  uv run python eval/bench.py preguntas --config C --repo R --tipo componente --n 30 --salida eval/preguntas/r-comp.yaml
  uv run python eval/bench.py agente    --config C --preguntas P.yaml --codigo --guias [--kb] [--etiqueta x]
  uv run python eval/bench.py busqueda  --config C --preguntas P.yaml
Con 15–35 preguntas, diferencias de menos de 10 puntos son empate; el agente varía ±7–14 entre ejecuciones: repite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from okf import config as C  # noqa: E402
from okf import extract, llm  # noqa: E402
from okf.okfio import split  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "resultados"
ANSWER, JUDGE, GEN, VERIFY = "gpt-5.4-mini", "claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001", "claude-sonnet-5-5"


# ------------------------------------------------------------------ preguntas

GEN_SYS = {
    "componente": ("Escribes preguntas de prueba para medir si una base de conocimiento sirve a un agente de código que va a USAR o INTEGRAR "
                   "este repo sin ver el código: qué hace un componente, cómo se invoca, qué recibe y devuelve, qué errores da, qué variables "
                   "o datos usa, reglas al usarlo. Nada de operación, historia ni rendimiento. Vocabulario del código."),
    "sistema": ("Escribes preguntas de prueba de NIVEL SISTEMA para un agente de código que va a integrar este repo sin ver el código: flujos "
                "de punta a punta, roles y permisos, qué componente llama a qué, reglas que cruzan varios ficheros. Cada respuesta debe "
                "requerir juntar al menos dos ficheros. Vocabulario del código."),
}


def gen_questions(cfg, repo: str, tipo: str, n: int) -> list[dict]:
    fx = extract.build(next(r for r in cfg.repos if r.name == repo))
    code = [r for r, f in fx["files"].items() if f["kind"] in {"code", "script"}]
    if tipo == "sistema":
        hubs = sorted(code, key=lambda r: -len(fx["files"][r].get("used_by", [])))[:12]
        batches = [hubs, hubs[::-1]]
    else:
        batches = [code[i:i + 6] for i in range(0, len(code), 6)]
    per = max(2, -(-n * 2 // len(batches)))   # genera el doble y la verificación descarta

    def one(files):
        src = "\n\n".join(f"### `{r}`\n```\n{fx['texts'][r][:14000]}\n```" for r in files)[:70000]
        inv = f"INVENTARIO:\n{extract.inventory(fx, {'code', 'script'})}\n\n" if tipo == "sistema" else ""
        data = llm.json_call(GEN, GEN_SYS[tipo] + ' Devuelve SOLO JSON {"questions": [{"question": "...", "answer": "respuesta concreta y verificable"}]}.',
                             f"Repo {repo}. Escribe {per} preguntas.\n\n{inv}{src}", max_tokens=8000)
        return [dict(q, material=src) for q in data.get("questions", [])]

    with ThreadPoolExecutor(6) as pool:
        qs = [q for lst in pool.map(one, batches) for q in lst]
    sys_v = ("Verificas una pregunta de prueba contra el código real. Es válida solo si el código permite UNA respuesta inequívoca. Corrige la "
             'respuesta si algo no coincide. Devuelve SOLO JSON {"valid": true|false, "corrected_answer": "...", "why": "breve"}.')
    with ThreadPoolExecutor(6) as pool:
        verdicts = list(pool.map(lambda q: llm.json_call(VERIFY, sys_v, f"CÓDIGO:\n{q['material']}\n\nPREGUNTA: {q['question']}\n"
                                                                        f"RESPUESTA PROPUESTA: {q['answer']}", max_tokens=6000), qs))
    valid = [{"question": q["question"], "answer": v.get("corrected_answer") or q["answer"]} for q, v in zip(qs, verdicts) if v.get("valid")][:n]
    return [{"id": f"{tipo[0]}{i:02d}", **q} for i, q in enumerate(valid, 1)]


# ------------------------------------------------------------------ juez

JUDGE_SYS = ("Evalúas respuestas contra una respuesta de referencia. Devuelve SOLO JSON {\"score\": 0|1|2, \"why\": \"...\"}. "
             "2 = correcta y sin errores relevantes; 1 = parcialmente correcta o incompleta; 0 = incorrecta, inventada o 'no lo sé'.")


def judge(q: dict, answer: str) -> int:
    out = llm.text(JUDGE, JUDGE_SYS, f"Pregunta: {q['question']}\nReferencia: {q['answer']}\nRespuesta: {answer}", max_tokens=800)
    m = re.search(r'"score"\s*:\s*([012])', out)
    return int(m.group(1)) if m else 0


# ------------------------------------------------------------------ agente

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "Lista las rutas (con tamaño) que empiezan por un prefijo.",
     "parameters": {"type": "object", "properties": {"prefix": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "grep", "description": "Busca una expresión regular (sin distinguir mayúsculas) en los ficheros.",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path_prefix": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Lee líneas de un fichero (1-based, máx. 300).",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["path"]}}},
]
MAX_STEPS = 12


def _resolve(path: str, texts: dict[str, str]) -> str:
    """Las guías citan rutas relativas al repo (`src/…`) y el corpus las lleva con su carpeta (`<repo>/src/…`): un agente
    que tiene el repo clonado entra en su carpeta, así que una ruta relativa que solo existe en un repo se resuelve sola."""
    path = path.lstrip("./")
    if path in texts:
        return path
    hits = [k for k in texts if k.endswith("/" + path)]
    return hits[0] if len(hits) == 1 else path


def _prefix(pre: str, texts: dict[str, str]) -> list[str]:
    pre = pre.lstrip("./")
    keys = [k for k in texts if k.startswith(pre)]
    return keys or [k for k in texts if "/" in k and k.split("/", 1)[1].startswith(pre)]


def tool(name: str, a: dict, texts: dict[str, str]) -> str:
    if name == "list_files":
        return "\n".join(f"{r} ({len(texts[r])} c)" for r in _prefix(a.get("prefix") or "", texts))[:8000] or "Sin ficheros."
    if name == "read_file":
        t = texts.get(_resolve(a.get("path", ""), texts))
        if t is None:
            return "No existe ese fichero."
        lines = t.splitlines()
        s = max(1, int(a.get("start") or 1))
        e = min(len(lines), int(a.get("end") or s + 299), s + 299)
        return "\n".join(f"{i}: {lines[i - 1]}" for i in range(s, e + 1)) + (f"\n... ({len(lines)} líneas)" if e < len(lines) else "")
    if name == "grep":
        try:
            rx = re.compile(a.get("pattern", ""), re.I)
        except re.error:
            return "Expresión regular no válida."
        scope = set(_prefix(a.get("path_prefix") or "", texts))
        hits = [f"{r}:{i}: {line.strip()[:200]}" for r, t in texts.items() if r in scope
                for i, line in enumerate(t.splitlines(), 1) if rx.search(line)]
        return "\n".join(hits[:60]) + ("\n... (más coincidencias)" if len(hits) > 60 else "") if hits else "Sin coincidencias."
    return "Herramienta desconocida."


def agent_answer(question: str, texts: dict, what: str) -> dict:
    client = llm._client("openai")
    msgs = [{"role": "system", "content": f"Eres un agente de código que va a usar o integrar estos sistemas. {what} Investiga con las "
             f"herramientas antes de responder (máximo {MAX_STEPS} pasos). Responde en español, breve y concreto, con los nombres exactos. "
             "Si no lo encuentras, di 'No lo sé con lo que he encontrado.'"}, {"role": "user", "content": question}]
    tok, t0 = 0, time.time()
    for step in range(MAX_STEPS):
        for attempt in range(4):   # errores transitorios
            try:
                r = client.chat.completions.create(model=ANSWER, messages=msgs, tools=TOOLS, tool_choice="auto" if step < MAX_STEPS - 1 else "none")
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        tok += r.usage.prompt_tokens
        m = r.choices[0].message
        if not m.tool_calls:
            break
        msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [tc.model_dump() for tc in m.tool_calls]})
        for tc in m.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": tool(tc.function.name, args, texts)[:12000]})
    return {"answer": (m.content or "").strip(), "steps": step + 1, "input_tokens": tok, "seconds": round(time.time() - t0, 1)}


def kb_texts(cfg) -> dict[str, str]:
    return {f"kb/{p.relative_to(cfg.salida).as_posix()}": p.read_text(encoding="utf-8") for p in sorted(cfg.salida.rglob("*.md")) if ".git" not in p.parts}


def code_texts(cfg) -> dict[str, str]:
    texts = {}
    for r in cfg.repos:
        texts.update({f"{r.name}/{k}": v for k, v in extract.build(r)["texts"].items()})
    return texts


def guides(cfg) -> str:
    out = []
    for p in sorted((cfg.salida / "repos").glob("*/guia.md")):
        out.append(f"===== Guía de {p.parent.name} =====\n{split(p.read_text(encoding='utf-8'))[1]}")
    for p in sorted((cfg.salida / "integracion").glob("*.md")):
        if p.name != "index.md":
            out.append(f"===== {p.stem} =====\n{split(p.read_text(encoding='utf-8'))[1]}")
    return "\n\n".join(out)


def run_agent(cfg, qs: list[dict], use_kb: bool, use_code: bool, use_guides: bool) -> list[dict]:
    texts = {**(kb_texts(cfg) if use_kb else {}), **(code_texts(cfg) if use_code else {})}
    what = ("Tienes " + " y ".join(x for x in ("los repos clonados (carpetas por repo)" if use_code else "",
                                               "la base de conocimiento del equipo en `kb/` (guías, índices de integración, Jira, Confluence y "
                                               "`kb/vigencia/`: valores vigentes cuando las fuentes no coinciden)" if use_kb else "") if x) + ".")
    if use_guides:
        what += f"\n\nGUÍAS DE LOS REPOS (tipo AGENTS.md):\n{guides(cfg)}\n"

    def one(q):
        row = {"id": q["id"], **agent_answer(q["question"], texts, what)}
        row["score"] = judge(q, row["answer"])
        return row

    with ThreadPoolExecutor(8) as pool:
        return list(pool.map(one, qs))


# ------------------------------------------------------------------ búsqueda (simula Foundry IQ sin agente)

def _chunks(texts: dict) -> list[str]:
    out = []
    for t in texts.values():
        out += [t[i:i + 2000] for i in range(0, len(t), 1800)]
    return out


def _embed(texts: list[str]) -> np.ndarray:
    cache = RESULTS / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    keys = [hashlib.sha256(("text-embedding-3-large" + t).encode()).hexdigest() for t in texts]
    missing = [(k, t) for k, t in zip(keys, texts) if not (cache / f"{k}.json").exists()]
    for b in range(0, len(missing), 64):
        batch = missing[b:b + 64]
        resp = llm._client("openai").embeddings.create(model="text-embedding-3-large", input=[t[:24000] for _, t in batch])
        for (k, _), d in zip(batch, resp.data):
            (cache / f"{k}.json").write_text(json.dumps(d.embedding))
    m = np.array([json.loads((cache / f"{k}.json").read_text()) for k in keys], dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def run_search(cfg, qs: list[dict]) -> list[dict]:
    from rank_bm25 import BM25Okapi
    chunks = _chunks(kb_texts(cfg))
    tok = lambda s: re.findall(r"\w[\w.\-]*", s.lower())
    bm25, mat, qmat = BM25Okapi([tok(c) for c in chunks]), _embed(chunks), _embed([q["question"] for q in qs])

    def one(i):
        q = qs[i]
        score = {}
        for order in (np.argsort(-bm25.get_scores(tok(q["question"]))), np.argsort(-(mat @ qmat[i]))):
            for rank, idx in enumerate(order):
                score[int(idx)] = score.get(int(idx), 0) + 1 / (61 + rank)
        top = sorted(score, key=lambda k: -score[k])[:5]
        ans = llm.text(ANSWER, "Respondes usando SOLO los fragmentos dados. Si no bastan, di 'No lo sé con estos fragmentos.' En español, breve.",
                       "Fragmentos:\n" + "\n\n---\n\n".join(chunks[k] for k in top) + f"\n\nPregunta: {q['question']}")
        return {"id": q["id"], "answer": ans, "score": judge(q, ans)}

    with ThreadPoolExecutor(8) as pool:
        return list(pool.map(one, range(len(qs))))


# ------------------------------------------------------------------ main

def summary(rows: list[dict]) -> str:
    n = len(rows)
    s = f"{sum(r['score'] for r in rows) / (2 * n):.0%} ({n} preguntas)"
    if rows and "steps" in rows[0]:
        s += f" · {sum(r['steps'] for r in rows) / n:.1f} pasos · {sum(r['input_tokens'] for r in rows) / n:,.0f} tokens/pregunta"
    return s


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["preguntas", "agente", "busqueda"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--repo")
    ap.add_argument("--tipo", choices=list(GEN_SYS), default="componente")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--salida")
    ap.add_argument("--preguntas")
    ap.add_argument("--kb", action="store_true")
    ap.add_argument("--codigo", action="store_true")
    ap.add_argument("--guias", action="store_true")
    ap.add_argument("--etiqueta", default="")
    a = ap.parse_args()
    cfg = C.load(a.config)
    if a.cmd == "preguntas":
        qs = gen_questions(cfg, a.repo, a.tipo, a.n)
        out = Path(a.salida or RESULTS / f"preguntas-{cfg.sistema}-{a.repo}-{a.tipo}.yaml")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml.safe_dump({"origen": f"bench.py {a.tipo} (Haiku genera, Sonnet verifica)", "questions": qs}, allow_unicode=True,
                                      sort_keys=False, width=200), encoding="utf-8")
        print(f"{len(qs)} preguntas verificadas → {out}")
        return
    qs = yaml.safe_load(Path(a.preguntas).read_text(encoding="utf-8"))["questions"]
    if a.cmd == "agente":
        rows = run_agent(cfg, qs, a.kb, a.codigo, a.guias)
        label = "agente-" + "+".join(x for x, on in (("kb", a.kb), ("codigo", a.codigo), ("guias", a.guias)) if on)
    else:
        rows = run_search(cfg, qs)
        label = "busqueda-kb"
    RESULTS.mkdir(parents=True, exist_ok=True)
    qname = f"{Path(a.preguntas).parent.name}-{Path(a.preguntas).stem}"   # carpeta + nombre: dos golden.yaml no se pisan
    out = RESULTS / f"{cfg.sistema}-{qname}-{label}{a.etiqueta}.json"
    out.write_text(json.dumps({"summary": summary(rows), "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{label:<28} {qname:<36} {summary(rows)}")


if __name__ == "__main__":
    main()
