---
name: component-card
description: Ficha de un componente (contrato primero) para el modo búsqueda, cuando el agente solo recibe trozos de un buscador y no puede leer el código.
---

# Ficha de componente (solo modo búsqueda)

**Cuándo.** Solo si el agente **no puede leer el código** (ni clonando el repo ni leyendo ficheros de la KB) y solo
recibe trozos de un buscador. Con el agente leyendo código, las fichas no aportan.

**Por qué así.** Un buscador corta los documentos en trozos de ~2.000 caracteres. En el piloto, los documentos que
agrupaban varios componentes y empezaban por los helpers internos enterraban el dato que pedía el agente en otro trozo.
Con **una ficha por componente, el contrato primero y el nombre del componente en cada sección**, el acierto con búsqueda
pasó de 43–52 % a 60–67 %, y estable entre ejecuciones.

## Secciones (exactamente estas; cada encabezado empieza por el nombre del componente)
1. `## <componente> · Qué hace y cómo se invoca`: una frase de propósito; disparador (ruta y método HTTP, evento, cron o firma).
2. `## <componente> · Entrada`: campos del body, parámetros de ruta o query, claims o grupos requeridos; cuáles son obligatorios.
3. `## <componente> · Salida y errores`: respuesta de éxito con su forma; cada código de error con su causa y su mensaje literal.
4. `## <componente> · Configuración y datos`: variables de entorno con su valor por defecto; tablas, índices, buckets y
   servicios externos que lee o escribe.
5. `## <componente> · Comportamiento y reglas`: pasos en orden, reglas de negocio, rollbacks, idempotencia, límites y valores literales.
6. `## <componente> · Ejemplo`: una invocación mínima real (de los tests si existen).

## Reglas
- Sigue `okf-format`. Copia literalmente los HECHOS que recibes (variables, tablas, firmas, valores).
- Las funciones internas (parseo, limpieza, helpers) no se documentan una a una: solo si cambian el contrato.
- Unas 450 palabras. Omite una sección solo si de verdad no aplica.

Devuelve JSON: `{"title": "...", "description": "una frase", "tags": ["..."], "body": "Markdown desde el H1"}`.
