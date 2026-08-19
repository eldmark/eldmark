#!/usr/bin/env python3
"""Generate the animated terminal hero SVG for the profile README.

Two update frequencies live here on purpose:

  * The status panel (BUILDING / LAST PUSH / STATUS) is baked in at generation
    time from the GitHub API, so it only changes when the workflow runs.
  * The CRT project carousel is pure CSS inside the SVG and replays in the
    visitor's browser, so no workflow has to run to keep it moving.

Images are committed by hand under assets/projects/ and embedded as data URIs;
nothing here takes screenshots. Usage:

    generate_hero.py <github-user> [output.svg]
"""
import base64
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "assets" / "projects"

W, H = 940, 400
CARD_SECONDS = 5.0          # time on screen per project, transition included
BG = "#0d0e16"
PANEL = "#12131f"
LINE = "#1f2335"
CYAN = "#7dcfff"
BLUE = "#7aa2f7"
MAGENTA = "#bb9af7"
DIM = "#565f89"
FG = "#c0caf5"
GREEN = "#9ece6a"
TAGLINE = "> turning ideas into systems"


def gh(path):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout else None


def latest_push(user):
    """Most recent public push to a repo the user owns.

    Returns (repo, short sha, days since, push date).

    Pushes to repositories owned by somebody else (coursework, forks) are real
    activity but say little about what this profile is building, so they are
    skipped here.
    """
    for event in gh(f"users/{user}/events/public?per_page=100") or []:
        if event.get("type") != "PushEvent":
            continue
        if not event["repo"]["name"].startswith(f"{user}/"):
            continue
        sha = event["payload"].get("head")
        if not sha:
            continue
        when = datetime.strptime(event["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        days = (datetime.now(timezone.utc) - when).days
        return (
            event["repo"]["name"].split("/")[-1],
            sha[:7],
            days,
            when.strftime("%Y-%m-%d"),
        )
    return None


def data_uri(name):
    raw = (PROJECTS / name).read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def pct(seconds, total):
    return round(seconds / total * 100, 3)


def build_css(cards):
    total = CARD_SECONDS * len(cards)

    # One card cycle: hold, signal loss, CRT collapse, black, then wait its turn.
    hold, glitch, collapse, gone = 4.3, 4.45, 4.6, 4.8
    stops = [
        (0, "opacity:1;transform:scaleY(1) translateX(0)"),
        (hold, "opacity:1;transform:scaleY(1) translateX(0)"),
        (glitch, "opacity:1;transform:scaleY(1) translateX(3px)"),
        (collapse, "opacity:1;transform:scaleY(0.02) translateX(0)"),
        (4.7, "opacity:0.5;transform:scaleY(0.004) translateX(0)"),
        (gone, "opacity:0;transform:scaleY(0.004) translateX(0)"),
        (total, "opacity:0;transform:scaleY(0.004) translateX(0)"),
    ]
    card_frames = "\n".join(
        f"  {pct(t, total)}% {{ {rule}; }}" for t, rule in stops
    )

    # Noise burst sits between two cards: dead black, then digital snow.
    noise_stops = []
    for i in range(len(cards)):
        base = i * CARD_SECONDS
        noise_stops += [
            (base + 4.55, 0),
            (base + 4.75, 0.55),
            (base + 4.95, 0.18),
            (base + 5.05, 0),
        ]
    noise_frames = "\n".join(
        f"  {pct(t, total)}% {{ opacity:{o}; }}" for t, o in sorted(noise_stops)
    )

    lines = [
        "@keyframes card {", card_frames, "}",
        "@keyframes noise {", "  0% { opacity:0; }", noise_frames, "  100% { opacity:0; }", "}",
        "@keyframes blink { 0%,49% { opacity:1; } 50%,100% { opacity:0; } }",
        # Prompt: types the loading line, holds, then confirms.
        "@keyframes typing {",
        "  0% { clip-path: inset(0 100% 0 0); }",
        f"  {pct(0.6, total)}% {{ clip-path: inset(0 0 0 0); }}",
        "  100% { clip-path: inset(0 0 0 0); }",
        "}",
        "@keyframes msgload {",
        "  0% { opacity:1; }",
        f"  {pct(1.4, total)}% {{ opacity:1; }}",
        f"  {pct(1.5, total)}% {{ opacity:0; }}",
        "  100% { opacity:0; }",
        "}",
        "@keyframes msgok {",
        "  0% { opacity:0; }",
        f"  {pct(1.5, total)}% {{ opacity:0; }}",
        f"  {pct(1.6, total)}% {{ opacity:1; }}",
        f"  {pct(4.3, total)}% {{ opacity:1; }}",
        f"  {pct(4.4, total)}% {{ opacity:0; }}",
        "  100% { opacity:0; }",
        "}",
        ".t { font-family: ui-monospace,'SFMono-Regular',Menlo,Consolas,'DejaVu Sans Mono',monospace; }",
        ".card, .msg-load, .msg-ok {"
        f" animation-duration:{total}s; animation-iteration-count:infinite;"
        " animation-timing-function:linear; }",
        ".card { animation-name: card; transform-box: fill-box; transform-origin: 50% 50%; }",
        ".msg-load { animation-name: msgload; }",
        ".msg-ok { animation-name: msgok; }",
        f".noise {{ animation: noise {total}s linear infinite; }}",
        ".cursor { animation: blink 1.06s step-end infinite; }",
        # Anything animated is opt-in motion; respect the OS setting.
        "@media (prefers-reduced-motion: reduce) {",
        "  .card, .msg-load, .msg-ok, .noise, .cursor { animation: none; }",
        "  .card { opacity:0; }",
        "  .card:first-of-type { opacity:1; }",
        "  .msg-ok { opacity:1; }",
        "  .msg-load { opacity:0; }",
        "}",
    ]
    return "\n".join(lines)


def slot_delay(index, count):
    """Negative delay that makes card `index` take the screen at index*CARD_SECONDS.

    A negative delay fast-forwards an animation, so the offset runs backwards
    through the loop: card 0 starts at 0, card 1 needs the whole loop minus its
    own slot, and so on.
    """
    return -((count - index) % count) * CARD_SECONDS


def card_svg(index, card, x, y, w, h, count):
    """One CRT card: media area on top, metadata strip underneath."""
    delay = slot_delay(index, count)
    media_h = h - 56
    parts = [
        f'<g class="card" style="animation-delay:{delay}s">',
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#0a0b12"/>',
    ]

    if card.get("image"):
        ratio = "xMidYMid slice" if card.get("fit") == "cover" else "xMidYMid meet"
        parts.append(
            f'<image x="{x}" y="{y}" width="{w}" height="{media_h}" '
            f'preserveAspectRatio="{ratio}" href="{data_uri(card["image"])}"/>'
        )
    else:
        ty = y + 26
        for row in card.get("terminal", []):
            fill = GREEN if row.startswith("  200") else (CYAN if row.startswith("$") else DIM)
            parts.append(
                f'<text class="t" x="{x + 20}" y="{ty}" font-size="12" fill="{fill}">'
                f"{escape(row)}</text>"
            )
            ty += 19

    # Scanlines only over the media area, barely there.
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{media_h}" fill="url(#scan)" opacity="0.5"/>'
    )

    meta_y = y + media_h
    parts += [
        f'<rect x="{x}" y="{meta_y}" width="{w}" height="56" fill="{PANEL}"/>',
        f'<rect x="{x}" y="{meta_y}" width="{w}" height="1" fill="{LINE}"/>',
        f'<text class="t" x="{x + 16}" y="{meta_y + 23}" font-size="13" fill="{FG}" '
        f'letter-spacing="0.6">{escape(card["title"])}</text>',
        f'<text class="t" x="{x + 16}" y="{meta_y + 42}" font-size="11" fill="{DIM}">'
        f'{escape(card["tech"])}</text>',
        f'<text class="t" x="{x + w - 16}" y="{meta_y + 42}" font-size="10" fill="{MAGENTA}" '
        f'text-anchor="end">{escape(card["status"])}</text>',
        f'<text class="t" x="{x + w - 16}" y="{meta_y + 23}" font-size="10" fill="{DIM}" '
        f'text-anchor="end">PROJECT://{index + 1:02d}</text>',
        "</g>",
    ]
    return "\n".join(parts)


def build(user):
    cards = json.loads((PROJECTS / "projects.json").read_text())["cards"]
    push = latest_push(user)

    if push:
        repo, sha, days, pushed_on = push
        state = "● ACTIVE" if days <= 2 else ("● BUILDING" if days <= 14 else "● IDLE")
        state_fill = GREEN if days <= 14 else DIM
    else:
        repo, sha, state, state_fill, pushed_on = "—", "—", "● UNKNOWN", DIM, "—"

    rows = [
        ("ROLE", "Software Engineer", FG),
        ("FOCUS", "Backend · AI · Systems", FG),
        ("BUILDING", repo, CYAN),
        ("LAST PUSH", sha, CYAN),
        ("STATUS", state, state_fill),
    ]

    crt_x, crt_y, crt_w, crt_h = 492, 74, 418, 262
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Terminal panel: Marco Diaz, Software Engineer. Backend, AI and Systems. '
        f'Rotating showcase of four projects.">',
        "<defs>",
        f"<style>{build_css(cards)}</style>",
        '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="1" fill="#000" opacity="0.30"/></pattern>',
        '<filter id="snow"><feTurbulence type="fractalNoise" baseFrequency="0.9" '
        'numOctaves="3" stitchTiles="stitch"/>'
        '<feColorMatrix type="saturate" values="0"/></filter>',
        f'<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{CYAN}"/><stop offset="55%" stop-color="{BLUE}"/>'
        f'<stop offset="100%" stop-color="{MAGENTA}"/></linearGradient>',
        f'<clipPath id="screen"><rect x="{crt_x}" y="{crt_y}" width="{crt_w}" height="{crt_h}" '
        'rx="4"/></clipPath>',
        "</defs>",
        f'<rect width="{W}" height="{H}" rx="10" fill="{BG}"/>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" '
        'stroke="url(#edge)" stroke-opacity="0.55"/>',
        # Title bar
        f'<rect x="1" y="1" width="{W - 2}" height="38" rx="10" fill="{PANEL}"/>',
        f'<rect x="1" y="28" width="{W - 2}" height="11" fill="{PANEL}"/>',
        f'<rect x="1" y="38" width="{W - 2}" height="1" fill="{LINE}"/>',
        f'<text class="t" x="24" y="25" font-size="13" fill="{FG}" letter-spacing="3.4">'
        "E L D M A R K</text>",
        f'<text class="t" x="188" y="25" font-size="12" fill="{DIM}">// SYSTEM STATUS</text>',
        f'<circle cx="{W - 96}" cy="20" r="4" fill="{GREEN}"/>',
        f'<text class="t" x="{W - 84}" y="24" font-size="11" fill="{GREEN}" '
        'letter-spacing="1.6">LIVE</text>',
        # Prompt + status table
        f'<text class="t" x="26" y="76" font-size="12" fill="{GREEN}">eldmark@github</text>'
        f'<text class="t" x="150" y="76" font-size="12" fill="{DIM}">:~$ status</text>',
    ]

    y = 118
    for label, value, fill in rows:
        out += [
            f'<text class="t" x="26" y="{y}" font-size="11" fill="{DIM}" letter-spacing="1.2">'
            f"{escape(label)}</text>",
            f'<text class="t" x="150" y="{y}" font-size="13" fill="{fill}">{escape(value)}</text>',
        ]
        y += 30

    out += [
        f'<rect x="26" y="{y + 4}" width="180" height="1" fill="{LINE}"/>',
        f'<text class="t" x="26" y="{y + 30}" font-size="12" fill="{MAGENTA}">'
        f"{escape(TAGLINE)}</text>",
        # Sits just past the tagline: monospace advance is ~0.6em at 12px.
        f'<rect class="cursor" x="{26 + round(len(TAGLINE) * 7.22) + 6}" y="{y + 20}" '
        f'width="7" height="13" fill="{MAGENTA}"/>',
        # CRT bezel
        f'<rect x="{crt_x - 8}" y="{crt_y - 8}" width="{crt_w + 16}" height="{crt_h + 16}" rx="8" '
        f'fill="{PANEL}" stroke="{LINE}"/>',
        f'<g clip-path="url(#screen)">',
        f'<rect x="{crt_x}" y="{crt_y}" width="{crt_w}" height="{crt_h}" fill="#07080d"/>',
    ]

    for i, card in enumerate(cards):
        out.append(card_svg(i, card, crt_x, crt_y, crt_w, crt_h, len(cards)))

    out += [
        f'<rect class="noise" x="{crt_x}" y="{crt_y}" width="{crt_w}" height="{crt_h}" '
        'filter="url(#snow)" opacity="0"/>',
        "</g>",
    ]

    # Per-card prompt line under the CRT.
    total = CARD_SECONDS * len(cards)
    py = crt_y + crt_h + 26
    for i, card in enumerate(cards):
        delay = slot_delay(i, len(cards))
        out += [
            f'<text class="t msg-load" style="animation-delay:{delay}s;'
            f'animation-name:msgload,typing;animation-duration:{total}s,{total}s;'
            f'animation-iteration-count:infinite,infinite;animation-timing-function:linear,linear;'
            f'animation-delay:{delay}s,{delay}s" '
            f'x="{crt_x}" y="{py}" font-size="11" fill="{DIM}">'
            f'&gt; loading project://{escape(card["id"])}</text>',
            f'<text class="t msg-ok" style="animation-delay:{delay}s" '
            f'x="{crt_x}" y="{py}" font-size="11" fill="{CYAN}">&gt; signal acquired</text>',
        ]

    stamp = pushed_on  # not "now": identical inputs must produce an identical file
    out += [
        f'<text class="t" x="{W - 24}" y="{py}" font-size="10" fill="{DIM}" text-anchor="end">'
        f"last push {escape(stamp)}</text>",
        "</svg>",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else "eldmark"
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "assets" / "generated" / "hero.svg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(build(user))
    print(f"wrote {dest} ({dest.stat().st_size // 1024} KB)")
