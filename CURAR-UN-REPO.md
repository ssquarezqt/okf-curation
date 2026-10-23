# Cómo curar un repo (y sus fuentes)

Procedimiento para preparar el conocimiento de un sistema (sus repos, su Jira y su Confluence) para que lo usen los agentes
de código. El porqué de cada decisión está en [METODOLOGIA.md](METODOLOGIA.md).

## 1. Qué se genera de cada repo

**Por defecto (la arquitectura objetivo: retrieval desde Blob con Foundry IQ):** el agente recibe trozos de un buscador y no
ve el código, así que **el repo se cura**. Se publica la guía, la documentación del repo tal cual, el **digest** (una ficha por
componente, flujos, restricciones y trampas) y los **catálogos** (componentes y dependencias, variables, tablas, comandos).
Configuración: `modo: busqueda` (por defecto). El detalle de qué contenido es clave y cuánto se destila está en
[METODOLOGIA.md](METODOLOGIA.md), sección 4.

**Alternativas, si la arquitectura lo permite:**

| | Por defecto · retrieval | Alternativa · el agente lee ficheros de la KB | Alternativa · el agente clona el repo |
|---|---|---|---|
| **Qué se publica del repo** | Guía + docs + digest + catálogos | Guía + el código tal cual | Solo la guía |
| **Configuración** | `modo: busqueda` | `modo: agente`, `exportar_codigo: true` | `modo: agente` |
| **Entre repos** | Índice + una ficha por llamada | Índice | Índice |
| **Resultado en el piloto** | 60–72 % en uso; **como mucho 42 % en preguntas de sistema** (repo C) | 74–81 % | 74–81 % |

**Repos pequeños**: en el repo pequeño probado (~190.000 caracteres), el código tal cual con la guía rindió igual que el digest (un solo caso; el umbral es orientativo).
Puedes usar `exportar_codigo: true` también en modo `busqueda`.

**El techo del retrieval** en preguntas de sistema (respuestas repartidas entre ficheros) no lo arregla ninguna curación. Si
Foundry IQ o el agente hospedado pueden abrir documentos enteros, la alternativa central sube al 74–81 %. Compruébalo en el spike de Azure.

## 2. Qué se genera siempre, sea cual sea el caso

| Pieza | Qué es | Quién la hace |
|---|---|---|
| Guía por repo | Para qué sirve el repo, qué expone, arquitectura, dónde está cada cosa, configuración, cómo se despliega y trampas | Modelo barato (skill `repo-guide`) |
| Jira y Confluence | Convertidos a Markdown **sin resumir** (comentarios, fechas, estados y enlaces incluidos) | Sin modelo |
| Índice entre repos | Qué componente de un repo atiende cada llamada de otro | Modelo barato (skill `integration-index`) |
| Registro de vigencia | Cada valor o regla con su historia entre fuentes, clasificado como consistente, cambio o contradicción | Modelos fuertes (skill `validity-register`); dos por precaución, aunque en el piloto uno solo detectó 7/7 |
| Preguntas al cliente | Una por contradicción, cerrada y con evidencias | Se genera sola; responde el experto del cliente (skill `client-confirmation`) |

## 3. El procedimiento

| Paso | Qué haces | Comando | Tiempo |
|---|---|---|---|
| 1. Exportar | Foto de cada repo (rama principal), export de Jira (JSON de la REST API) y de Confluence (espacio en XML), una sola vez | — | Lo que tarden los permisos |
| 2. Configurar | Copia `config/sources.example.yaml` a `config/local-<sistema>.yaml`: repos con sus patrones `include`, `docs` y `exclude`, integraciones, exports, y el modo según el punto 1 | — | 15–30 min (estimado) |
| 3. Escanear | Revisa los posibles datos sensibles. Se redactan solos, pero excluye los ficheros de credenciales o configuración privada | `okf scan --config …` | Minutos |
| 4. Curar | Ejecuta la curación completa | `okf build --config …` | 1–17 min por sistema (medido) |
| 5. Revisar | Lee por encima cada guía: que las rutas existan y que no falte ningún punto de entrada importante. Revisa `trabajo/<sistema>/informe.json` (lint, volumen y uso de modelos) | — | 15–30 min por repo (estimado) |
| 6. Preguntar | Envía `trabajo/<sistema>/confirmaciones.md` al experto del cliente. Si son muchas, prioriza las que afectan a lo que va a construir la factory | — | Unos 2 min por pregunta del experto (estimado) |
| 7. Aplicar | Copia las respuestas en `respuestas.yaml` y vuelve a publicar | `okf confirm --config …` | Minutos |
| 8. Publicar | Sube el repo OKF (`salida`) a su repositorio. CI/CD lo sincroniza a Blob, de ahí a AI Search y a Foundry IQ | `git push` | Minutos |

Puedes publicar antes de tener las respuestas del cliente: las contradicciones sin confirmar salen como `draft`, con los dos
valores y un aviso.

## 4. Cuándo repetir

- **Cambio importante en un repo** (componentes nuevos, otra arquitectura): `okf build --pasos guias,integracion`, o la
  curación completa en modo `busqueda`.
- **Nuevo export de Jira o Confluence**: `okf build --pasos atlassian,vigencia`, y vuelve a preguntar al cliente lo nuevo.
- **Para medir si una curación sirve con fuentes reales**: `eval/bench.py` genera preguntas verificadas a partir del código y
  mide al agente. `eval/recall_vigencia.py` comprueba cuántas contradicciones conocidas detecta el registro.
