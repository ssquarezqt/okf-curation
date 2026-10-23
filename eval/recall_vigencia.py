"""¿Cuántas contradicciones conocidas detecta el registro de vigencia? Uno frente a dos detectores.

Si el detector no ve una contradicción, nadie pregunta al cliente por ella y se publica un valor equivocado. Este script
compara una lista de conflictos conocidos con lo que encontró cada detector (trabajo/<sistema>/detecciones.json) y con el
registro fusionado (registro.json). Un modelo (Claude Sonnet) decide si alguna entrada cubre cada conflicto.

Conflictos conocidos (YAML): {"questions": [{"id", "detalle": {"topic", "jira", "confluence", "vigente"}}]} o
{"conflictos": [{"id", "tema", "descripcion"}]}.

Uso:  uv run python eval/recall_vigencia.py --config C --conocidos conflictos.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from okf import config as C  # noqa: E402
from okf import llm  # noqa: E402

SYS = ("Decides si un registro de valores vigentes cubre un conflicto conocido entre fuentes. Lo cubre si alguna entrada trata el MISMO "
       "valor o regla y recoge que cambió o que las fuentes no coinciden (clase cambio o contradiccion). "
       'Devuelve SOLO JSON {"cubierto": true|false, "entrada": "tema de la entrada que lo cubre o null", "clase": "clase de esa entrada o null"}.')


def known(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if "conflictos" in data:
        return data["conflictos"]
    return [{"id": q["id"], "tema": q["detalle"]["topic"], "descripcion": f"Jira: {q['detalle']['jira']} · Confluence: {q['detalle']['confluence']}"}
            for q in data["questions"]]


def coverage(conflicts: list[dict], entries: list[dict]) -> list[dict]:
    reg = json.dumps([{k: e.get(k) for k in ("tema", "clase", "vigente")} for e in entries], ensure_ascii=False)

    def one(c):
        v = llm.json_call("claude-sonnet-5-5", SYS, f"CONFLICTO: {c['tema']} — {c['descripcion']}\n\nREGISTRO:\n{reg}", max_tokens=4000)
        return {"id": c["id"], "tema": c["tema"], **v}

    with ThreadPoolExecutor(6) as pool:
        return list(pool.map(one, conflicts))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--conocidos", required=True)
    a = ap.parse_args()
    cfg = C.load(a.config)
    conflicts = known(Path(a.conocidos))
    found = json.loads((cfg.trabajo / "detecciones.json").read_text(encoding="utf-8"))
    sets = {**{f"solo {m}": es for m, es in found.items()}, "fusionado": json.loads((cfg.trabajo / "registro.json").read_text(encoding="utf-8"))}
    report = {}
    for name, entries in sets.items():
        rows = coverage(conflicts, entries)
        ok = [r for r in rows if r.get("cubierto")]
        contra = [r for r in ok if r.get("clase") == "contradiccion"]
        report[name] = {"entradas": len(entries), "cubiertos": len(ok), "como_contradiccion": len(contra), "de": len(conflicts), "detalle": rows}
        print(f"{name:<28} {len(entries):>3} entradas · cubre {len(ok)}/{len(conflicts)} conflictos conocidos "
              f"({len(contra)} como contradicción → pregunta al cliente) · se le escapan: {[r['id'] for r in rows if not r.get('cubierto')]}")
    out = Path(__file__).resolve().parent / "resultados" / f"recall-vigencia-{cfg.sistema}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
