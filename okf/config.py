"""Configuración de una curación (config/*.yaml). Ver config/sources.example.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

MODOS = ("agente", "busqueda")


@dataclass
class Repo:
    name: str
    path: Path
    include: list[str]
    docs: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    contexto: str = ""


@dataclass
class Config:
    sistema: str
    modo: str                                  # busqueda (retrieval desde Blob, por defecto) | agente
    salida: Path                               # carpeta del repo OKF que se genera
    trabajo: Path                              # registro de vigencia, preguntas al cliente, informes
    repos: list[Repo]
    exportar_codigo: bool = False              # caso A: el agente no clona, pero puede leer ficheros de la KB
    integraciones: list[tuple[str, str]] = field(default_factory=list)   # (consumidor, proveedor)
    jira: Path | None = None                   # export JSON de la REST API ({"issues": [...]})
    confluence: Path | None = None             # carpeta con pages.json + pages/<id>.xml (storage format)
    modelos: dict = field(default_factory=dict)

    def modelo(self, rol: str) -> str:
        return self.modelos.get(rol, DEFAULT_MODELS[rol])

    def detectores(self) -> list[str]:
        return self.modelos.get("detectores", DEFAULT_MODELS["detectores"])


DEFAULT_MODELS = {
    "redactor": "gpt-5.4-mini",                           # guías, índices, fichas: tareas acotadas y baratas
    "detectores": ["claude-sonnet-5-5", "gpt-5.5"],       # vigencia: dos modelos fuertes de familias distintas
    "fusion": "claude-sonnet-5-5",                        # une lo que encuentran los detectores
}


def load(path: str | Path) -> Config:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    base = path.parent
    rel = lambda p: (base / p).resolve() if p and not Path(p).is_absolute() else (Path(p) if p else None)
    modo = raw.get("modo", "busqueda")   # la arquitectura objetivo es retrieval desde Blob (Foundry IQ)
    if modo not in MODOS:
        raise SystemExit(f"modo debe ser uno de {MODOS}, no {modo!r}")
    repos = [Repo(name=r["name"], path=rel(r["path"]), include=r["include"], docs=r.get("docs", []),
                  exclude=r.get("exclude", []), contexto=r.get("contexto", "")) for r in raw.get("repos", [])]
    names = {r.name for r in repos}
    integ = [(i["consumidor"], i["proveedor"]) for i in raw.get("integraciones", [])]
    for c, p in integ:
        if c not in names or p not in names:
            raise SystemExit(f"integración {c} → {p}: los dos repos deben estar en `repos`")
    sistema = raw["sistema"]
    return Config(sistema=sistema, modo=modo, salida=rel(raw.get("salida", f"salida/okf-{sistema}")),
                  trabajo=rel(raw.get("trabajo", f"trabajo/{sistema}")), repos=repos, exportar_codigo=raw.get("exportar_codigo", False),
                  integraciones=integ, jira=rel(raw.get("jira")), confluence=rel(raw.get("confluence")), modelos=raw.get("modelos", {}))
