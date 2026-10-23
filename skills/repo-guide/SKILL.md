---
name: repo-guide
description: Escribe la guía de navegación de un repo (tipo AGENTS.md) para un agente de código que va a usarlo o integrarlo. Es la pieza que más aporta de toda la curación.
---

# Guía de un repo

**Para qué sirve.** En el piloto, dar al agente el repo más esta guía corta subió el acierto entre 18 y 31 puntos frente
al repo solo, y le ahorró pasos. Un digest completo del repo, 50 veces más largo, no aportó más. La guía no resume el
código: **le dice al agente qué es el repo y dónde mirar**, para que vaya directo al fichero que necesita.

## Qué recibes
El inventario completo del repo (cada fichero con su cabecera, lo que define, variables y tablas), los hechos globales
(paquetes, comandos, ficheros más usados), la configuración literal (rutas, despliegue), el README si existe y el código
de los ficheros centrales.

## Qué escribes (estas secciones, en este orden; omite la que no aplique)

1. **`<repo>` · Para qué sirve**: 2–4 frases. Qué problema resuelve, para quién, en qué sistema más grande encaja.
2. **`<repo>` · Qué expone**: los puntos de entrada que otros usan, cada uno con el fichero o carpeta donde vive:
   rutas HTTP (método + ruta), eventos y colas, tareas programadas, CLI, librerías públicas, pantallas. Si son muchos,
   agrúpalos y da el patrón ("cada Lambda HTTP vive en `src/functions/<área>/<nombre>/handler.py`").
3. **`<repo>` · Arquitectura**: componentes, cómo se comunican y el recorrido de una petición o evento típico, en texto y
   con un diagrama Mermaid pequeño.
4. **`<repo>` · Dónde está cada cosa**: mapa de carpetas → qué contienen, y **dónde buscar** según lo que se quiera saber
   (contratos y validaciones, reglas de negocio, acceso a datos, configuración, tests, despliegue). Esta sección es la
   que más usa el agente: sé concreto con rutas.
5. **`<repo>` · Configuración y datos**: variables de entorno (qué controla cada grupo), tablas o bases de datos, servicios
   externos y cómo se autentica.
6. **`<repo>` · Compilar, probar, desplegar**: comandos exactos.
7. **`<repo>` · Convenciones y trampas**: patrones que hay que seguir para ampliar el repo y comportamientos no obvios
   (sacados de los comentarios de advertencia y del código).
8. **`<repo>` · Relación con otros sistemas**: qué consume y quién lo consume, si se ve en el código.

## Reglas
- Sigue `okf-format`. Rutas y nombres exactos.
- **Navegación, no resumen**: cada afirmación importante lleva la ruta donde comprobarla. No copies contratos completos:
  el agente los leerá en el código (o en las fichas, en modo búsqueda).
- Corta: entre 900 y 1.800 palabras. Va en el contexto del agente en cada tarea.
- No inventes: si no ves algo en las fuentes, no lo pongas.

Devuelve JSON: `{"title": "<repo>", "description": "una frase", "tags": ["..."], "body": "Markdown desde el H1"}`.
