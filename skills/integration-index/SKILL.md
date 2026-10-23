---
name: integration-index
description: Empareja los puntos de un repo consumidor que llaman a otro repo (proveedor) con el componente del proveedor que los atiende. Produce un índice de navegación entre repos.
---

# Índice de integración entre dos repos

**Para qué sirve.** La conexión entre repos casi nunca está escrita: el frontend llama a `import.meta.env.VITE_*_URL`
y ningún fichero dice qué Lambda hay detrás. El agente tiene que deducirlo cada vez. Este índice lo deja escrito.

**Qué produce y qué no.** Un **índice** (qué llama a qué, con las rutas de los dos lados), no un resumen del contrato.
En el piloto, las fichas con el contrato resumido ayudaron a la búsqueda (+12–21 puntos), pero **empeoraron al agente
que tenía el código** (−15–23): se fiaba del resumen y dejaba de leer. Por eso, en modo agente solo se publica el índice
y las fichas solo se publican en modo búsqueda.

## Qué recibes
Del consumidor, los ficheros que hacen llamadas a servicios (cliente HTTP, variables `*_URL`, SDK). Del proveedor, el
inventario de sus puntos de entrada (cabeceras, rutas, nombres de despliegue).

## Cómo emparejar
1. Para cada llamada del consumidor (método o función), busca el punto de entrada del proveedor que la atiende. Las pistas
   son el nombre de la variable de URL, la ruta, los parámetros que envía, los campos que lee y el nombre del componente.
2. Si es local, un mock o un servicio externo que no está en el proveedor, márcalo así (`handler: null`).
3. Explica en una frase la evidencia del emparejamiento ("usa `VITE_TICKETS_BOARD_API_URL` y lee `columns`, que devuelve
   `board_list_tickets`").
4. No inventes: si no hay evidencia suficiente, `handler: null` y dilo en `why`.

Devuelve JSON: `{"pairs": [{"consumer_file": "ruta", "consumer_symbol": "método o función", "provider_file": "ruta o null",
"via": "variable de URL, ruta o SDK", "why": "evidencia en una frase"}]}`.
