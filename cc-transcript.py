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
  --bg: #f7f7f5; --fg: #1a1a1a; --muted: #6b6b6b;
  --user-bg: #e7f0ff; --assistant-bg: #ffffff;
  --thinking-bg: #f0eaf7; --tool-bg: #fff8e7;
  --tool-result-bg: #f4f4f2;
  --code-bg: #2b2b2b; --code-fg: #f5f5f5;
  --border: #e0e0e0; --accent: #b45309;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #181818; --fg: #e8e8e8; --muted: #9a9a9a;
    --user-bg: #1f3556; --assistant-bg: #232323;
    --thinking-bg: #2c1f3d; --tool-bg: #3d2f0f;
    --tool-result-bg: #1f1f1f;
    --code-bg: #0f0f0f; --code-fg: #e8e8e8;
    --border: #333; --accent: #f59e0b;
  }
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  margin: 0; padding: 24px 16px;
  background: var(--bg); color: var(--fg);
  line-height: 1.55;
}
.container { max-width: 920px; margin: 0 auto; }
header { margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
header h1 { margin: 0 0 4px 0; font-size: 20px; }
header .meta { color: var(--muted); font-size: 12px; word-break: break-all; }
.msg { margin: 12px 0; padding: 14px 18px; border-radius: 12px; border: 1px solid var(--border); }
.msg.user { background: var(--user-bg); }
.msg.assistant { background: var(--assistant-bg); }
.role {
  font-weight: 600; font-size: 11px; text-transform: uppercase;
  color: var(--muted); margin-bottom: 8px; letter-spacing: 0.6px;
}
.role .ts { font-weight: 400; text-transform: none; margin-left: 8px; color: var(--muted); }
.msg p { margin: 6px 0; }
.msg pre {
  background: var(--code-bg); color: var(--code-fg);
  padding: 12px; border-radius: 8px; overflow-x: auto;
  font-size: 12.5px; line-height: 1.5;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: pre-wrap; word-break: break-word;
}
.msg :not(pre) > code {
  background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 4px;
  font-size: 0.92em; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  .msg :not(pre) > code { background: rgba(255,255,255,0.08); }
}
details {
  margin: 8px 0; border: 1px solid var(--border);
  border-radius: 8px; overflow: hidden;
}
details > summary {
  padding: 8px 12px; cursor: pointer;
  font-size: 13px; font-weight: 500; user-select: none;
  list-style: none;
}
details > summary::-webkit-details-marker { display: none; }
details[open] > summary { border-bottom: 1px solid var(--border); }
details > .body { padding: 10px 12px; }
.thinking { background: var(--thinking-bg); }
.thinking > summary::before { content: "🧠  "; }
.tool { background: var(--tool-bg); }
.tool > summary::before { content: "🔧  "; }
.tool-result { background: var(--tool-result-bg); margin-top: 8px; }
.tool-result > summary::before { content: "↳  "; }
.tool-name { font-weight: 600; color: var(--accent); }
.muted { color: var(--muted); font-weight: 400; }
.attachment { background: var(--tool-result-bg); font-size: 12px; }
.attachment > summary::before { content: "ⓘ  "; }
.idx { list-style: none; padding: 0; margin: 0; }
.idx li {
  padding: 12px 16px; border: 1px solid var(--border);
  border-radius: 8px; margin: 8px 0; background: var(--assistant-bg);
}
.idx li a { color: var(--fg); text-decoration: none; font-weight: 500; }
.idx li a:hover { color: var(--accent); }
.idx .sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
.stats {
  display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px;
}
.stat {
  background: var(--assistant-bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 8px 14px; min-width: 84px; text-align: center;
}
.stat-num { font-size: 19px; font-weight: 700; }
.stat-lbl {
  font-size: 10.5px; text-transform: uppercase; color: var(--muted);
  letter-spacing: 0.5px; margin-top: 2px;
}
.tool-breakdown { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
.tool-chip {
  font-size: 12px; background: var(--tool-bg);
  border: 1px solid var(--border); border-radius: 999px; padding: 3px 10px;
}
.tool-chip b { color: var(--accent); }
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


def render_event(ev, tool_results, show_attachments):
    etype = ev.get("type")
    ts = fmt_ts(ev.get("timestamp"))

    if etype in ("permission-mode", "file-history-snapshot"):
        return ""

    if etype == "attachment":
        if not show_attachments:
            return ""
        att = ev.get("attachment", {})
        atype = att.get("type", "attachment")
        body = json.dumps(att, indent=2, ensure_ascii=False)
        return (
            f'<details class="msg attachment"><summary>system: {esc(atype)} '
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
            f'<div class="msg user"><div class="role">user '
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
            f'<div class="msg assistant"><div class="role">assistant '
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
    for ev in events:
        if ev.get("type") == "user":
            c = ev.get("message", {}).get("content")
            if isinstance(c, str) and c.strip():
                return c.strip()
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


def render_html(events, title, show_attachments=False):
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
    for ev in events:
        chunk = render_event(ev, tool_results, show_attachments)
        if chunk:
            body_parts.append(chunk)

    first = first_user_prompt(events)
    cwd = next((ev["cwd"] for ev in events if ev.get("cwd")), "")
    sid = next((ev["sessionId"] for ev in events if ev.get("sessionId")), "")
    started = next((fmt_ts(ev["timestamp"], full=True) for ev in events if ev.get("timestamp")), "")

    title_text = (first[:80] + ("…" if len(first) > 80 else "")) if first else title
    stats_html = render_stats(compute_stats(events))

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


def cmd_render(pathlike, output, show_attachments=False):
    path = resolve_path(pathlike)
    if path is None:
        print(f"Not found: {pathlike}", file=sys.stderr)
        sys.exit(1)
    events = parse_jsonl(path)
    out_html = render_html(events, path.stem, show_attachments=show_attachments)
    if output == "-":
        sys.stdout.write(out_html)
    else:
        Path(output).write_text(out_html, encoding="utf-8")
        print(f"Wrote {output}  ({len(events)} events from {path})")


def cmd_render_all(out_dir, show_attachments=False):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = list_sessions()
    if not rows:
        print(f"No sessions found in {PROJECTS_DIR}", file=sys.stderr)
        return
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
        out_html = render_html(events, r["session"], show_attachments=show_attachments)
        sub = out / r["project"]
        sub.mkdir(exist_ok=True)
        outfile = sub / f"{r['session']}.html"
        outfile.write_text(out_html, encoding="utf-8")
        items.append((r, first_user_prompt(events), outfile.relative_to(out)))
        try:
            t = count_tokens_stream(r["path"])
            for k in agg_total:
                agg_total[k] += t[k]
        except Exception:
            pass

    items_html = []
    for r, first, rel in items:
        title = (first[:120] + ("…" if len(first) > 120 else "")) if first else r["session"]
        items_html.append(
            f'<li><a href="{esc(str(rel))}">{esc(title)}</a>'
            f'<div class="sub">{esc(r["project"])} · {r["mtime"]:%Y-%m-%d %H:%M} · {r["size"]:,} bytes · '
            f'<code>{esc(r["session"])}</code></div></li>'
        )
    index_html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code transcripts</title>
<style>{CSS}</style>
</head><body><div class="container">
<header><h1>Claude Code transcripts</h1>
<div class="meta">{len(items)} sessions · {esc(str(PROJECTS_DIR))}</div>
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
    print(f"Wrote {len(items)} sessions to {out}/  (open {out}/index.html)")


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

    args = p.parse_args()
    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "tokens":
        cmd_tokens()
    elif args.cmd == "render":
        cmd_render(args.path, args.output, show_attachments=args.attachments)
    elif args.cmd == "all":
        cmd_render_all(args.output, show_attachments=args.attachments)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
