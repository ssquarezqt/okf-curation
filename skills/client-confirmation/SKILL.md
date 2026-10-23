---
name: client-confirmation
description: Convierte cada contradicción del registro de vigencia en una pregunta cerrada para el experto del cliente y aplica sus respuestas. Es el único paso con persona del proceso.
---

# Confirmación del cliente

**Para qué sirve.** Las contradicciones entre fuentes no las resuelve ningún modelo con seguridad: la verdad la sabe el
dueño del sistema. En vez de revisar todo el registro, **solo se pregunta lo que está en contradicción**: unas pocas
preguntas de un minuto cada una.

## La pregunta
Una por contradicción, cerrada y con las evidencias delante:

> **`BOARD_OPEN_LIMIT` de `BoardListTickets`**
> - Confluence «06 — Configuración AWS» (2026-08-08): **20000**
> - Jira ETC-70 (resuelto 2026-09-05): **200** — "para evitar timeouts"
>
> ¿Cuál rige hoy en producción?  ☐ 200  ☐ 20000  ☐ Otro: ____
> *Propuesta por fecha: 200*

Reglas:
- Cada opción es un valor que aparece en las fuentes, con su fuente y su fecha. Siempre hay "Otro".
- La **propuesta por fecha** va marcada, para que confirmar sea un clic.
- Lenguaje del negocio cuando se pueda, con el nombre técnico entre comillas invertidas.
- Sin jerga de la curación: el experto no tiene por qué saber qué es OKF.

## Aplicar las respuestas
- Respondida → la entrada pasa a `status: stable`, con "confirmado por <persona>, <fecha>". Las fuentes con el otro
  valor quedan marcadas como desactualizadas.
- Sin respuesta → se publica con **los dos valores**, la propuesta por fecha y un aviso de "no confirmado"
  (`status: draft`), para que el agente lo trate con cautela.
