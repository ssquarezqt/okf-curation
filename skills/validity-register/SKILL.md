---
name: validity-register
description: Lee todas las fuentes juntas (Jira, Confluence, configuración de los repos) y registra cada valor o regla con su historia, clasificado como consistente, cambio documentado o contradicción. Es la curación que más cambia el resultado.
---

# Registro de vigencia

**Para qué sirve.** Cuando Jira cambia un valor y Confluence sigue diciendo el antiguo, todo falla, y con seguridad. En
el piloto, el agente con las fuentes crudas acertó el 14–36 % de estas preguntas, y con cada fuente curada por separado,
el 7 % (congelaba el valor viejo). Con un registro de vigencia hecho por un modelo fuerte, el **68–82 %**. Ni la búsqueda
ni el agente reconcilian fuentes por sí solos: hay que hacerlo al curar.

## Qué registras
Cada **valor configurable, límite, umbral, ventana, tiempo, reintento, nombre, formato, estado o regla de comportamiento**
que aparezca en más de un sitio o que haya cambiado con el tiempo. Ignora lo que solo aparece una vez y nunca cambió.

## Cómo
1. Lee las fuentes **en orden cronológico**: fecha de resolución de cada ticket, última modificación de cada página, foto del repo.
2. Para cada valor o regla, reconstruye la cronología: `fecha · fuente · valor`.
3. Clasifica:
   - **consistente**: todas las fuentes dicen lo mismo;
   - **cambio**: un cambio posterior lo modifica de forma explícita (un ticket resuelto que dice "pasa de X a Y") y nada
     posterior lo contradice. Vigente = el último valor;
   - **contradicción**: las fuentes no coinciden y no hay una resolución explícita, hay varios cambios que chocan, o una
     página posterior al cambio sigue diciendo el valor antiguo. Propón el vigente por fecha, pero **no lo des por bueno**.
4. Anota qué fuentes quedan desactualizadas.

## Reglas
- Nombres exactos entre comillas invertidas (`FIRST_THRESHOLD` de `process-phoneuse-alert`, no "el umbral").
- `tema` identifica el valor y dónde aplica, sin ambigüedad.
- No inventes valores: cada punto de la cronología cita su fuente (clave del ticket o título de la página) y su fecha.

- `tema` corto: el nombre exacto y dónde aplica (`AUTO_APPROVE_LIMIT` de `demo-create-claim`), sin explicaciones.
- `valor` y `vigente` son **cortos y comparables** (`400`, `PENDING_REVIEW`, `2 h`); la explicación va en `detalle`.

Devuelve JSON: `{"entradas": [{"tema": "...", "clase": "consistente|cambio|contradiccion", "vigente": "valor corto propuesto",
"vigente_detalle": "una frase", "cronologia": [{"fecha": "AAAA-MM-DD", "fuente": "clave del ticket, página o fichero", "valor": "valor corto",
"detalle": "qué dice esa fuente"}], "desactualizado_en": ["fuente"], "nota": "por qué es contradicción, si lo es"}]}`.
