"""Línea de comandos.

  okf build   --config config/mi-sistema.yaml [--pasos guias,vigencia] [--offline]
  okf confirm --config config/mi-sistema.yaml     aplica trabajo/<sistema>/respuestas.yaml y vuelve a publicar
  okf scan    --config config/mi-sistema.yaml     solo el escaneo de datos sensibles de las fuentes
  okf lint    <carpeta del repo OKF>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="okf")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="curación completa: fuentes → repo OKF")
    b.add_argument("--config", required=True)
    b.add_argument("--pasos", help="lista separada por comas (por defecto todos): guias,codigo,fichas,atlassian,integracion,vigencia")
    b.add_argument("--offline", action="store_true", help="sin modelos: solo extracción, conversión y publicación")
    for name, help_ in (("confirm", "aplica las respuestas del cliente"), ("scan", "escaneo de datos sensibles")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--config", required=True)
    lt = sub.add_parser("lint", help="comprueba un repo OKF")
    lt.add_argument("carpeta")
    a = ap.parse_args(argv)

    from . import config
    if a.cmd == "build":
        from .pipeline import run
        info = run(config.load(a.config), set(a.pasos.split(",")) if a.pasos else None, a.offline)
        print(json.dumps({k: v for k, v in info.items() if k != "lint"}, ensure_ascii=False, indent=1))
        if info["lint"]:
            print(f"\nlint: {len(info['lint'])} avisos (primeros 10):\n  " + "\n  ".join(info["lint"][:10]))
        return 0
    if a.cmd == "confirm":
        from .okfio import append_log, build_indexes, commit
        from .validity import apply_answers
        cfg = config.load(a.config)
        n = apply_answers(cfg.salida, cfg.trabajo, cfg.sistema)
        build_indexes(cfg.salida, cfg.sistema, cfg.modo)
        if n:
            append_log(cfg.salida, f"{n} valores confirmados por el cliente")
            commit(cfg.salida, f"Vigencia: {n} confirmaciones del cliente")
        print(f"{n} respuestas aplicadas; pendientes en {cfg.trabajo / 'confirmaciones.md'}")
        return 0
    if a.cmd == "scan":
        from .sources import scan_repo
        cfg = config.load(a.config)
        for r in cfg.repos:
            found = scan_repo(r)
            print(f"{r.name}: {len(found)} ficheros con avisos")
            for f, hits in found.items():
                print(f"  {f}: {', '.join(hits)}")
        return 0
    if a.cmd == "lint":
        from .okfio import lint
        problems = lint(Path(a.carpeta))
        print("\n".join(problems) or "sin avisos")
        return 1 if problems else 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
