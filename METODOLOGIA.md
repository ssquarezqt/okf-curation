# Metodología de curación (v1)

Cómo convertir repos, Jira y Confluence en el conocimiento que usa un agente de código, y la evidencia de cada decisión.
Sale de un piloto local con preguntas de prueba, en el que se compararon 10 enfoques. Los datos del piloto no están
en este repo.

## El principio

> **Se cura lo que el agente no puede deducir leyendo: cómo moverse por las fuentes y qué es verdad hoy cuando las fuentes
> no coinciden. No se resume lo que el agente puede leer por sí mismo.**

En el piloto, los resúmenes empataron con la fuente original o la empeoraron: el agente se fía del resumen y deja de
mirar la fuente. Las piezas que sí movieron el resultado fueron la **guía** de cada repo y el **registro de vigencia**.

## Cómo se midió

- **Fuentes:**
  - repo A: backend Python grande, 57 Lambdas, ~1,2 M caracteres;
  - repo B: backend Python pequeño, ~190.000 caracteres, solo README;
  - repo C: frontend React + TypeScript, ~570.000 caracteres, consumidor de A;
  - Jira (84 issues, y 686 en la prueba a escala) y Confluence (14 páginas), simulados a partir de A, con trampas:
    reglas que cambian, duplicados, causas en comentarios, páginas obsoletas y actas mezcladas.
- **Preguntas con respuesta conocida, verificadas contra la fuente por un modelo fuerte:**
  - uso de componentes (contratos, errores, variables);
  - sistema (respuestas repartidas entre varios ficheros);
  - entre repos (frontend ↔ backend);
  - conflictos entre fuentes.
- **Respuesta:** gpt-5.4-mini. **Juez:** Claude Haiku, que puntúa 2 (correcta), 1 (parcial) o 0 (incorrecta o "no lo sé").
- **Dos formas de entregar el conocimiento al agente:**
  - **búsqueda**: 5 trozos de 2.000 caracteres por pregunta, BM25 + embeddings, como Foundry IQ sin agente;
  - **agente**: explora con `list_files`, `grep` y `read_file`, hasta 12 pasos.
- **Ruido:** menos de 10 puntos de diferencia es empate. El agente varía ±7–14 puntos entre ejecuciones, así que lo importante se repitió.

## Qué se probó y qué resultó

| # | Enfoque | Resultado | Decisión |
|---|---|---|---|
| 1 | Organizar el digest de un repo con un planificador libre: por grafo, por preguntas o por entidades | 35–58 %, sin ganador, muy inestable entre ejecuciones (8–24 puntos) | Descartado |
| 2 | Redactar con prompt frente a agente con herramientas | Empate | Descartado (da igual) |
| 3 | Plantilla temática fija | Estable, sin mejora | Descartado |
| 4 | **Una ficha por componente, contrato primero** | Con búsqueda: 60–67 % frente a 43–52 %; estable | **Solo en modo búsqueda** |
| 5 | Herramienta de mercado (CodeWiki) tal cual | 16 % | Descartado |
| 6 | **Repo clonado + guía corta frente a digest** | Repo + guía: 74–81 %, el mejor en los 3 repos. Sin guía: entre 6 y 31 puntos menos | **Pieza central** |
| 7 | Jira: un documento por ticket, por épica o por funcionalidad | Ninguno gana al export convertido (58 % con búsqueda, 71 % con agente), ni con 686 tickets | **Convertir sin resumir** |
| 8 | Confluence: trocear, plantilla o proposiciones | Ninguno gana al export convertido; reescribir le quita información al agente (96 % → 78 %) | **Convertir sin resumir** |
| 9 | Mapa entre repos (fichas de contrato) | Búsqueda: +12–21 puntos. Agente con código: −15–23 (deja de leer el código). Solo índice: neutro | **Índice**; fichas solo en modo búsqueda |
| 10 | **Registro de vigencia entre fuentes** | Sin él, el agente acierta el 14–36 % de los conflictos (7 % si cada fuente se cura por separado). Con él, **68–82 %**, confirmado con dos modelos distintos | **Pieza central** |

## La metodología

### Dos modos de entrega (decisión de arquitectura)

| | **Modo agente** (recomendado) | **Modo búsqueda** |
|---|---|---|
| Cuándo | El agente puede explorar: clona los repos o lee ficheros de la KB con herramientas | El agente solo recibe trozos de un buscador |
| Repos | Guía + acceso al código. Si no puede clonar pero sí leer ficheros de la KB: el código tal cual en la KB (`exportar_codigo: true`). Para el agente es lo mismo | Guía + **digest** (estructura fija M6): ficha por componente, 3–6 flujos de punta a punta, restricciones y trampas, catálogos |
| Entre repos | Índice de integración | Índice + fichas de integración |
| Techo medido | 74–81 % (uso y sistema) | 60–72 % en uso, **≤ 42 % en preguntas de sistema** |

Si el agente solo tiene búsqueda, las preguntas que exigen juntar varios ficheros quedan por debajo del 42 %, y ninguna
curación lo arregla del todo. Por eso conviene que el agente pueda **leer documentos enteros**, no solo recibir trozos.

#El procedimiento práctico, con el árbol de decisión de cuánto curar cada repo, está en [CURAR-UN-REPO.md](CURAR-UN-REPO.md).

## El proceso

| Paso | Qué | Quién | Tiempo |
|---|---|---|---|
| 1. Exportar | Foto de los repos, export de Jira (JSON) y Confluence (XML), una sola vez | Persona con accesos | Lo que tarden los permisos |
| 2. Escanear y limpiar | Datos personales y credenciales: informe + redacción automática | Automático + revisión rápida | Minutos |
| 3. Extraer hechos | Variables, tablas, comandos, firmas, quién usa a quién (Python, TS/JS, C#) | Automático, sin LLM | Segundos |
| 4. Guías | Una por repo (skill `repo-guide`) | LLM barato | 1–3 min y céntimos por repo |
| 5. Jira y Confluence | A Markdown sin resumir, quitando solo los comentarios de bots | Automático, sin LLM | Segundos |
| 6. Índice entre repos | Skill `integration-index` | LLM barato | Minutos por par |
| 7. Vigencia | **Dos modelos fuertes** de familias distintas leen todas las fuentes juntas y clasifican cada valor o regla: consistente, cambio documentado o **contradicción** | Automático | ~5–10 min |
| 8. **Confirmación del cliente** | Solo las contradicciones, una pregunta cerrada por cada una, con evidencias y propuesta por fecha | **Experto del cliente** | ~2 min por pregunta (estimado) |
| 9. Aplicar y publicar | Respuestas → `stable`; sin respuesta → `draft` con los dos valores y un aviso | Automático | Minutos |

El único paso con persona es el 8, y es el único en el que medimos que la curación cambia el resultado de verdad. Si hay
que recortar tiempo, se recorta en cualquier otro.

## Validación de esta versión

Con las mismas fuentes y preguntas del piloto, este repo reproduce sus resultados:

| Medición | Piloto | Versión final |
|---|---|---|
| Repo A, preguntas de código (agente + código + guías) | 77–82 % | 87–88 % (con A solo o con A y C juntos) |
| Repo A, preguntas de la documentación | 79 % | 82 % |
| Repo C, uso / sistema | 83 % / 82 % | 85 % / 82 % |
| Entre repos (con índice) | 68–82 % | 79 % |
| Conflictos entre fuentes (agente + KB con vigencia) | 50–100 % | 50–71 % |
| Detección de los 7 conflictos conocidos | — | 7/7 con cada detector por separado y fusionados |

En estos datos simulados, el segundo detector no añadió detección. Se mantiene por defecto porque con fuentes reales no
sabemos aún cuántas contradicciones se escaparían con uno solo: `eval/recall_vigencia.py` lo mide.

## Límites conocidos

- **Las cifras vienen de un piloto controlado:**
  - repos Python y TypeScript pequeños y medianos;
  - Atlassian simulado por un LLM, más limpio que uno real;
  - pocas preguntas en conflictos (7) y entre repos (17).

  Las decisiones se apoyan en efectos grandes y repetidos, pero las cifras hay que confirmarlas con fuentes reales.
- **Sin probar:**
  - repos .NET grandes;
  - metadatos de Salesforce;
  - documentos de normativa y políticas;
  - tareas reales de la factory, en vez de preguntas;
  - Foundry IQ real (reranker, recuperación agéntica).
- **"Export once":** el registro de vigencia caduca cuando alguien cambia un valor en producción. Hay que decidir si se
  rehace periódicamente.
- Que el agente use bien un valor `draft` sin confirmar no se ha medido.

Para todo esto está `eval/bench.py`: genera preguntas verificadas sobre fuentes nuevas y mide cualquier variante.
