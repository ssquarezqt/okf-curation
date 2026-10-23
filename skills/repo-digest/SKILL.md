---
name: repo-digest
description: Digest de un repo para el modo búsqueda, cuando el agente no puede leer el código y solo recibe trozos de un buscador. Define qué documentos lleva y cómo se escriben los flujos y las restricciones; las fichas de componente siguen la skill component-card.
---

# Digest de un repo (modo búsqueda)

**Cuándo.** Solo cuando el agente **no puede leer el código**: ni clonando el repo ni leyendo ficheros de la base de
conocimiento con herramientas, y solo recibe trozos de unos 2.000 caracteres que elige un buscador. Si puede leer el código,
basta con la guía (skill `repo-guide`): el digest no aporta y las fichas compiten con la fuente.

**Qué funcionó en el piloto.** Con un digest organizado por un planificador libre (grafo, preguntas, entidades), el agente
acertaba un 35–58 % y el resultado era inestable. Con una **estructura fija y una ficha por componente**, acertaba un 60–67 % y el
resultado era estable. El techo de este modo está en las **preguntas de sistema** (como mucho un 42 %), porque la respuesta está
repartida entre varios ficheros. Los **flujos** de punta a punta son la pieza que junta esa información en un sitio.

## Documentos del digest (estructura fija; no se planifica)

| Documento | Qué responde | Cómo |
|---|---|---|
| `guia.md` | Qué es el repo y dónde está cada cosa | skill `repo-guide` |
| `componentes/<grupo>/<componente>.md` | Cómo se usa cada componente (contrato) | skill `component-card`, uno por fichero de código |
| `flujos/<flujo>.md` | Qué pasa de punta a punta en un proceso de negocio | esta skill, entre 3 y 6 flujos |
| `restricciones-trampas.md` | Qué hay que saber para no romper nada | esta skill, a partir de los comentarios de advertencia y del código |
| `catalogos/*.md` | Listas completas: variables de entorno, tablas, comandos y configuración | determinista, sin modelo |

## Flujos

Elige entre 3 y 6 **procesos de negocio de punta a punta**, cada uno nombrado como lo nombraría el negocio ("Ingesta de una
alerta hasta la llamada al conductor") y con los ficheros que recorre. Para cada uno, estas secciones; cada encabezado empieza
por el nombre del flujo:

1. `## <flujo> · Disparador`: qué lo inicia (petición HTTP, evento, cron, mensaje) y con qué datos.
2. `## <flujo> · Pasos`: en orden, cada paso con el fichero o componente que lo ejecuta y lo que lee o escribe. Añade un Mermaid
   pequeño, y repite en texto todo lo que diga el diagrama.
3. `## <flujo> · Estados y reglas`: estados por los que pasa la entidad, transiciones, umbrales, ventanas, reintentos y valores literales.
4. `## <flujo> · Errores y casos límite`: qué pasa si falla cada paso, timeouts, idempotencia y rollbacks.
5. `## <flujo> · Sistemas externos`: con qué servicios habla y cómo.

## Restricciones y trampas

Una lista de lo que hay que saber para **ampliar o integrar el repo sin romper nada**: comportamientos no obvios, límites,
valores que parecen booleanos y son texto, consultas con trampas, variables obligatorias, orden de operaciones, idempotencia y
timeouts. Cada punto nombra el fichero donde ocurre y, si sale de un comentario del código, lo cita. Agrupa por tema con
encabezados que nombren el repo ("`servicio-x` · Autorización").

## Reglas
- Sigue `okf-format`. Nombres y valores exactos entre comillas invertidas.
- Solo lo que dicen las fuentes; lo que no se pueda confirmar, se dice.
- Flujos: unas 600–900 palabras cada uno. Restricciones: unas 900 palabras.

Devuelve JSON: `{"title": "...", "description": "una frase", "tags": ["..."], "body": "Markdown desde el H1"}`.
