#!/usr/bin/env python3
"""把仓库里的 Markdown 编译成 site/ 下的静态站点（仅用标准库）。

用法： python3 scripts/build_site.py
依赖：无。产物： site/
"""
import html
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")

NAV = [
    ("index.html", "首页"),
    ("docs/01-architecture.html", "架构"),
    ("docs/02-message-dataflow.html", "数据流"),
    ("docs/03-protocols-and-runtime.html", "协议"),
    ("docs/04-troubleshooting.html", "排查"),
    ("docs/05-ecosystem.html", "生态"),
    ("diagrams/coze-desktop-agent-sequence.html", "时序图"),
    ("diagrams/coze-desktop-agent-architecture.html", "架构图"),
    ("diagrams/coze-device-agent-lifecycle.html", "生命周期图"),
]

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{base}assets/style.css">
</head>
<body>
<header class="topbar">
  <a class="brand" href="{base}index.html">Coze Agent Notes</a>
  <nav>{nav}</nav>
</header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">
  独立研究笔记 · 非官方文档 · 所有个人标识与密钥均已脱敏
</footer>
<script type="module">
  const mermaid = document.querySelectorAll('pre.mermaid');
  if (mermaid.length) {{
    const s = document.createElement('script');
    s.type = 'module';
    s.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    s.onload = () => window.mermaid?.run?.();
    document.head.appendChild(s);
  }}
</script>
</body>
</html>
"""


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def rewrite_links(t):
    t = re.sub(r"\]\((\./)?(docs/[A-Za-z0-9._-]+)\.md\)", r"](\2.html)", t)
    return t


def convert(md):
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]

        m = re.match(r"^```(\w*)\s*$", line)
        if m:
            lang = m.group(1)
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            body = html.escape("\n".join(buf))
            if lang == "mermaid":
                out.append('<pre class="mermaid">%s</pre>' % body)
            else:
                out.append('<pre><code class="lang-%s">%s</code></pre>' % (lang, body))
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl, txt = len(m.group(1)), m.group(2)
            out.append("<h%d>%s</h%d>" % (lvl, inline(txt), lvl))
            i += 1
            continue

        if re.match(r"^---+\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        if line.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join("<th>%s</th>" % inline(c) for c in header)
            trs = "".join(
                "<tr>" + "".join("<td>%s</td>" % inline(c) for c in r) + "</tr>" for r in rows
            )
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (th, trs))
            continue

        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % inline(x) for x in items))
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
            out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % inline(x) for x in items))
            continue

        if line.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % convert("\n".join(buf)))
            continue

        if not line.strip():
            i += 1
            continue

        buf = []
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|```|\||>|\s*[-*]\s|\s*\d+\.\s|---+\s*$)", lines[i]
        ):
            buf.append(lines[i])
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(buf)))

    return "\n".join(out)


def title_of(md):
    m = re.search(r"^#\s+(.*)$", md, re.M)
    return m.group(1).strip() if m else "Coze Agent Notes"


def nav_for(base, current):
    parts = []
    for href, label in NAV:
        cls = ' class="on"' if href == current else ""
        parts.append('<a href="%s%s"%s>%s</a>' % (base, href, cls, label))
    return "".join(parts)


def render(md, base, current):
    body = convert(rewrite_links(md))
    return PAGE.format(title=title_of(md), base=base, nav=nav_for(base, current), body=body)


def main():
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(os.path.join(SITE, "docs"))
    os.makedirs(os.path.join(SITE, "assets"))
    os.makedirs(os.path.join(SITE, "diagrams"))

    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(render(readme, "", "index.html"))

    for name in sorted(os.listdir(os.path.join(ROOT, "docs"))):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(ROOT, "docs", name), encoding="utf-8") as f:
            md = f.read()
        out = name[:-3] + ".html"
        with open(os.path.join(SITE, "docs", out), "w", encoding="utf-8") as f:
            f.write(render(md, "../", "docs/" + out))

    src = os.path.join(ROOT, "diagrams")
    for name in sorted(os.listdir(src)):
        if name.endswith((".html", ".png", ".svg")):
            shutil.copy(os.path.join(src, name), os.path.join(SITE, "diagrams", name))

    with open(os.path.join(ROOT, "assets", "style.css"), encoding="utf-8") as f:
        css = f.read()
    with open(os.path.join(SITE, "assets", "style.css"), "w", encoding="utf-8") as f:
        f.write(css)

    print("site/ 生成完成")
    for dirpath, _, files in os.walk(SITE):
        for fn in sorted(files):
            p = os.path.join(dirpath, fn)
            print("  %8d  %s" % (os.path.getsize(p), os.path.relpath(p, ROOT)))


if __name__ == "__main__":
    main()
