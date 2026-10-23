"""Jira y Confluence → Markdown SIN resumir (sin LLM).

En el piloto, ninguna curación de Jira (por ticket, por épica, por funcionalidad) ni de Confluence (trocear, plantilla,
proposiciones) ganó al export convertido tal cual, ni con 686 tickets. Lo que importa es no perder nada:
comentarios (la causa raíz suele estar ahí), fechas, estados, enlaces y el historial.

Entrada:
  jira        JSON de la REST API v3: {"issues": [{"key", "fields": {...}, "changelog": {...}}]}
              (descripción y comentarios en ADF)
  confluence  carpeta con pages.json ([{"id", "title", "version", "ancestors", "lastModified", "labels"}])
              y pages/<id>.xml en storage format
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .okfio import write
from .sources import redact

BOTS = re.compile(r"(?i)(automation for jira|github for jira|jira bot|bitbucket|jenkins)")


def adf_md(node) -> str:
    if not isinstance(node, dict):
        return str(node or "")
    t, kids = node.get("type"), node.get("content", [])
    inner = "".join(adf_md(k) for k in kids)
    if t == "text":
        txt = node.get("text", "")
        marks = {m.get("type") for m in node.get("marks", [])}
        return f"`{txt}`" if "code" in marks else f"**{txt}**" if "strong" in marks else txt
    if t == "paragraph":
        return inner + "\n\n"
    if t == "heading":
        return "#" * (node.get("attrs", {}).get("level", 3) + 1) + " " + inner + "\n\n"
    if t == "codeBlock":
        return f"```\n{inner}\n```\n\n"
    if t == "bulletList":
        return "".join(f"- {adf_md(li).strip()}\n" for li in kids) + "\n"
    if t == "orderedList":
        return "".join(f"{i}. {adf_md(li).strip()}\n" for i, li in enumerate(kids, 1)) + "\n"
    if t == "hardBreak":
        return "\n"
    if t in {"mention", "emoji"}:
        return node.get("attrs", {}).get("text", "")
    return inner


def storage_md(x: str) -> str:
    x = re.sub(r'<ac:structured-macro ac:name="code">.*?<!\[CDATA\[(.*?)\]\]>.*?</ac:structured-macro>', lambda m: f"\n```\n{m.group(1)}\n```\n", x, flags=re.S)
    x = re.sub(r'<ac:structured-macro ac:name="(info|note|warning|tip)">.*?<ac:rich-text-body>(.*?)</ac:rich-text-body>.*?</ac:structured-macro>',
               lambda m: f"\n> **{m.group(1).upper()}:** {re.sub(r'<[^>]+>', ' ', m.group(2)).strip()}\n", x, flags=re.S)
    x = re.sub(r"<h(\d)>(.*?)</h\1>", lambda m: "\n" + "#" * int(m.group(1)) + " " + m.group(2) + "\n", x)
    x = re.sub(r"<tr>(.*?)</tr>", lambda m: "| " + " | ".join(re.sub(r"<[^>]+>", "", c).strip()
                                                           for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(1), re.S)) + " |\n", x, flags=re.S)
    x = re.sub(r"<li>(?:<p>)?(.*?)(?:</p>)?</li>", r"- \1\n", x, flags=re.S)
    x = re.sub(r"<code>(.*?)</code>", r"`\1`", x)
    x = re.sub(r"<strong>(.*?)</strong>", r"**\1**", x)
    x = re.sub(r"<p>(.*?)</p>", r"\1\n", x, flags=re.S)
    x = re.sub(r"<br\s*/?>", "\n", x)
    x = re.sub(r"<[^>]+>", "", x)
    return html.unescape(re.sub(r"\n{3,}", "\n\n", x)).strip()


def issue_md(i: dict) -> str:
    f = i["fields"]
    g = lambda k, sub="name": (f.get(k) or {}).get(sub, "—") if isinstance(f.get(k), dict) else "—"
    meta = [f"- Tipo: {g('issuetype')}", f"- Estado: {g('status')}", f"- Resolución: {g('resolution')}", f"- Prioridad: {g('priority')}",
            f"- Épica o padre: {(f.get('parent') or {}).get('key', '—')}", f"- Asignado: {g('assignee', 'displayName')}",
            f"- Creado: {(f.get('created') or '—')[:10]}", f"- Resuelto: {(f.get('resolutiondate') or '—')[:10]}",
            f"- Etiquetas: {', '.join(f.get('labels', [])) or '—'}"]
    for l in f.get("issuelinks", []):
        other = l.get("outwardIssue") or l.get("inwardIssue") or {}
        meta.append(f"- Enlace: {l.get('type', {}).get('name', '')} {other.get('key', '')}")
    out = [f"# {i['key']} · {f.get('summary', '')}", "", *meta, "", "## Descripción", "", adf_md(f.get("description")).strip() or "—", ""]
    comments = [c for c in f.get("comment", {}).get("comments", []) if not BOTS.search(c.get("author", {}).get("displayName", ""))]
    if comments:   # los comentarios de bots (sprints, PR merged) son ruido; los humanos se conservan TODOS
        out += ["## Comentarios", ""]
        for c in comments:
            out += [f"**{c['author'].get('displayName', '?')}** ({c.get('created', '')[:10]}):", "", adf_md(c.get("body")).strip(), ""]
    hist = [f"- {h['created'][:10]}: {it['field']} {it.get('fromString')} → {it.get('toString')}"
            for h in i.get("changelog", {}).get("histories", []) for it in h.get("items", []) if it.get("field") in {"status", "resolution", "Fix Version"}]
    if hist:
        out += ["## Historial", "", *hist]
    return redact("\n".join(out))


def page_md(p: dict, xml: str) -> str:
    return redact(f"# {p['title']}\n\n- Espacio: {' / '.join(p.get('ancestors', []))}\n- Versión: {p.get('version')}\n"
                  f"- Última modificación: {p.get('lastModified', '—')}\n- Etiquetas: {', '.join(p.get('labels', [])) or '—'}\n\n{storage_md(xml)}")


def load_jira(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["issues"]


def load_confluence(folder: Path) -> list[tuple[dict, str]]:
    pages = json.loads((folder / "pages.json").read_text(encoding="utf-8"))
    return [(p, (folder / "pages" / f"{p['id']}.xml").read_text(encoding="utf-8")) for p in pages]


def write_jira(issues: list[dict], out: Path, gen: dict) -> int:
    for i in issues:
        f = i["fields"]
        write(out / "jira" / f"{i['key']}.md", {"type": "Jira Issue", "title": f"{i['key']} {f.get('summary', '')}",
                                                "sources": [{"resource": f"jira:{i['key']}"}], "generated": gen,
                                                "status": "stable"}, issue_md(i))
    return len(issues)


def write_confluence(pages: list[tuple[dict, str]], out: Path, gen: dict) -> int:
    for p, xml in pages:
        archived = any(a.lower() in {"archivo", "archive", "obsoleto"} for a in p.get("ancestors", []))
        write(out / "confluence" / f"{p['id']}.md", {"type": "Confluence Page", "title": p["title"],
                                                     "sources": [{"resource": f"confluence:{p['id']}@v{p.get('version')}"}], "generated": gen,
                                                     "status": "deprecated" if archived else "stable"}, page_md(p, xml))
    return len(pages)
