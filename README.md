# okf-curation

Convierte repos de código, Jira y Confluence en un **repo OKF** (Markdown + YAML, Open Knowledge Format v0.2) para
que agentes de código entiendan los sistemas que van a usar o integrar.

Hace solo lo que demostró aportar en el piloto (ver [METODOLOGIA.md](METODOLOGIA.md)):

| Pieza | Qué es | Cómo |
|---|---|---|
| **Guía por repo** | Para qué sirve, qué expone, arquitectura, dónde está cada cosa | LLM barato |
| **Jira y Confluence** | Convertidos a Markdown **sin resumir** | Sin LLM |
| **Índice de integración** | Qué componente de un repo atiende cada llamada de otro | LLM barato |
| **Registro de vigencia** | Cada valor o regla con su historia entre fuentes; las **contradicciones se preguntan al cliente** | 2 modelos fuertes + el cliente |
| *Modo búsqueda* | Si el agente no puede leer el código: además, el **digest** del repo (ficha por componente, flujos, restricciones y catálogos) | LLM barato |

**¿Hay que curar el repo o basta con la guía?** Depende de si el agente puede leer el código: ver el árbol de decisión y el
procedimiento paso a paso en [CURAR-UN-REPO.md](CURAR-UN-REPO.md).

## Uso

```bash
uv sync
cp config/sources.example.yaml config/local-mi-sistema.yaml     # ajusta rutas y modo
export OKF_ENV_FILE=~/.okf.env                                   # OPENAI_API_KEY=… y ANTHROPIC_API_KEY=… (o variables de entorno)

uv run okf scan  --config config/local-mi-sistema.yaml           # 1. revisa datos sensibles en las fuentes
uv run okf build --config config/local-mi-sistema.yaml           # 2. curación completa → repo OKF en `salida`
#    → envía trabajo/<sistema>/confirmaciones.md al experto del cliente; contesta en respuestas.yaml
uv run okf confirm --config config/local-mi-sistema.yaml         # 3. aplica sus respuestas y vuelve a publicar
```

- `okf build --pasos vigencia`: rehace un solo paso (`guias`, `codigo`, `fichas`, `atlassian`, `integracion`, `vigencia`).
- `okf build --offline`: sin modelos ni claves (extracción, conversión y publicación). Sirve de prueba rápida.
- `okf lint <carpeta>`: comprueba un repo OKF (frontmatter, H1, enlaces, datos sensibles).

**Prueba con el ejemplo sintético** (dos repos, Jira y Confluence con una contradicción plantada):

```bash
uv run okf build --config examples/demo/sources.yaml            # modo agente
cat trabajo/demo-reclamaciones/confirmaciones.md                 # la pregunta al cliente por AUTO_APPROVE_LIMIT
uv run okf build --config examples/demo/sources-busqueda.yaml   # modo búsqueda: añade fichas por componente y de integración
```

## Qué produce

```
okf-<sistema>/                      repo git; súbelo a su propio repositorio y de ahí a Blob → AI Search
├── index.md                        okf_version 0.2
├── repos/<repo>/guia.md            guía de navegación de cada repo
│   ├── codigo/…                    solo si exportar_codigo: true (el agente no clona pero lee ficheros)
│   └── componentes/ flujos/ restricciones-trampas.md catalogos/     solo en modo búsqueda (digest)
├── integracion/<consumidor>--<proveedor>.md
├── jira/<KEY>.md · confluence/<id>.md
├── vigencia/<id>-<tema>.md         stable si es consistente, cambio documentado o confirmado; draft si espera al cliente
├── vigencia/pendientes.md
└── log.md
trabajo/<sistema>/                  fuera del repo OKF
├── confirmaciones.md · respuestas.yaml    preguntas al cliente y sus respuestas
├── registro.json · detecciones.json       registro de vigencia y lo que vio cada detector
└── escaneo-fuentes.json · informe.json
```

## Estructura del repo

```
okf/        el pipeline (config, sources, extract, convert, guides, integration, validity, cards, okfio, pipeline, cli)
skills/     los prompts, en formato SKILL.md: okf-format, repo-guide, integration-index, validity-register,
            client-confirmation y, para el modo búsqueda, repo-digest y component-card. Un agente puede usarlas tal cual.
eval/       banco de pruebas: generar preguntas verificadas y medir agente o búsqueda sobre una KB (eval/bench.py)
examples/   ejemplo sintético
config/     sources.example.yaml
```

## Medir un cambio

```bash
uv run python eval/bench.py preguntas --config C --repo R --tipo componente --n 30 --salida eval/preguntas/r.yaml
uv run python eval/bench.py agente   --config C --preguntas eval/preguntas/r.yaml --codigo --guias --kb
uv run python eval/bench.py busqueda --config C --preguntas eval/preguntas/r.yaml
```
Con 15–35 preguntas, menos de 10 puntos de diferencia es empate, y el agente varía ±7–14 puntos entre ejecuciones: repite antes de concluir.
