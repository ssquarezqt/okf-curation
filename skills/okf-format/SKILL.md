---
name: okf-format
description: Formato del repo OKF (Open Knowledge Format v0.2) que produce esta curación. Úsala al escribir o revisar cualquier documento de la base de conocimiento.
---

# Formato del repo OKF

El repo OKF es lo que un agente de código consulta para entender sistemas que va a usar o integrar. Puede llegarle
de dos formas, y el formato sirve para las dos:
- **modo agente**: el agente explora los ficheros (los lista, busca en ellos y los lee enteros);
- **modo búsqueda**: el agente recibe trozos de unos 2.000 caracteres que elige un buscador (Azure AI Search / Foundry IQ).

## Reglas del formato (OKF v0.2)

- **Un concepto por fichero.** La ruta sin `.md` es su identidad.
- **Frontmatter YAML** con `type` (obligatorio), `title`, `description` (una frase), `tags`, `sources`
  (`resource` = `<repo>@<foto>:<fichero>`, `jira:<KEY>` o `confluence:<id>@v<versión>`), `generated` (`by`, `at`) y
  `status` (`draft` | `stable` | `deprecated`).
- `index.md` en cada carpeta y `log.md` en la raíz son reservados: los genera el pipeline. El `index.md` raíz lleva `okf_version`.

## Tipos que produce esta curación

| type | Qué es | Dónde |
|---|---|---|
| Repository Guide | Guía de navegación de un repo (skill `repo-guide`) | `repos/<repo>/guia.md` |
| Source File | Código tal cual, solo si el agente no puede clonar pero sí leer ficheros | `repos/<repo>/codigo/` |
| Integration Index | Qué componente de un repo usa qué componente de otro (skill `integration-index`) | `integracion/` |
| Vigencia | Valor o regla con su historia entre fuentes y el valor vigente (skill `validity-register`) | `vigencia/` |
| Jira Issue / Confluence Page | Export convertido sin resumir | `jira/`, `confluence/` |
| API · Flow · Reference · Catalog | Digest del repo, solo en modo búsqueda: ficha por componente (skill `component-card`), flujos y restricciones (skill `repo-digest`), catálogos | `repos/<repo>/componentes/`, `flujos/`, `restricciones-trampas.md`, `catalogos/` |

## Reglas de escritura (para todo lo que redacta un modelo)

1. El H1 es `# <Tipo> · <Nombre>`.
2. **Nombres exactos entre comillas invertidas**: ficheros, funciones, variables de entorno, tablas, estados, comandos
   y valores, tal como aparecen en las fuentes. Nunca los parafrasees ni los generalices ("`MAX_RETRIES` = 2", no "tiene
   un límite de reintentos").
3. **Cada sección se entiende sola**: su título nombra el sujeto ("`admin_create_user` · Entrada", no "Entrada") y su
   primera frase sitúa el contexto. En modo búsqueda un trozo llega sin el resto del documento.
4. **Solo lo que dicen las fuentes.** Si algo relevante no se puede confirmar, dilo.
5. Nada importante solo en un diagrama: lo que dice un Mermaid también va en texto.
6. Sin cuerpos de funciones; sí firmas, rutas y ejemplos mínimos.
