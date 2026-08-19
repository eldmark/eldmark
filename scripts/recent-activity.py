#!/usr/bin/env python3
"""Print the last N public commits across the user's repositories as Markdown.

Reads the public events feed (private repositories never appear there), takes
the head commit of each push, and resolves its message through the commits API
because the events payload does not carry commit objects.

Usage: recent-activity.py <github-user> [limit]
Requires: the `gh` CLI, authenticated (GH_TOKEN is enough).
"""
import json
import subprocess
import sys


def gh(path):
    out = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, check=False
    )
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout else None


def main():
    user = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    events = gh(f"users/{user}/events/public?per_page=100") or []
    lines, seen = [], set()

    for event in events:
        if len(lines) >= limit:
            break
        if event.get("type") != "PushEvent":
            continue
        repo = event["repo"]["name"]
        sha = event["payload"].get("head")
        if not sha or (repo, sha) in seen:
            continue
        seen.add((repo, sha))

        commit = gh(f"repos/{repo}/commits/{sha}")
        if not commit:
            continue
        message = commit["commit"]["message"].splitlines()[0].strip()
        if not message or message.startswith("Merge "):
            continue

        date = commit["commit"]["author"]["date"].split("T")[0]
        name = repo.split("/")[-1]
        lines.append(
            f"- **[{name}](https://github.com/{repo})** · `{sha[:7]}` — {message} _({date})_"
        )

    print("\n".join(lines))


if __name__ == "__main__":
    main()
