#!/usr/bin/env python3
"""Render Claude Code JSONL transcripts as readable HTML.

Usage:
  cc-transcript.py list                        # list all sessions across projects
  cc-transcript.py render <path|sessionId>     # render one transcript -> transcript.html
  cc-transcript.py render <path> -o out.html   # custom output (use '-' for stdout)
  cc-transcript.py all                         # render every transcript + index page
  cc-transcript.py all -o ./out                # custom output directory
"""
import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"

CSS = """
:root {
  --bg: #faf9f5;
  --surface: #ffffff;
  --fg: #2c2825;
  --muted: #8a857c;
  --accent: #c96442;
  --accent-soft: #f4ece2;
  --border: #ece8de;
  --border-soft: #f1ede3;
  --user-bg: #f0ebe1;
  --assistant-bg: transparent;
  --thinking-bg: #f1ecf5;
  --thinking-fg: #6b5b86;
  --tool-bg: #faf3e0;
  --tool-result-bg: #f5f1ea;
  --code-bg: #30302e;
  --code-fg: #f5f1ea;
  --inline-code-bg: #f0ebe1;
  --inline-code-fg: #993b1f;
}
* { box-sizing: border-box; }
html { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
body {
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Söhne",
    "Inter", "Segoe UI", system-ui, sans-serif;
  margin: 0; padding: 32px 16px;
  background: var(--bg); color: var(--fg);
  line-height: 1.6; font-size: 15px;
}
.container { max-width: 780px; margin: 0 auto; }
header {
  margin-bottom: 28px; padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
header h1 {
  margin: 0 0 6px 0; font-size: 22px; font-weight: 500;
  font-family: "Copernicus", "Tiempos Headline", Georgia, "Iowan Old Style", serif;
  letter-spacing: -0.01em; color: var(--fg);
}
header .meta {
  color: var(--muted); font-size: 12.5px; word-break: break-all;
  font-feature-settings: "tnum";
}
.msg { margin: 18px 0; padding: 0; }
.msg.user {
  background: var(--user-bg);
  padding: 14px 18px; border-radius: 14px;
  margin-left: 12%;
}
.msg.assistant { padding: 4px 0; }
.role {
  font-weight: 500; font-size: 11px; text-transform: uppercase;
  color: var(--muted); margin-bottom: 8px; letter-spacing: 0.7px;
}
.role .ts { font-weight: 400; text-transform: none; margin-left: 8px; color: var(--muted); }
.msg p { margin: 8px 0; }
.msg p:first-child { margin-top: 0; }
.msg p:last-child { margin-bottom: 0; }
.msg pre {
  background: var(--code-bg); color: var(--code-fg);
  padding: 14px 16px; border-radius: 10px; overflow-x: auto;
  font-size: 12.5px; line-height: 1.55;
  font-family: ui-monospace, SFMono-Regular, "JetBrains Mono", Menlo, monospace;
  white-space: pre-wrap; word-break: break-word;
  margin: 12px 0;
}
.msg :not(pre) > code {
  background: var(--inline-code-bg); color: var(--inline-code-fg);
  padding: 1px 6px; border-radius: 5px;
  font-size: 0.88em;
  font-family: ui-monospace, SFMono-Regular, "JetBrains Mono", Menlo, monospace;
}
details {
  margin: 10px 0; border: 1px solid var(--border);
  border-radius: 10px; overflow: hidden; background: var(--surface);
}
details > summary {
  padding: 9px 14px; cursor: pointer;
  font-size: 13px; font-weight: 500; user-select: none;
  list-style: none; color: var(--fg);
  transition: background 0.12s ease;
}
details > summary::-webkit-details-marker { display: none; }
details > summary:hover { background: var(--border-soft); }
details[open] > summary { border-bottom: 1px solid var(--border); }
details > .body { padding: 12px 14px; background: var(--surface); }
.thinking { background: var(--thinking-bg); border-color: #ddd4e8; }
.thinking > summary { color: var(--thinking-fg); }
.thinking > summary::before { content: "✦  "; }
.thinking > .body { background: var(--thinking-bg); color: var(--thinking-fg); }
.tool { background: var(--tool-bg); border-color: #ecd9a7; }
.tool > summary::before { content: "▸  "; color: var(--accent); }
.tool > .body { background: var(--tool-bg); }
.tool-result {
  background: var(--tool-result-bg); margin-top: 10px;
  border-color: var(--border);
}
.tool-result > summary::before { content: "↳  "; color: var(--muted); }
.tool-result > .body { background: var(--tool-result-bg); }
.tool-name { font-weight: 600; color: var(--accent); }
.muted { color: var(--muted); font-weight: 400; }
.attachment { background: var(--surface); font-size: 12px; }
.attachment > summary::before { content: "ⓘ  "; color: var(--muted); }
.attachment > .body { background: var(--surface); }
.idx { list-style: none; padding: 0; margin: 0; }
.idx li {
  padding: 14px 18px; border: 1px solid var(--border);
  border-radius: 12px; margin: 10px 0; background: var(--surface);
  transition: border-color 0.12s ease, transform 0.12s ease;
}
.idx li:hover { border-color: var(--accent); }
.idx li a { color: var(--fg); text-decoration: none; font-weight: 500; }
.idx li a:hover { color: var(--accent); }
.idx .sub {
  color: var(--muted); font-size: 12px; margin-top: 6px;
  font-feature-settings: "tnum";
}
.idx .sub code {
  background: var(--accent-soft); color: var(--accent);
  padding: 1px 5px; border-radius: 4px; font-size: 0.92em;
}
.stats { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
.stat {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 16px; min-width: 96px; text-align: center;
}
.stat-num {
  font-size: 20px; font-weight: 600; color: var(--fg);
  font-feature-settings: "tnum";
  font-family: "Copernicus", Georgia, "Iowan Old Style", serif;
}
.stat-lbl {
  font-size: 10.5px; text-transform: uppercase; color: var(--muted);
  letter-spacing: 0.6px; margin-top: 3px;
}
.tool-breakdown { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; }
.tool-chip {
  font-size: 12px; background: var(--accent-soft); color: var(--fg);
  border: 1px solid var(--border); border-radius: 999px; padding: 3px 10px;
  font-feature-settings: "tnum";
}
.tool-chip b { color: var(--accent); font-weight: 600; }

/* --- bookmarks --- */
.bm-nav {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 14px 18px; margin: 18px 0 4px;
}
.bm-nav h2 {
  margin: 0 0 10px; font-size: 13px; text-transform: uppercase;
  letter-spacing: 0.6px; color: var(--muted); font-weight: 600;
}
.bm-nav ol { margin: 0; padding-left: 20px; }
.bm-nav li { margin: 5px 0; }
.bm-nav a { color: var(--fg); text-decoration: none; }
.bm-nav a:hover { color: var(--accent); }
.bm-nav .cat {
  display: inline-block; font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.5px; padding: 1px 7px; border-radius: 999px;
  background: var(--accent-soft); color: var(--accent); margin-right: 6px;
  vertical-align: middle;
}
.bm-nav .note { color: var(--muted); font-size: 12.5px; }
.msg.bookmarked {
  scroll-margin-top: 16px;
}
.bm-flag {
  display: flex; align-items: baseline; gap: 8px;
  background: linear-gradient(0deg, transparent, var(--accent-soft));
  border-left: 3px solid var(--accent);
  padding: 8px 12px; border-radius: 0 8px 8px 0; margin-bottom: 10px;
}
.bm-flag .bm-star { color: var(--accent); font-size: 15px; }
.bm-flag .bm-title { font-weight: 600; color: var(--accent); }
.bm-flag .bm-note { color: var(--muted); font-size: 13px; }
.bm-flag .cat {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;
  padding: 1px 7px; border-radius: 999px; background: var(--surface);
  border: 1px solid var(--accent); color: var(--accent);
}
:target.msg, :target.bookmarked {
  animation: flash 1.6s ease;
}
@keyframes flash {
  0%, 30% { background: #fbe6c8; }
  100% { background: var(--user-bg); }
}
.msg.assistant:target { animation: flashplain 1.6s ease; }
@keyframes flashplain {
  0%, 30% { background: #fbe6c8; border-radius: 10px; }
  100% { background: transparent; }
}
/* bookmarks index page */
.bm-group { margin: 22px 0; }
.bm-group h2 {
  font-size: 16px; margin: 0 0 4px;
  font-family: "Copernicus", Georgia, serif; font-weight: 500;
}
.bm-group .ses-meta { color: var(--muted); font-size: 12px; margin-bottom: 10px; }
.bm-item {
  border: 1px solid var(--border); border-left: 3px solid var(--accent);
  border-radius: 0 10px 10px 0; padding: 10px 14px; margin: 8px 0;
  background: var(--surface);
}
.bm-item a { color: var(--fg); text-decoration: none; font-weight: 600; }
.bm-item a:hover { color: var(--accent); }
.bm-item .note { color: var(--muted); font-size: 13px; margin-top: 3px; }
.bm-item .quote {
  margin-top: 6px; padding-left: 10px; border-left: 2px solid var(--border);
  color: var(--muted); font-size: 12.5px; font-style: italic;
}
"""


def esc(s):
    return html.escape("" if s is None else str(s))


def fmt_ts(ts, full=False):
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S" if full else "%H:%M:%S")
    except Exception:
        return ts


def md_to_html(text):
    """Tiny markdown-ish renderer: fenced code, inline code, bold, paragraphs."""
    if not text:
        return ""
    out = []
    for i, part in enumerate(text.split("```")):
        if i % 2 == 1:
            if "\n" in part:
                first, body = part.split("\n", 1)
                if re.fullmatch(r"[A-Za-z0-9_+\-.]*", first.strip()):
                    part = body
            out.append(f"<pre><code>{esc(part)}</code></pre>")
        else:
            t = esc(part)
            t = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", t)
            t = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", t)
            for para in re.split(r"\n\s*\n", t):
                p = para.strip()
                if p:
                    out.append(f'<p>{p.replace(chr(10), "<br>")}</p>')
    return "\n".join(out)


def render_tool_result(block, max_chars=8000):
    if block is None:
        return ""
    inner = block.get("content")
    if isinstance(inner, list):
        bits = []
        for b in inner:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    bits.append(b.get("text", ""))
                else:
                    bits.append(json.dumps(b, indent=2, ensure_ascii=False))
            else:
                bits.append(str(b))
        text = "\n\n".join(bits)
    elif inner is None:
        text = ""
    else:
        text = str(inner)
    err = ' <span class="muted" style="color:var(--accent)">(error)</span>' if block.get("is_error") else ""
    note = ""
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n…[truncated, {len(text) - max_chars} more chars]"
        note = ' <span class="muted">[truncated]</span>'
    return (
        f'<details class="tool-result"><summary>tool result{err}{note}</summary>'
        f'<div class="body"><pre><code>{esc(text)}</code></pre></div></details>'
    )


def render_assistant_block(block, tool_results):
    btype = block.get("type")
    if btype == "thinking":
        thinking = block.get("thinking", "")
        if not thinking.strip():
            return ""
        return (
            f'<details class="thinking"><summary>thinking</summary>'
            f'<div class="body">{md_to_html(thinking)}</div></details>'
        )
    if btype == "text":
        return md_to_html(block.get("text", ""))
    if btype == "tool_use":
        name = esc(block.get("name", ""))
        tool_input = block.get("input", {})
        try:
            input_text = json.dumps(tool_input, indent=2, ensure_ascii=False)
        except Exception:
            input_text = str(tool_input)
        summary_extra = ""
        if isinstance(tool_input, dict):
            for k in ("command", "file_path", "path", "description", "prompt", "query", "pattern", "url"):
                v = tool_input.get(k)
                if isinstance(v, str) and v:
                    snippet = v.replace("\n", " ").strip()
                    summary_extra = f' <span class="muted">— {esc(snippet[:90])}{"…" if len(snippet) > 90 else ""}</span>'
                    break
        result_html = render_tool_result(tool_results.get(block.get("id")))
        return (
            f'<details class="tool"><summary><span class="tool-name">{name}</span>{summary_extra}</summary>'
            f'<div class="body"><pre><code>{esc(input_text)}</code></pre>{result_html}</div></details>'
        )
    return f'<pre><code>{esc(json.dumps(block, indent=2, ensure_ascii=False))}</code></pre>'


def render_user_content(content):
    if isinstance(content, str):
        return md_to_html(content)
    if isinstance(content, list):
        bits = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                bits.append(md_to_html(b.get("text", "")))
        return "\n".join(bits)
    return ""


def is_pure_tool_result(content):
    return (
        isinstance(content, list)
        and len(content) > 0
        and all(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
    )


def render_bookmark_flag(bm):
    cat = bm.get("category", "")
    cat_html = f'<span class="cat">{esc(cat)}</span>' if cat else ""
    note = bm.get("note", "")
    note_html = f'<span class="bm-note">{esc(note)}</span>' if note else ""
    return (
        f'<div class="bm-flag"><span class="bm-star">★</span>{cat_html}'
        f'<span class="bm-title">{esc(bm.get("title", "Bookmark"))}</span>'
        f'{note_html}</div>'
    )


def render_event(ev, tool_results, show_attachments, bookmarks=None):
    etype = ev.get("type")
    ts = fmt_ts(ev.get("timestamp"))
    uid = ev.get("uuid", "")
    bm = bookmarks.get(uid) if (bookmarks and uid) else None
    anchor = f' id="msg-{esc(uid)}"' if uid else ""
    flag = render_bookmark_flag(bm) if bm else ""
    bm_cls = " bookmarked" if bm else ""

    if etype in ("permission-mode", "file-history-snapshot"):
        return ""

    if etype == "attachment":
        if not show_attachments:
            return ""
        att = ev.get("attachment", {})
        atype = att.get("type", "attachment")
        body = json.dumps(att, indent=2, ensure_ascii=False)
        return (
            f'<details class="msg attachment"{anchor}><summary>system: {esc(atype)} '
            f'<span class="ts">{esc(ts)}</span></summary>'
            f'<div class="body"><pre><code>{esc(body)}</code></pre></div></details>'
        )

    if etype == "user":
        msg = ev.get("message", {})
        content = msg.get("content", "")
        if is_pure_tool_result(content):
            return ""
        body = render_user_content(content)
        if not body.strip():
            return ""
        return (
            f'<div class="msg user{bm_cls}"{anchor}>{flag}<div class="role">user '
            f'<span class="ts">{esc(ts)}</span></div>{body}</div>'
        )

    if etype == "assistant":
        msg = ev.get("message", {})
        content = msg.get("content", [])
        if not isinstance(content, list):
            return ""
        rendered = [render_assistant_block(b, tool_results) for b in content]
        rendered = [r for r in rendered if r and r.strip()]
        if not rendered:
            return ""
        model = esc(msg.get("model", ""))
        meta = esc(ts) + ((" · " + model) if model else "")
        return (
            f'<div class="msg assistant{bm_cls}"{anchor}>{flag}<div class="role">assistant '
            f'<span class="ts">{meta}</span></div>'
            + "\n".join(rendered)
            + "</div>"
        )

    return ""


def parse_jsonl(path):
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def first_user_prompt(events):
    """First real user prompt — skips slash-command shells like <local-command-caveat>."""
    for ev in events:
        if ev.get("type") != "user":
            continue
        c = ev.get("message", {}).get("content")
        if not isinstance(c, str):
            continue
        s = c.strip()
        if not s:
            continue
        if s.startswith("<local-command-") or s.startswith("<command-"):
            continue
        return s
    return ""


def session_title(events, project_dir_name=""):
    """Return the session's display name.

    Priority: aiTitle (auto-generated descriptive title shown in /resume)
              -> customTitle (skip if it just mirrors the project folder name)
              -> first user prompt
    Uses the LAST occurrence of each title event, since they may be rewritten.
    """
    ai_title = ""
    custom_title = ""
    for ev in events:
        t = ev.get("type")
        if t == "ai-title":
            v = ev.get("aiTitle")
            if isinstance(v, str) and v.strip():
                ai_title = v.strip()
        elif t == "custom-title":
            v = ev.get("customTitle")
            if isinstance(v, str) and v.strip():
                custom_title = v.strip()
    if ai_title:
        return ai_title
    # Skip customTitle when it's just (or contains) the project folder name —
    # Claude Code defaults to it, and cwd may change mid-session so basename
    # equality is unreliable. Substring of the encoded project dir works for
    # dashed names like "claude-transcript-viewer", "lora-rs", etc.
    if custom_title and len(custom_title) >= 4:
        proj_key = project_dir_name.lower()
        if custom_title.lower() in proj_key:
            custom_title = ""
    if custom_title:
        return custom_title
    first = first_user_prompt(events)
    if first:
        return first[:80] + ("…" if len(first) > 80 else "")
    return ""


def compute_stats(events):
    s = {
        "user": 0,
        "assistant": 0,
        "tool_uses": 0,
        "thinking": 0,
        "tool_errors": 0,
        "in_tokens": 0,
        "out_tokens": 0,
        "tools": {},
        "duration": "",
    }
    timestamps = []
    for ev in events:
        if ev.get("timestamp"):
            timestamps.append(ev["timestamp"])
        etype = ev.get("type")
        if etype == "user":
            content = ev.get("message", {}).get("content", "")
            if is_pure_tool_result(content):
                for b in content:
                    if b.get("is_error"):
                        s["tool_errors"] += 1
            elif render_user_content(content).strip():
                s["user"] += 1
        elif etype == "assistant":
            msg = ev.get("message", {})
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            has_visible = False
            for b in content:
                bt = b.get("type")
                if bt == "tool_use":
                    s["tool_uses"] += 1
                    name = b.get("name", "?")
                    s["tools"][name] = s["tools"].get(name, 0) + 1
                    has_visible = True
                elif bt == "thinking" and b.get("thinking", "").strip():
                    s["thinking"] += 1
                    has_visible = True
                elif bt == "text" and b.get("text", "").strip():
                    has_visible = True
            if has_visible:
                s["assistant"] += 1
            usage = msg.get("usage", {})
            if isinstance(usage, dict):
                s["in_tokens"] += usage.get("input_tokens", 0) or 0
                s["in_tokens"] += usage.get("cache_read_input_tokens", 0) or 0
                s["in_tokens"] += usage.get("cache_creation_input_tokens", 0) or 0
                s["out_tokens"] += usage.get("output_tokens", 0) or 0
    if len(timestamps) >= 2:
        try:
            parsed = []
            for t in timestamps:
                try:
                    parsed.append(datetime.fromisoformat(t.replace("Z", "+00:00")))
                except Exception:
                    pass
            secs = int((max(parsed) - min(parsed)).total_seconds())
            if secs >= 3600:
                s["duration"] = f"{secs // 3600}h {secs % 3600 // 60}m"
            elif secs >= 60:
                s["duration"] = f"{secs // 60}m {secs % 60}s"
            else:
                s["duration"] = f"{secs}s"
        except Exception:
            pass
    return s


def render_stats(s):
    def stat(label, value):
        return (
            f'<div class="stat"><div class="stat-num">{esc(value)}</div>'
            f'<div class="stat-lbl">{esc(label)}</div></div>'
        )

    cards = [
        stat("user msgs", f'{s["user"]:,}'),
        stat("assistant msgs", f'{s["assistant"]:,}'),
        stat("tool calls", f'{s["tool_uses"]:,}'),
        stat("thinking blocks", f'{s["thinking"]:,}'),
    ]
    if s["tool_errors"]:
        cards.append(stat("tool errors", f'{s["tool_errors"]:,}'))
    if s["in_tokens"] or s["out_tokens"]:
        cards.append(stat("tokens in", f'{s["in_tokens"]:,}'))
        cards.append(stat("tokens out", f'{s["out_tokens"]:,}'))
    if s["duration"]:
        cards.append(stat("time span", s["duration"]))

    top = sorted(s["tools"].items(), key=lambda kv: kv[1], reverse=True)
    breakdown = ""
    if top:
        chips = " ".join(
            f'<span class="tool-chip">{esc(name)} <b>{count}</b></span>'
            for name, count in top
        )
        breakdown = f'<div class="tool-breakdown">{chips}</div>'

    return f'<div class="stats">{"".join(cards)}</div>{breakdown}'


def render_bm_nav(ordered_bms):
    if not ordered_bms:
        return ""
    items = []
    for uid, bm in ordered_bms:
        cat = bm.get("category", "")
        cat_html = f'<span class="cat">{esc(cat)}</span>' if cat else ""
        note = bm.get("note", "")
        note_html = f' <span class="note">— {esc(note)}</span>' if note else ""
        items.append(
            f'<li><a href="#msg-{esc(uid)}">{cat_html}{esc(bm.get("title", "Bookmark"))}</a>{note_html}</li>'
        )
    return (
        f'<div class="bm-nav"><h2>★ {len(items)} bookmarks in this session</h2>'
        f'<ol>{"".join(items)}</ol></div>'
    )


def render_html(events, title, show_attachments=False, project_dir_name="", bookmarks=None):
    bookmarks = bookmarks or {}
    tool_results = {}
    for ev in events:
        if ev.get("type") == "user":
            content = ev.get("message", {}).get("content")
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        tuid = b.get("tool_use_id")
                        if tuid:
                            tool_results[tuid] = b

    body_parts = []
    ordered_bms = []
    for ev in events:
        uid = ev.get("uuid", "")
        chunk = render_event(ev, tool_results, show_attachments, bookmarks)
        if chunk:
            if uid and uid in bookmarks:
                ordered_bms.append((uid, bookmarks[uid]))
            body_parts.append(chunk)

    cwd = next((ev["cwd"] for ev in events if ev.get("cwd")), "")
    sid = next((ev["sessionId"] for ev in events if ev.get("sessionId")), "")
    started = next((fmt_ts(ev["timestamp"], full=True) for ev in events if ev.get("timestamp")), "")

    title_text = session_title(events, project_dir_name) or title
    stats_html = render_stats(compute_stats(events))
    bm_nav = render_bm_nav(ordered_bms)

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title_text)}</title>
<style>{CSS}</style>
</head><body>
<div class="container">
<header>
<h1>{esc(title_text)}</h1>
<div class="meta">{esc(sid)} · {esc(cwd)} · {esc(started)}</div>
{stats_html}
</header>
{bm_nav}
{"".join(body_parts)}
</div>
</body></html>
"""


def list_sessions():
    rows = []
    if not PROJECTS_DIR.exists():
        return rows
    for project_dir in sorted(PROJECTS_DIR.glob("*")):
        if not project_dir.is_dir():
            continue
        for f in sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = f.stat()
            rows.append({
                "project": project_dir.name,
                "session": f.stem,
                "path": f,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime),
            })
    return rows


def cmd_list():
    rows = list_sessions()
    if not rows:
        print(f"No sessions found in {PROJECTS_DIR}", file=sys.stderr)
        return
    for r in rows:
        print(f"{r['mtime']:%Y-%m-%d %H:%M}  {r['size']:>8}  {r['project']}/{r['session']}")


def count_tokens_stream(path):
    """Sum token usage by streaming a .jsonl line-by-line (memory-safe for huge files)."""
    t = {"fresh_in": 0, "cache_read": 0, "out": 0}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if '"usage"' not in line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") != "assistant":
                continue
            u = ev.get("message", {}).get("usage")
            if not isinstance(u, dict):
                continue
            t["fresh_in"] += (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
            t["cache_read"] += u.get("cache_read_input_tokens") or 0
            t["out"] += u.get("output_tokens") or 0
    return t


def aggregate_tokens():
    rows = list_sessions()
    per = []
    total = {"fresh_in": 0, "cache_read": 0, "out": 0}
    for r in rows:
        try:
            t = count_tokens_stream(r["path"])
        except Exception as e:
            print(f"  skip {r['session']}: {e}", file=sys.stderr)
            continue
        for k in total:
            total[k] += t[k]
        per.append((r, t))
    return per, total


def cmd_tokens():
    per, total = aggregate_tokens()
    if not per:
        print(f"No sessions found in {PROJECTS_DIR}", file=sys.stderr)
        return
    per.sort(key=lambda rt: rt[1]["out"], reverse=True)
    hdr = f'{"OUTPUT":>13}  {"FRESH IN":>13}  {"CACHE READ":>14}  SESSION'
    print(hdr)
    print("-" * len(hdr))
    for r, t in per:
        print(f'{t["out"]:>13,}  {t["fresh_in"]:>13,}  {t["cache_read"]:>14,}  '
              f'{r["project"]}/{r["session"][:8]}')
    print("-" * len(hdr))
    print(f'{total["out"]:>13,}  {total["fresh_in"]:>13,}  {total["cache_read"]:>14,}  '
          f'TOTAL ({len(per)} sessions)')
    grand = total["fresh_in"] + total["cache_read"] + total["out"]
    print()
    print(f'  Output tokens generated : {total["out"]:,}')
    print(f'  Fresh input tokens      : {total["fresh_in"]:,}')
    print(f'  Cache-read input tokens : {total["cache_read"]:,}')
    print(f'  Grand total (all-in)    : {grand:,}')


def resolve_path(pathlike):
    p = Path(pathlike)
    if p.exists():
        return p
    for proj in PROJECTS_DIR.glob("*"):
        cand = proj / f"{pathlike}.jsonl"
        if cand.exists():
            return cand
    return None


# --------------------------------------------------------------------------
# Digest: a compact, UUID-tagged text extract for skimming or subagent review.
# Streams the JSONL so it stays memory-safe on huge (100s of MB) transcripts.
# --------------------------------------------------------------------------

def iter_events_stream(path):
    """Yield events one at a time without loading the whole file into memory."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _truncate(s, n):
    s = s.strip()
    if len(s) > n:
        return s[:n].rstrip() + f" …[+{len(s) - n} chars]"
    return s


def _reindent(s, pad="    "):
    return s.replace("\n", "\n" + pad)


def render_user_content_plain(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                bits.append(b.get("text", ""))
        return "\n".join(bits)
    return ""


def _has_image(content):
    if not isinstance(content, list):
        return False
    for b in content:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "image":
            return True
        if b.get("type") == "tool_result" and isinstance(b.get("content"), list):
            for ib in b["content"]:
                if isinstance(ib, dict) and ib.get("type") == "image":
                    return True
    return False


def digest_entry(ev, idx, user_chars=1800, asst_chars=900, think_chars=500):
    """Compact text block for one event, or '' to skip."""
    etype = ev.get("type")
    uid = ev.get("uuid", "")
    ts = fmt_ts(ev.get("timestamp"))
    if etype == "user":
        content = ev.get("message", {}).get("content", "")
        if is_pure_tool_result(content):
            if any(isinstance(b, dict) and b.get("is_error") for b in content):
                return f"[{idx:05d}] {uid}  TOOL-ERROR  {ts}\n    (a tool returned an error)\n"
            return ""
        text = render_user_content_plain(content)
        img = "  [+IMAGE]" if _has_image(content) else ""
        if not text.strip() and not img:
            return ""
        if text.strip().startswith("<local-command-") or text.strip().startswith("<command-"):
            return ""
        return f"[{idx:05d}] {uid}  USER  {ts}{img}\n    {_reindent(_truncate(text, user_chars))}\n"
    if etype == "assistant":
        content = ev.get("message", {}).get("content", [])
        if not isinstance(content, list):
            return ""
        parts = []
        for b in content:
            bt = b.get("type")
            if bt == "thinking":
                th = b.get("thinking", "").strip()
                if th:
                    parts.append("THINK: " + _reindent(_truncate(th, think_chars)))
            elif bt == "text":
                tx = b.get("text", "").strip()
                if tx:
                    parts.append("SAY: " + _reindent(_truncate(tx, asst_chars)))
            elif bt == "tool_use":
                name = b.get("name", "?")
                inp = b.get("input", {})
                summ = ""
                if isinstance(inp, dict):
                    for k in ("command", "file_path", "path", "description",
                              "prompt", "query", "pattern", "url", "old_string"):
                        v = inp.get(k)
                        if isinstance(v, str) and v.strip():
                            summ = " ".join(v.split())[:130]
                            break
                parts.append(f"TOOL[{esc_off(name)}]: {summ}")
        if not parts:
            return ""
        return f"[{idx:05d}] {uid}  ASSISTANT  {ts}\n    " + "\n    ".join(parts) + "\n"
    return ""


def esc_off(s):
    return "" if s is None else str(s)


def cmd_digest(pathlike, output):
    path = resolve_path(pathlike)
    if path is None:
        print(f"Not found: {pathlike}", file=sys.stderr)
        sys.exit(1)
    header = (
        f"# Digest of {path.name}\n"
        f"# Each block: [index] <uuid>  ROLE  time\n"
        f"#   USER = the human's message; ASSISTANT lines are THINK / SAY / TOOL[name].\n"
        f"#   Tool *results* are omitted (only errors noted). [+IMAGE] marks attached images.\n"
        f"#   To bookmark a moment, record its <uuid>.\n\n"
    )
    n = 0
    parts = [header]
    for idx, ev in enumerate(iter_events_stream(path)):
        entry = digest_entry(ev, idx)
        if entry:
            parts.append(entry)
            n += 1
    body = "\n".join(parts)
    if output == "-":
        sys.stdout.write(body)
    else:
        Path(output).write_text(body, encoding="utf-8")
        print(f"Wrote {output}  ({n} entries, {len(body):,} chars from {path.name})")


# --------------------------------------------------------------------------
# Bookmarks: bookmarks.json -> in-page highlights + a bookmarks.html index.
# --------------------------------------------------------------------------

BOOKMARKS_FILE = Path(__file__).resolve().parent / "bookmarks.json"


def load_bookmarks(path=None):
    p = Path(path) if path else BOOKMARKS_FILE
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  warning: could not parse {p}: {e}", file=sys.stderr)
        return []
    if isinstance(data, dict):
        data = data.get("bookmarks", [])
    return data if isinstance(data, list) else []


def bookmarks_by_session(bms):
    out = {}
    for bm in bms:
        s = bm.get("session", "")
        if s:
            out.setdefault(s, {})[bm.get("uuid", "")] = bm
    return out


def _html_title(html_file):
    try:
        with open(html_file, encoding="utf-8") as fh:
            head = fh.read(4096)
        m = re.search(r"<title>(.*?)</title>", head, re.S)
        if m:
            return html.unescape(m.group(1).strip())
    except Exception:
        pass
    return html_file.stem


def build_bookmarks_page(out_dir, bookmarks):
    out = Path(out_dir)
    by_sess = {}
    for bm in bookmarks:
        by_sess.setdefault((bm.get("project", ""), bm.get("session", "")), []).append(bm)
    groups = []
    total = 0
    for (proj, sess), bms in sorted(by_sess.items()):
        rel = f"{proj}/{sess}.html"
        html_file = out / proj / f"{sess}.html"
        title = _html_title(html_file) if html_file.exists() else sess
        rows = []
        for bm in sorted(bms, key=lambda b: b.get("idx", 1 << 60)):
            cat = bm.get("category", "")
            cat_html = f'<span class="cat">{esc(cat)}</span> ' if cat else ""
            note = bm.get("note", "")
            quote = bm.get("quote", "")
            note_html = f'<div class="note">{esc(note)}</div>' if note else ""
            quote_html = f'<div class="quote">{esc(quote)}</div>' if quote else ""
            rows.append(
                f'<div class="bm-item">{cat_html}'
                f'<a href="{esc(rel)}#msg-{esc(bm.get("uuid", ""))}">{esc(bm.get("title", "Bookmark"))}</a>'
                f'{note_html}{quote_html}</div>'
            )
        total += len(bms)
        groups.append(
            f'<div class="bm-group"><h2><a href="{esc(rel)}" '
            f'style="text-decoration:none;color:inherit">{esc(title)}</a></h2>'
            f'<div class="ses-meta">{esc(proj)} · {len(bms)} bookmarks</div>'
            f'{"".join(rows)}</div>'
        )
    page = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bookmarks</title>
<style>{CSS}</style>
</head><body><div class="container">
<header><h1>★ Bookmarks</h1>
<div class="meta">{total} highlights across {len(by_sess)} sessions ·
<a href="index.html" style="color:var(--accent)">all transcripts</a></div></header>
{"".join(groups)}
</div></body></html>
"""
    (out / "bookmarks.html").write_text(page, encoding="utf-8")
    return total


def cmd_render(pathlike, output, show_attachments=False):
    path = resolve_path(pathlike)
    if path is None:
        print(f"Not found: {pathlike}", file=sys.stderr)
        sys.exit(1)
    events = parse_jsonl(path)
    sid = next((ev.get("sessionId") for ev in events if ev.get("sessionId")), path.stem)
    bms = bookmarks_by_session(load_bookmarks()).get(sid, {})
    out_html = render_html(events, path.stem, show_attachments=show_attachments, bookmarks=bms)
    if output == "-":
        sys.stdout.write(out_html)
    else:
        Path(output).write_text(out_html, encoding="utf-8")
        print(f"Wrote {output}  ({len(events)} events, {len(bms)} bookmarks, from {path})")


def cmd_render_all(out_dir, show_attachments=False, only=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = list_sessions()
    if not rows:
        print(f"No sessions found in {PROJECTS_DIR}", file=sys.stderr)
        return
    if only:
        rows = [r for r in rows
                if any(o.lower() in r["project"].lower() or o.lower() in r["session"].lower()
                       for o in only)]
        if not rows:
            print(f"No sessions matched --only {only}", file=sys.stderr)
            return

    all_bms = load_bookmarks()
    by_sess = bookmarks_by_session(all_bms)

    items = []
    agg_total = {"fresh_in": 0, "cache_read": 0, "out": 0}
    for r in rows:
        try:
            events = parse_jsonl(r["path"])
        except Exception as e:
            print(f"  skip {r['session']}: {e}", file=sys.stderr)
            continue
        if not events:
            continue
        title = session_title(events, r["project"]) or r["session"]
        bms = by_sess.get(r["session"], {})
        out_html = render_html(events, r["session"], show_attachments=show_attachments,
                               project_dir_name=r["project"], bookmarks=bms)
        sub = out / r["project"]
        sub.mkdir(exist_ok=True)
        outfile = sub / f"{r['session']}.html"
        outfile.write_text(out_html, encoding="utf-8")
        items.append((r, title, outfile.relative_to(out), len(bms)))
        try:
            t = count_tokens_stream(r["path"])
            for k in agg_total:
                agg_total[k] += t[k]
        except Exception:
            pass
        print(f"  · {r['project']}/{r['session'][:8]}"
              + (f"  ({len(bms)}★)" if bms else ""))

    n_bm = build_bookmarks_page(out, all_bms) if all_bms else 0

    # In a focused --only run, leave the existing full index.html untouched.
    if only:
        print(f"Rendered {len(items)} session(s) to {out}/ "
              f"(index.html left as-is; bookmarks.html has {n_bm})")
        return

    bm_link = (f' · <a href="bookmarks.html" style="color:var(--accent)">★ {n_bm} bookmarks</a>'
               if n_bm else "")
    items_html = []
    for r, title, rel, nb in items:
        star = f' <span class="cat">★ {nb}</span>' if nb else ""
        items_html.append(
            f'<li><a href="{esc(str(rel))}">{esc(title)}</a>{star}'
            f'<div class="sub">{esc(r["project"])} · {r["mtime"]:%Y-%m-%d %H:%M} · {r["size"]:,} bytes · '
            f'<code>{esc(r["session"][:8])}</code></div></li>'
        )
    index_html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code transcripts</title>
<style>{CSS}</style>
</head><body><div class="container">
<header><h1>Claude Code transcripts</h1>
<div class="meta">{len(items)} sessions · {esc(str(PROJECTS_DIR))}{bm_link}</div>
<div class="stats">
<div class="stat"><div class="stat-num">{len(items):,}</div><div class="stat-lbl">sessions</div></div>
<div class="stat"><div class="stat-num">{agg_total["out"]:,}</div><div class="stat-lbl">tokens out</div></div>
<div class="stat"><div class="stat-num">{agg_total["fresh_in"]:,}</div><div class="stat-lbl">fresh tokens in</div></div>
<div class="stat"><div class="stat-num">{agg_total["cache_read"]:,}</div><div class="stat-lbl">cache-read tokens</div></div>
<div class="stat"><div class="stat-num">{(agg_total["out"]+agg_total["fresh_in"]+agg_total["cache_read"]):,}</div><div class="stat-lbl">grand total</div></div>
</div></header>
<ul class="idx">{''.join(items_html)}</ul>
</div></body></html>
"""
    (out / "index.html").write_text(index_html, encoding="utf-8")
    print(f"Wrote {len(items)} sessions to {out}/  (open {out}/index.html)"
          + (f", {n_bm} bookmarks" if n_bm else ""))


def main():
    p = argparse.ArgumentParser(
        description="Render Claude Code JSONL transcripts as readable HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("list", help="list all sessions across projects")
    sub.add_parser("tokens", help="sum token usage across all sessions")

    pr = sub.add_parser("render", help="render one transcript to HTML")
    pr.add_argument("path", help="path to a .jsonl file or a session id")
    pr.add_argument("-o", "--output", default="transcript.html",
                    help="output HTML (default: transcript.html, '-' for stdout)")
    pr.add_argument("--attachments", action="store_true",
                    help="include system attachment events (skill listings, reminders, etc.)")

    pa = sub.add_parser("all", help="render every transcript and an index page")
    pa.add_argument("-o", "--output", default="./transcripts-html",
                    help="output directory (default: ./transcripts-html)")
    pa.add_argument("--attachments", action="store_true",
                    help="include system attachment events")
    pa.add_argument("--only", action="append", default=None, metavar="SUBSTR",
                    help="only render sessions whose project/id contains SUBSTR "
                         "(repeatable; leaves index.html untouched)")

    pd = sub.add_parser("digest", help="compact UUID-tagged text extract (for skimming/subagents)")
    pd.add_argument("path", help="path to a .jsonl file or a session id")
    pd.add_argument("-o", "--output", default="-",
                    help="output text file (default: stdout)")

    pb = sub.add_parser("bookmarks", help="(re)build bookmarks.html from bookmarks.json")
    pb.add_argument("-o", "--output", default="./transcripts-html",
                    help="output directory containing the rendered sessions")

    args = p.parse_args()
    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "tokens":
        cmd_tokens()
    elif args.cmd == "render":
        cmd_render(args.path, args.output, show_attachments=args.attachments)
    elif args.cmd == "all":
        cmd_render_all(args.output, show_attachments=args.attachments, only=args.only)
    elif args.cmd == "digest":
        cmd_digest(args.path, args.output)
    elif args.cmd == "bookmarks":
        n = build_bookmarks_page(args.output, load_bookmarks())
        print(f"Wrote {args.output}/bookmarks.html  ({n} bookmarks)")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
