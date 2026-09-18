#!/usr/bin/env python3
"""GitHub 主页极简黑白灰资产生成器。

读取 scripts/data.json，生成 assets/ 下所有 SVG（亮色 + 暗色双主题），
并输出 overview-*.svg 供整体预览。

用法:
    python3 scripts/build.py            # 使用现有 data.json 生成资产
    python3 scripts/build.py --fetch    # 先调用 GitHub API 刷新 data.json 再生成
"""

import json
import os
import sys
import urllib.request
from datetime import date
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "scripts", "data.json")
ASSETS_DIR = os.path.join(ROOT, "assets")
WIDTH = 880

SERIF = "Georgia, 'Nimbus Roman', 'Times New Roman', serif"
SANS = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"

THEMES = {
    "light": {
        "page": "#ffffff",
        "chrome_bg": "#fafafa",
        "card": "#ffffff",
        "border": "#e4e4e7",
        "border_strong": "#d4d4d8",
        "text900": "#0a0a0a",
        "text700": "#404040",
        "muted": "#71717a",
        "text400": "#858585",
        "text300": "#a1a1aa",
        "sep_dot": "#d4d4d4",
        "chrome_dot": "#e5e5e5",
        "grid0": "#fafafa",
        "grid1": "#e5e5e5",
        "grid2": "#a3a3a3",
        "grid3": "#3f3f46",
        "mono_fill": "#18181b",
        "mono_text": "#fafafa",
    },
    "dark": {
        "page": "#0d1117",
        "chrome_bg": "#161b22",
        "card": "#161b22",
        "border": "#30363d",
        "border_strong": "#3d444d",
        "text900": "#f0f6fc",
        "text700": "#c9d1d9",
        "muted": "#8b949e",
        "text400": "#8b949e",
        "text300": "#6e7681",
        "sep_dot": "#3d444d",
        "chrome_dot": "#30363d",
        "grid0": "#161b22",
        "grid1": "#30363d",
        "grid2": "#6e7681",
        "grid3": "#c9d1d9",
        "mono_fill": "#f0f6fc",
        "mono_text": "#0d1117",
    },
}

# lucide 风格线性图标，24x24 viewBox
ICONS = {
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "fork": '<circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9"/><path d="M12 12v3"/>',
    "book": '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/>',
    "github": '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
}

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def tw(text, size, kind="sans", spacing=0.0):
    """粗略估算文本渲染宽度（latin 按平均字宽，CJK 按 1em）。"""
    latin = {"mono": 0.62, "sans": 0.52, "serif": 0.50}[kind]
    w = 0.0
    for ch in text:
        w += (1.0 if ord(ch) > 0x2E7F else latin) * size
    return w + spacing * max(len(text) - 1, 0)


def icon(name, x, y, size, color, stroke=2.0):
    s = size / 24.0
    sw = stroke * (size / 24.0) * (24.0 / size) * (size / 12.0 if size <= 14 else 1.0)
    sw = max(1.4, stroke * size / 24.0 * 1.15)
    return (
        f'<g transform="translate({x},{y}) scale({s})" fill="none" '
        f'stroke="{color}" stroke-width="{sw:.2f}" stroke-linecap="round" '
        f'stroke-linejoin="round">{ICONS[name]}</g>'
    )


def wrap_svg(inner, height, theme, extra=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 {extra}0 {WIDTH} {height}" font-family="{SANS}">{inner}</svg>'
    )


# ---------- 各区块渲染 ----------


def render_chrome(t, d):
    h = 40
    p = d["profile"]
    inner = [
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{h - 1}" rx="12" fill="{t["chrome_bg"]}" stroke="{t["border"]}"/>',
        f'<circle cx="20" cy="20" r="4" fill="{t["chrome_dot"]}"/>',
        f'<circle cx="36" cy="20" r="4" fill="{t["chrome_dot"]}"/>',
        f'<circle cx="52" cy="20" r="4" fill="{t["chrome_dot"]}"/>',
        icon("lock", 70, 14, 12, t["text300"]),
        f'<text x="90" y="24.5" font-family="{MONO}" font-size="12" fill="{t["muted"]}">github.com / {escape(p["login"])}</text>',
    ]
    return "".join(inner), h


def render_hero(t, d):
    p = d["profile"]
    parts = []
    height = 0
    # monogram
    parts.append(f'<rect x="392" y="0" width="96" height="96" rx="14" fill="{t["mono_fill"]}"/>')
    parts.append(
        f'<text x="440" y="50" text-anchor="middle" dominant-baseline="central" '
        f'font-family="{SERIF}" font-size="54" letter-spacing="-1" fill="{t["mono_text"]}">AY</text>'
    )
    height = 96
    # display name: alex_yunyun（下划线用浅灰）
    y_name = height + 28 + 46
    parts.append(
        f'<text x="440" y="{y_name}" text-anchor="middle" font-family="{SERIF}" font-size="64" '
        f'letter-spacing="-0.5" fill="{t["text900"]}">alex'
        f'<tspan fill="{t["text300"]}">_</tspan>yunyun</text>'
    )
    height = y_name + 8
    # personal quote（衬线斜体，中间点分隔）
    y_quote = height + 18 + 24
    parts.append(
        f'<text x="440" y="{y_quote}" text-anchor="middle" font-family="{SERIF}" font-style="italic" '
        f'font-size="22" fill="{t["text700"]}">Building small tools'
        f'<tspan fill="{t["text300"]}" font-style="normal"> · </tspan>for quiet everyday problems'
        f'<tspan fill="{t["text300"]}" font-style="normal"> · </tspan>one commit at a time</text>'
    )
    height = y_quote + 6
    # meta 行：joined / repos / stars
    y_meta = height + 22 + 10
    items = [
        ("calendar", f'joined {p["joined"]}'),
        ("book", f'{p["public_repos"]} public repos'),
        ("star", f'{p["total_stars"]} stars earned'),
    ]
    gap = 18
    widths = [14 + 6 + tw(label, 14, "sans") for _, label in items]
    total = sum(widths) + gap * (len(items) - 1)
    x = (WIDTH - total) / 2
    for i, ((ic, label), w) in enumerate(zip(items, widths)):
        parts.append(icon(ic, x, y_meta - 12, 14, t["text300"]))
        parts.append(
            f'<text x="{x + 20:.1f}" y="{y_meta}" font-family="{SANS}" font-size="14" '
            f'fill="{t["muted"]}">{escape(label)}</text>'
        )
        if i < len(items) - 1:
            cx = x + w + gap / 2
            parts.append(f'<circle cx="{cx:.1f}" cy="{y_meta - 5}" r="1.6" fill="{t["sep_dot"]}"/>')
        x += w + gap
    height = y_meta + 8
    # stats pill
    stats = [
        (str(p["followers"]), "followers"),
        (str(p["following"]), "following"),
        (str(p["total_stars"]), "stars"),
    ]
    pad_v, pad_h, stat_pad = 14, 24, 18
    stat_ws = [tw(v, 15, "mono") + 8 + tw(l, 13, "mono") for v, l in stats]
    pill_w = pad_h * 2 + sum(stat_ws) + stat_pad * 2 * (len(stats) - 1)
    pill_h = pad_v * 2 + 19
    pill_y = height + 36
    pill_x = (WIDTH - pill_w) / 2
    parts.append(
        f'<rect x="{pill_x:.1f}" y="{pill_y}" width="{pill_w:.1f}" height="{pill_h}" rx="12" '
        f'fill="{t["card"]}" stroke="{t["border"]}"/>'
    )
    sx = pill_x + pad_h + stat_pad
    for i, ((v, l), w) in enumerate(zip(stats, stat_ws)):
        parts.append(
            f'<text x="{sx:.1f}" y="{pill_y + pad_v + 14}" font-family="{MONO}" font-size="15" '
            f'font-weight="500" fill="{t["text900"]}">{escape(v)}'
            f'<tspan dx="8" font-size="13" font-weight="400" fill="{t["text400"]}">{escape(l)}</tspan></text>'
        )
        if i < len(stats) - 1:
            dx = sx + w + stat_pad
            parts.append(
                f'<line x1="{dx:.1f}" y1="{pill_y + 13}" x2="{dx:.1f}" y2="{pill_y + pill_h - 13}" '
                f'stroke="{t["border"]}"/>'
            )
        sx += w + stat_pad * 2
    height = pill_y + pill_h
    return "".join(parts), height


def render_section_head(t, title, hint):
    h = 40
    inner = [
        f'<text x="0" y="22" font-family="{SERIF}" font-size="22" fill="{t["text900"]}">{escape(title)}</text>',
        f'<text x="{WIDTH}" y="24" text-anchor="end" font-family="{MONO}" font-size="11" '
        f'letter-spacing="1.5" fill="{t["text400"]}">{escape(hint.upper())}</text>',
        f'<line x1="0" y1="39" x2="{WIDTH}" y2="39" stroke="{t["border"]}"/>',
    ]
    return "".join(inner), h


def render_repo_card(t, repo):
    h = 148
    name = f'{repo["full_name"]}'
    parts = [
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{h - 1}" rx="12" fill="{t["card"]}" stroke="{t["border"]}"/>',
        icon("book", 28, 26, 14, t["text300"]),
        f'<text x="50" y="37" font-family="{MONO}" font-size="14" font-weight="500" fill="{t["text900"]}">{escape(name)}</text>',
        f'<text x="{WIDTH - 28}" y="36" text-anchor="end" font-family="{MONO}" font-size="11" '
        f'letter-spacing="1.3" fill="{t["text400"]}">PINNED</text>',
        f'<text x="28" y="66" font-family="{SANS}" font-size="14" fill="{t["muted"]}">{escape(repo["description"])}</text>',
    ]
    y = 104
    x = 28
    parts.append(f'<circle cx="{x + 4}" cy="{y - 4}" r="4.5" fill="{t["mono_fill"]}"/>')
    parts.append(
        f'<text x="{x + 14}" y="{y}" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{escape(repo["language"])}</text>'
    )
    x += 14 + tw(repo["language"], 12, "mono") + 22
    parts.append(icon("star", x, y - 11, 12, t["text300"]))
    parts.append(
        f'<text x="{x + 17}" y="{y}" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{repo["stars"]}</text>'
    )
    x += 17 + tw(str(repo["stars"]), 12, "mono") + 20
    parts.append(icon("fork", x, y - 11, 12, t["text300"]))
    parts.append(
        f'<text x="{x + 17}" y="{y}" font-family="{MONO}" font-size="12" fill="{t["muted"]}">{repo["forks"]}</text>'
    )
    return "".join(parts), h


def render_tech_stack(t, tags):
    chip_h, pad_x, gap = 30, 12, 10
    rows, x, y = [], 0, 0
    for tag in tags:
        w = tw(tag, 12, "mono") + pad_x * 2
        if x + w > WIDTH:
            rows.append(y)
            x, y = 0, y + chip_h + 10
        x += w + gap
    rows.append(y)
    h = rows[-1] + chip_h
    parts = []
    x, y = 0, 0
    for tag in tags:
        w = tw(tag, 12, "mono") + pad_x * 2
        if x + w > WIDTH:
            x, y = 0, y + chip_h + 10
        parts.append(
            f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{chip_h}" rx="6" fill="{t["card"]}" stroke="{t["border"]}"/>'
        )
        parts.append(
            f'<text x="{x + pad_x:.1f}" y="{y + 19}" font-family="{MONO}" font-size="12" '
            f'fill="{t["text700"]}">{escape(tag)}</text>'
        )
        x += w + gap
    return "".join(parts), h


def render_contributions(t, d):
    c = d["contributions"]
    days = c["days"]
    pad = 28
    head_h = 46
    grid_w = WIDTH - pad * 2
    gap = 3
    cols = 53
    cell = (grid_w - (cols - 1) * gap) / cols
    grid_h = cell * 7 + gap * 6
    axis_y = pad + head_h + grid_h + 16
    legend_y = axis_y + 20
    h = legend_y + 16

    def level(count):
        if count <= 0:
            return t["grid0"]
        if count <= 2:
            return t["grid1"]
        if count <= 6:
            return t["grid2"]
        return t["grid3"]

    parts = [
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{h - 1}" rx="12" fill="{t["card"]}" stroke="{t["border"]}"/>',
        f'<text x="{pad}" y="{pad + 18}" font-family="{SERIF}" font-size="16" fill="{t["text900"]}">'
        f'{c["total"]} contributions in the last year</text>',
        f'<text x="{WIDTH - pad}" y="{pad + 18}" text-anchor="end" font-family="{MONO}" font-size="12" '
        f'fill="{t["muted"]}">longest streak <tspan fill="{t["text900"]}">{c["longest_streak"]}d</tspan>'
        f' · current <tspan fill="{t["text900"]}">{c["current_streak"]}d</tspan></text>',
    ]
    gx, gy = pad, pad + head_h
    for i, day in enumerate(days):
        col, row = i // 7, i % 7
        parts.append(
            f'<rect x="{gx + col * (cell + gap):.2f}" y="{gy + row * (cell + gap):.2f}" '
            f'width="{cell:.2f}" height="{cell:.2f}" rx="2" fill="{level(day["count"])}"/>'
        )
    # 月份刻度：每月首次出现的列打标签
    labeled = []
    for col in range(cols):
        idx = col * 7
        if idx >= len(days):
            break
        month = int(days[idx]["date"][5:7]) - 1
        if month not in labeled:
            labeled.append(month)
            parts.append(
                f'<text x="{gx + col * (cell + gap):.1f}" y="{axis_y}" font-family="{MONO}" font-size="10" '
                f'fill="{t["text400"]}">{MONTHS[month]}</text>'
            )
    # 图例
    lx = pad
    parts.append(f'<text x="{lx}" y="{legend_y}" font-family="{MONO}" font-size="11" fill="{t["text400"]}">less</text>')
    lx += tw("less", 11, "mono") + 8
    for i, key in enumerate(["grid0", "grid1", "grid2", "grid3"]):
        parts.append(
            f'<rect x="{lx:.1f}" y="{legend_y - 9}" width="10" height="10" rx="2" fill="{t[key]}"/>'
        )
        lx += 14
    parts.append(f'<text x="{lx:.1f}" y="{legend_y}" font-family="{MONO}" font-size="11" fill="{t["text400"]}">more</text>')
    return "".join(parts), h


def render_footer(t, d):
    p = d["profile"]
    updated = d["generated_at"]
    ym, mm = updated[:4], int(updated[5:7])
    stamp = f"last updated · {MONTHS[mm - 1]} {ym}"
    est = f'{p["login"]} · est. {p["created_year"]}'
    y_line, y_row = 34, 66
    parts = [
        f'<line x1="0" y1="0" x2="{WIDTH}" y2="0" stroke="{t["border"]}"/>',
        f'<text x="0" y="{y_line}" font-family="{SERIF}" font-style="italic" font-size="16" fill="{t["text700"]}">'
        f'“Less, but better.” — Dieter Rams, faintly overheard in every commit.</text>',
        icon("github", 0, y_row - 12, 12, t["text300"]),
        f'<text x="18" y="{y_row}" font-family="{MONO}" font-size="11" letter-spacing="0.7" '
        f'fill="{t["text400"]}">{escape(est).upper()}</text>',
        icon("calendar", WIDTH - 12 - tw(stamp.upper(), 11, "mono", 0.7) - 8, y_row - 12, 12, t["text300"]),
        f'<text x="{WIDTH}" y="{y_row}" text-anchor="end" font-family="{MONO}" font-size="11" '
        f'letter-spacing="0.7" fill="{t["text400"]}">{escape(stamp).upper()}</text>',
    ]
    return "".join(parts), y_row + 12


# ---------- 组装 ----------


def build_assets(d):
    os.makedirs(ASSETS_DIR, exist_ok=True)
    tech_tags = ["TypeScript", "Vue", "JavaScript", "Python", "Java", "Flask", "ECharts", "Vercel"]
    renders = {
        "chrome": lambda t: render_chrome(t, d),
        "hero": lambda t: render_hero(t, d),
        "section-featured": lambda t: render_section_head(t, "Featured", "03 / pinned"),
        "section-tech-stack": lambda t: render_section_head(t, "Tech stack", "tools I keep coming back to"),
        "section-contributions": lambda t: render_section_head(t, "Contributions", "last 53 weeks"),
        "tech-stack": lambda t: render_tech_stack(t, tech_tags),
        "contributions": lambda t: render_contributions(t, d),
        "footer": lambda t: render_footer(t, d),
    }
    for repo in d["repos"]:
        slug = repo["name"].lower()
        renders[f"repo-{slug}"] = lambda t, r=repo: render_repo_card(t, r)

    sizes = {}
    for theme_name, theme in THEMES.items():
        for name, fn in renders.items():
            inner, h = fn(theme)
            sizes[name] = h
            path = os.path.join(ASSETS_DIR, f"{name}-{theme_name}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(wrap_svg(inner, h, theme))
            print(f"  wrote assets/{name}-{theme_name}.svg ({h}px)")

    # 整体预览图（双主题）
    for theme_name, theme in THEMES.items():
        seq = [
            ("chrome", 0),
            ("hero", 64),
            ("section-featured", 40),
            ("repo-bookmanagesystem", 16),
            ("repo-unicode-symbols", 16),
            ("repo-jwordscards", 16),
            ("section-tech-stack", 64),
            ("tech-stack", 24),
            ("section-contributions", 64),
            ("contributions", 24),
            ("footer", 72),
        ]
        total_h = sum(sizes[n] for n, _ in seq) + sum(g for _, g in seq) + 40
        body = [f'<rect width="{WIDTH}" height="{total_h}" fill="{theme["page"]}"/>']
        y = 20
        for name, g in seq:
            body.append(f'<g transform="translate(0,{y})">{renders[name](theme)[0]}</g>')
            y += sizes[name] + g
        path = os.path.join(ASSETS_DIR, f"overview-{theme_name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(wrap_svg("".join(body), total_h, theme))
        print(f"  wrote assets/overview-{theme_name}.svg ({total_h}px)")


# ---------- 数据刷新 ----------


def api_get(url, token=None):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-builder"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def fetch_data(login="alexyunyun"):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    user = api_get(f"https://api.github.com/users/{login}", token)
    repos = api_get(f"https://api.github.com/users/{login}/repos?per_page=100&sort=updated", token)
    query = (
        "query($login:String!){user(login:$login){contributionsCollection"
        "{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday}}}}}"
    )
    payload = json.dumps({"query": query, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-builder",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req) as resp:
        gql = json.load(resp)
    cal = gql["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        {"date": dd["date"], "count": dd["contributionCount"], "weekday": dd["weekday"]}
        for w in cal["weeks"]
        for dd in w["contributionDays"]
    ]
    counts = [x["count"] for x in days]
    best = cur = 0
    for c in counts:
        cur = cur + 1 if c > 0 else 0
        best = max(best, cur)
    cur2 = 0
    for c in reversed(counts):
        if c > 0:
            cur2 += 1
        else:
            break
    featured = [
        {
            "name": r["name"],
            "full_name": r["full_name"],
            "url": r["html_url"],
            "description": (r["description"] or "").strip(),
            "language": r["language"] or "Code",
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
        }
        for r in sorted(repos, key=lambda r: (-r["stargazers_count"], r["name"]))[:3]
    ]
    return {
        "generated_at": date.today().isoformat(),
        "profile": {
            "login": user["login"],
            "name": user.get("name") or user["login"],
            "created_year": int(user["created_at"][:4]),
            "joined": MONTHS[int(user["created_at"][5:7]) - 1] + " " + user["created_at"][:4],
            "followers": user["followers"],
            "following": user["following"],
            "public_repos": user["public_repos"],
            "total_stars": sum(r["stargazers_count"] for r in repos),
        },
        "repos": featured,
        "contributions": {
            "total": cal["totalContributions"],
            "longest_streak": best,
            "current_streak": cur2,
            "days": days,
        },
    }


def main():
    if "--fetch" in sys.argv:
        print("fetching data from GitHub API ...")
        data = fetch_data()
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  wrote scripts/data.json ({len(data['contributions']['days'])} days)")
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    print("building assets ...")
    build_assets(data)
    print("done.")


if __name__ == "__main__":
    main()
