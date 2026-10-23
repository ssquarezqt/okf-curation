"""Acceso a modelos. Un modelo `claude-*` va por Anthropic; cualquier otro, por OpenAI.

Claves: variables de entorno OPENAI_API_KEY / ANTHROPIC_API_KEY o un fichero KEY=valor indicado en OKF_ENV_FILE
(por defecto ~/.okf.env). Nunca se imprimen.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

_clients: dict = {}
_lock = threading.Lock()
usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}


def _key(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    env = Path(os.environ.get("OKF_ENV_FILE", Path.home() / ".okf.env")).expanduser()
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            t = line.strip().removeprefix("export ")
            if t.startswith(name + "="):
                return t.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"Falta {name} (variable de entorno o fichero OKF_ENV_FILE)")


def _client(provider: str):
    with _lock:
        if provider not in _clients:
            if provider == "anthropic":
                import anthropic
                _clients[provider] = anthropic.Anthropic(api_key=_key("ANTHROPIC_API_KEY"))
            else:
                from openai import OpenAI
                _clients[provider] = OpenAI(api_key=_key("OPENAI_API_KEY"))
    return _clients[provider]


def _count(i: int, o: int) -> None:
    with _lock:
        usage["calls"] += 1
        usage["input_tokens"] += i
        usage["output_tokens"] += o


def text(model: str, system: str, user: str, max_tokens: int = 16000) -> str:
    for attempt in range(4):
        try:
            if model.startswith("claude"):
                # streaming: las salidas largas lo exigen; solo cuentan los bloques de texto (no el razonamiento)
                with _client("anthropic").messages.stream(model=model, max_tokens=max_tokens, system=system,
                                                          messages=[{"role": "user", "content": user}]) as s:
                    r = s.get_final_message()
                _count(r.usage.input_tokens, r.usage.output_tokens)
                return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()
            r = _client("openai").chat.completions.create(model=model, messages=[{"role": "system", "content": system},
                                                                                {"role": "user", "content": user}])
            _count(r.usage.prompt_tokens, r.usage.completion_tokens)
            return (r.choices[0].message.content or "").strip()
        except Exception as e:  # errores transitorios
            if attempt == 3:
                raise
            print(f"    reintento {model} ({type(e).__name__})", flush=True)
            time.sleep(4 * (attempt + 1))
    return ""


def json_call(model: str, system: str, user: str, max_tokens: int = 16000) -> dict:
    """Llamada que debe devolver un objeto JSON. Reintenta si el JSON llega roto."""
    for attempt in range(3):
        if not model.startswith("claude"):
            try:
                r = _client("openai").chat.completions.create(model=model, response_format={"type": "json_object"},
                                                              messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
                _count(r.usage.prompt_tokens, r.usage.completion_tokens)
                return json.loads(r.choices[0].message.content)
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"    reintento {model} ({type(e).__name__})", flush=True)
                time.sleep(3 * (attempt + 1))
                continue
        out = text(model, system, user, max_tokens)
        m = re.search(r"\{.*\}", out, re.S)
        try:
            return json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            if attempt == 2:
                return {}
    return {}
