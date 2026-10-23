# Cómo curar un repo (y sus fuentes)

Procedimiento para preparar el conocimiento de un sistema (sus repos, su Jira y su Confluence) para que lo usen los agentes
de código. El porqué de cada decisión está en [METODOLOGIA.md](METODOLOGIA.md).

## 1. Decide cuánto hay que curar el repo

Depende de **cómo llega el conocimiento al agente**, no del repo. Es lo primero que hay que saber:

```
¿El agente puede clonar el repo?
├── Sí ─────────────────────────────────────────────► CASO 1 · Repo accesible
└── No → ¿Puede leer ficheros de la base de conocimiento
         (abrir un documento entero, listar, buscar texto)?
         ├── Sí ────────────────────────────────────► CASO 2 · Código dentro de la KB
         └── No, solo recibe trozos de un buscador ─► CASO 3 · Hay que curar el repo (digest)
```

| | Caso 1 · Repo accesible | Caso 2 · Código dentro de la KB | Caso 3 · Curar el repo (digest) |
|---|---|---|---|
| **Cuándo** | El agente clona el repo | No puede clonar, pero lee ficheros de la KB | Solo recibe trozos de un buscador (Foundry IQ sin lectura de ficheros) |
| **Qué se publica del repo** | Solo la guía | Guía + el código tal cual (sin resumir) | Guía + **digest**: una ficha por componente, flujos, restricciones y trampas, catálogos |
| **Configuración** | `modo: agente` | `modo: agente`, `exportar_codigo: true` | `modo: busqueda` |
| **Entre repos** | Índice de integración | Índice de integración | Índice + una ficha por integración |
| **Resultado en el piloto** | 74–81 % | Igual que el caso 1: para el agente es lo mismo leer el código del repo que de la KB | 60–72 % en uso, **como mucho 42 % en preguntas de sistema** |

**Repos pequeños** (menos de unos 200.000 caracteres de código): en el caso 3, el código tal cual con la guía rindió igual
que el digest. Puedes usar `exportar_codigo: true` aunque el modo sea `busqueda`.

**Si estás en el caso 3, intenta pasar al 2.** El techo de las preguntas de sistema no lo arregla ninguna curación: el
buscador no junta información repartida entre ficheros. Que el agente pueda abrir un documento entero lo cambia todo.

## 2. Qué se genera siempre, sea cual sea el caso

| Pieza | Qué es | Quién la hace |
|---|---|---|
| Guía por repo | Para qué sirve el repo, qué expone, arquitectura, dónde está cada cosa, configuración, cómo se despliega y trampas | Modelo barato (skill `repo-guide`) |
| Jira y Confluence | Convertidos a Markdown **sin resumir** (comentarios, fechas, estados y enlaces incluidos) | Sin modelo |
| Índice entre repos | Qué componente de un repo atiende cada llamada de otro | Modelo barato (skill `integration-index`) |
| Registro de vigencia | Cada valor o regla con su historia entre fuentes, clasificado como consistente, cambio o contradicción | Dos modelos fuertes (skill `validity-register`) |
| Preguntas al cliente | Una por contradicción, cerrada y con evidencias | Se genera sola; responde el experto del cliente (skill `client-confirmation`) |

## 3. El procedimiento

| Paso | Qué haces | Comando | Tiempo |
|---|---|---|---|
| 1. Exportar | Foto de cada repo (rama principal), export de Jira (JSON de la REST API) y de Confluence (espacio en XML), una sola vez | — | Lo que tarden los permisos |
| 2. Configurar | Copia `config/sources.example.yaml` a `config/local-<sistema>.yaml`: repos con sus patrones `include`, `docs` y `exclude`, integraciones, exports, y el modo según el punto 1 | — | 15–30 min |
| 3. Escanear | Revisa los posibles datos sensibles. Se redactan solos, pero excluye los ficheros de credenciales o configuración privada | `okf scan --config …` | Minutos |
| 4. Curar | Ejecuta la curación completa | `okf build --config …` | 5–15 min por sistema |
| 5. Revisar | Lee por encima cada guía: que las rutas existan y que no falte ningún punto de entrada importante. Revisa `trabajo/<sistema>/informe.json` (lint, volumen y uso de modelos) | — | 15–30 min por repo |
| 6. Preguntar | Envía `trabajo/<sistema>/confirmaciones.md` al experto del cliente. Si son muchas, prioriza las que afectan a lo que va a construir la factory | — | Unos 2 min por pregunta (del experto) |
| 7. Aplicar | Copia las respuestas en `respuestas.yaml` y vuelve a publicar | `okf confirm --config …` | Minutos |
| 8. Publicar | Sube el repo OKF (`salida`) a su repositorio. CI/CD lo sincroniza a Blob, de ahí a AI Search y a Foundry IQ | `git push` | Minutos |

Puedes publicar antes de tener las respuestas del cliente: las contradicciones sin confirmar salen como `draft`, con los dos
valores y un aviso.

## 4. Cuándo repetir

- **Cambio importante en un repo** (componentes nuevos, otra arquitectura): `okf build --pasos guias,integracion`, o la
  curación completa en el caso 3.
- **Nuevo export de Jira o Confluence**: `okf build --pasos atlassian,vigencia`, y vuelve a preguntar al cliente lo nuevo.
- **Para medir si una curación sirve con fuentes reales**: `eval/bench.py` genera preguntas verificadas a partir del código y
  mide al agente. `eval/recall_vigencia.py` comprueba cuántas contradicciones conocidas detecta el registro.
