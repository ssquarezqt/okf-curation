# Metodología: transformar el conocimiento en Markdown para retrieval desde Blob

> **Objetivo.** Usar la arquitectura de retrieval nativa desde Azure Blob Storage (Blob → AI Search → Foundry IQ). Para ello
> hay que convertir todo el conocimiento de las fuentes del agente (repos, documentación, Jira, Confluence) en una
> jerarquía de carpetas con documentos Markdown. Algunas fuentes son directas, como un ticket de Jira. Otras no, como un
> repositorio de código, donde hay que decidir cuánto se destila y cuál es el contenido clave.

Esta metodología sale de un piloto en el que se compararon 10 enfoques con preguntas de prueba (evidencia al final). La
implementa este repo: `okf build` produce la jerarquía y `okf confirm` aplica las respuestas del cliente.

## 1. Seis reglas que valen para cualquier fuente

| Regla | Por qué |
|---|---|
| **Un concepto por fichero**, con frontmatter OKF (`type`, `title`, `description`, `sources`, `status`) | El buscador recupera trozos de ~2.000 caracteres. Un fichero que mezcla varios conceptos deja el dato en un trozo que no se recupera |
| **Cada sección se entiende sola**: su encabezado nombra el sujeto (`create_claim · Entrada`, no `Entrada`) | El trozo llega al agente sin el resto del documento |
| **Lo que ya es un documento se convierte, no se resume** (tickets, páginas, docs de los repos) | Ningún resumen ganó al original convertido. Algunos perdían datos: duplicados, causas en comentarios |
| **Lo que no es un documento se destila con estructura fija** (el código) | Con un planificador libre, el resultado era inestable (8–24 puntos entre ejecuciones). Con estructura fija fue estable y mejor |
| **Los literales no se parafrasean**: nombres, variables, tablas, valores y comandos se extraen con herramientas y se verifican | Al redactar, los modelos perdían literales y ficheros de configuración. Con extracción y verificación se cubre el 100 % de los hechos |
| **Lo que se contradice entre fuentes se reconcilia y se confirma con el cliente** | Ante un conflicto entre fuentes, sin reconciliar todo falla (14–36 %); con registro de vigencia, 68–82 % |

## 2. La jerarquía de carpetas

```
okf-<sistema>/
├── index.md                                 raíz OKF (okf_version) con enlaces a todo
├── repos/<repo>/
│   ├── guia.md                              qué es el repo y dónde está cada cosa
│   ├── docs/…                               la documentación que ya tiene el repo, tal cual
│   ├── componentes/<grupo>/<componente>.md  una ficha por componente: el contrato
│   ├── flujos/<flujo>.md                    3–6 procesos de negocio de punta a punta
│   ├── restricciones-trampas.md             lo que hay que saber para no romper nada
│   └── catalogos/
│       ├── componentes-dependencias.md      quién usa a quién dentro del repo + paquetes externos
│       ├── variables-entorno.md             cada variable y quién la lee
│       ├── tablas.md                        cada tabla o recurso de datos y quién lo usa
│       └── comandos-configuracion.md        comandos de scripts/CI y configuración literal
├── integracion/<consumidor>--<proveedor>.md qué componente atiende cada llamada entre repos
│   └── <consumidor>--<proveedor>/<llamada>.md   qué envía y qué lee cada lado
├── jira/<KEY>.md                            un ticket por fichero, completo
├── confluence/<id>.md                       una página por fichero, completa
├── vigencia/<id>-<tema>.md                  valor vigente de cada valor o regla, con su historia entre fuentes
├── vigencia/pendientes.md                   contradicciones que el cliente aún no ha confirmado
└── log.md
```

## 3. Cómo se transforma cada fuente

| Fuente | Qué se genera | Contenido clave | Cuánto se destila | Cómo |
|---|---|---|---|---|
| **Ticket de Jira** | `jira/<KEY>.md` | Resumen, tipo, estado, resolución, fechas, épica, enlaces (duplicados, bloqueos), descripción, **todos los comentarios humanos**, historial de estados | Nada; solo se quitan los comentarios de bots (sprints, PR merged) | Conversión ADF → Markdown, sin modelo |
| **Página de Confluence** | `confluence/<id>.md` | Título, espacio, versión, fecha de última modificación, cuerpo con tablas y bloques de código | Nada; las páginas en "Archivo" se marcan `deprecated` | Conversión storage XHTML → Markdown, sin modelo |
| **Docs del repo** (README, `docs/`) | `repos/<repo>/docs/…` | Lo que explica el porqué, la operación y los flujos | Nada | Copia con frontmatter |
| **Repositorio de código** | Guía + digest + catálogos (sección 4) | Propósito, contratos, dependencias, flujos, configuración, restricciones | Se destila con estructura fija. No se reduce el volumen (el digest ocupó entre el 75 % y el 115 % del código), pero sí la forma: contrato primero, un componente por fichero, sin cuerpos de funciones. La guía es ~1 % del código | Hechos con herramientas + redacción con modelo barato + verificación |
| **Varios repos** | `integracion/` | Qué llamada de un repo atiende qué componente de otro, por qué vía (variable de URL, ruta, SDK) | Índice + una ficha por llamada | Modelo barato con el código de los dos lados |
| **Entre todas las fuentes** | `vigencia/` | Cada valor o regla que cambió o que no coincide entre fuentes, con su cronología y el vigente | Solo lo que cambia o se contradice | Dos modelos fuertes + confirmación del cliente (sección 5) |

## 4. El repositorio de código en detalle

Es la fuente difícil: no es un documento y es demasiado grande para meterlo entero.

**Qué contenido es clave.** Lo que necesita un agente que va a **usar o integrar** el repo sin verlo, y dónde lo encuentra:

| Lo que necesita el agente | Documento | Ejemplo de pregunta que responde |
|---|---|---|
| Para qué sirve y qué expone | `guia.md` | ¿Qué rutas HTTP expone y dónde vive cada una? |
| Cómo se usa cada componente (el contrato) | `componentes/…` | ¿Qué campos son obligatorios en `POST /claims` y qué error da si falta uno? |
| De qué depende cada cosa (**árbol de dependencias**) | `catalogos/componentes-dependencias.md` | ¿Qué Lambdas usan `shared/auth.py`? ¿Qué paquetes externos usa? |
| Configuración y datos | `catalogos/variables-entorno.md`, `tablas.md` | ¿Qué variables necesita y con qué valor por defecto? |
| Cómo fluye un proceso de punta a punta | `flujos/…` | ¿Qué pasa desde que entra una alerta hasta que se llama al conductor? |
| Qué no se debe romper | `restricciones-trampas.md` | ¿Hay algún límite, orden u operación no idempotente que deba conocer? |
| Cómo se compila, prueba y despliega | `guia.md` + `catalogos/comandos-configuracion.md` | ¿Con qué comando se despliega una función? |
| Por qué está hecho así | `docs/…` (si el repo lo documenta) | ¿Por qué se descartó la alternativa X? |

**Qué se destila y qué no.**

| Se conserva literal | Se explica (redacta un modelo) | Se descarta |
|---|---|---|
| Rutas, firmas públicas, campos, códigos y mensajes de error, variables con su valor por defecto, tablas, valores de estados y umbrales, comandos, configuración | Qué hace cada componente, cómo encaja, el recorrido de un proceso, las reglas y las trampas | Cuerpos de funciones, helpers internos (parseo, limpieza) salvo que cambien el contrato, y código repetido |

**Cuánto.** Destilar no significa acortar. El digest ocupó entre el 75 % y el 115 % del código. Lo que aporta es **reorganizar**:
cada componente en su fichero con el contrato delante, los procesos juntados en flujos, las dependencias y la configuración en
listas completas, y sin código de implementación. El recorte del volumen está en la guía (~1 % del código), que es lo que el
agente lee primero.

**Cómo se hace, por documento:**

| Documento | Cómo | Tamaño |
|---|---|---|
| Hechos (base de todo) | Herramientas, sin modelo: inventario completo, firmas, variables, tablas, comandos, quién usa a quién, comentarios de advertencia (Python, TS/JS, C#) | — |
| Catálogos | Sin modelo, a partir de los hechos: completos por construcción | Listas |
| `guia.md` | Modelo barato con el inventario, la configuración, el README y los ficheros centrales (skill `repo-guide`) | 900–1.800 palabras |
| Fichas por componente | Una por fichero de código, con su código, sus tests y sus hechos; después, una verificación que la reescribe si falta algún hecho (skill `component-card`) | ~450 palabras |
| Flujos | El modelo elige 3–6 procesos y escribe cada uno con los ficheros que recorre (skill `repo-digest`) | 600–900 palabras |
| Restricciones y trampas | Desde los comentarios de advertencia y el código central (skill `repo-digest`) | ~900 palabras |

**Repos pequeños** (menos de unos 200.000 caracteres de código): el código tal cual más la guía rindió igual que el digest
(`exportar_codigo: true`).

**Sobre el árbol de dependencias.** También se probó a **organizar** todo el digest siguiendo el grafo de dependencias, y no
funcionó mejor que otras organizaciones y fue inestable. Las dependencias van como **dato** en el catálogo y en cada ficha
(usa y lo usan), no como forma de organizar el contenido.

## 5. Reconciliar entre fuentes y confirmar con el cliente

1. **Detectar.** Dos modelos fuertes de familias distintas leen todas las fuentes juntas, en orden cronológico, y registran cada valor o regla con su
   cronología. Lo clasifican como **consistente**, **cambio documentado** (un ticket posterior lo cambia explícitamente) o
   **contradicción** (las fuentes no coinciden y no hay resolución clara).
2. **Preguntar.** Solo las contradicciones van al experto del cliente, una por pregunta, cerrada, con las evidencias y la propuesta
   por fecha marcada (`trabajo/<sistema>/confirmaciones.md`).
3. **Aplicar.** Respondida, pasa a `stable` con quién y cuándo la confirmó. Sin respuesta, se publica con los dos valores y un aviso (`draft`).

Es el único paso con persona, y el único en el que medimos que la curación cambia el resultado de verdad.

## 6. El proceso

| Paso | Qué | Quién |
|---|---|---|
| 1 | Exportar una vez: foto de cada repo, Jira (JSON), Confluence (XML) | Persona con accesos |
| 2 | Escanear datos sensibles (`okf scan`); se redactan solos, pero se excluyen los ficheros de credenciales | Automático + revisión |
| 3 | Curar (`okf build`): hechos, guías, docs, digest, catálogos, Jira, Confluence, integración, vigencia | Automático, 5–15 min por sistema |
| 4 | Revisar las guías por encima | Persona, 15–30 min por repo |
| 5 | Confirmar las contradicciones | Experto del cliente, ~2 min por pregunta |
| 6 | Aplicar (`okf confirm`) y publicar el repo OKF (git → Blob → AI Search → Foundry IQ) | Automático |

Procedimiento detallado en [CURAR-UN-REPO.md](CURAR-UN-REPO.md).

## 7. Si el agente pudiera leer ficheros enteros

Con retrieval de trozos hay un techo: las **preguntas de sistema**, cuya respuesta está repartida entre varios ficheros, no pasaron
del 42 %. Si el agente puede abrir documentos enteros (clonar el repo o leer ficheros de la KB con herramientas), el resultado
sube al 74–81 %, y entonces basta con la guía más el código tal cual (`modo: agente`, `exportar_codigo: true`). Conviene comprobar
en el spike de Azure si Foundry IQ o el agente hospedado lo permiten.

## 8. Evidencia: qué se probó para llegar aquí

**Cómo se midió.**
- Preguntas con respuesta conocida y verificada contra la fuente. Responde gpt-5.4-mini, juzga Claude (0/1/2).
- Dos formas de consulta: búsqueda de 5 trozos (como Foundry IQ) y agente con herramientas.
- Fuentes:
  - repo A: backend Python grande;
  - repo B: Python pequeño;
  - repo C: frontend TypeScript;
  - Jira y Confluence simulados con trampas.
- Menos de 10 puntos de diferencia cuenta como empate.

| Enfoque probado | Resultado | Decisión |
|---|---|---|
| Digest organizado por un planificador libre (por grafo, por preguntas, por entidades) | 35–58 %, sin ganador, inestable | Descartado |
| Redactar con agente en lugar de prompt | Empate | Descartado |
| Plantilla temática fija por grupos | Estable, sin mejora | Descartado |
| **Una ficha por componente, contrato primero** (+ flujos, restricciones y catálogos) | De ~45 % a 60–67 %, estable | **Digest del repo** |
| **Digest + documentación del repo** | 72 % (frente a 46–54 % del digest solo) | **Se publican los docs del repo** |
| Herramienta de mercado (CodeWiki) | 16 % | Descartado |
| Guía corta + código, con agente | 74–81 %, el mejor en los tres repos | **Guía en todos los casos** |
| Jira: por ticket, épica o funcionalidad · Confluence: trocear, plantilla, proposiciones | Ninguno ganó al export convertido, ni con 686 tickets | **Convertir sin resumir** |
| Mapa de integración entre repos | Búsqueda: de 29–32 % a 44–50 % | **Índice + fichas de integración** |
| **Registro de vigencia entre fuentes** | Conflictos: de 14–36 % a 68–82 %; curar cada fuente por separado, 7 % | **Vigencia + confirmación** |

**Validación de este repo:** con las mismas fuentes y preguntas reproduce los resultados del piloto (repo A 87–88 %, repo C
85 % / 82 %, entre repos 79 %, conflictos 50–71 %). El detector encuentra 7 de 7 conflictos conocidos.

**Límites:**
- Piloto controlado: repos Python y TypeScript pequeños y medianos, Atlassian simulado, pocas preguntas de conflicto (7) y entre repos (17).
- Sin probar todavía:
  - repos .NET grandes;
  - Salesforce;
  - documentos de normativa;
  - tareas reales de la factory;
  - Foundry IQ real.
- El registro de vigencia caduca cuando cambian las fuentes ("export once"): hay que decidir cada cuánto se rehace.

`eval/bench.py` y `eval/recall_vigencia.py` permiten repetir las mediciones con fuentes reales.
