#!/usr/bin/env python3
"""Self-checks for the hero generator. Run: python3 scripts/test_generate_hero.py"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from generate_hero import CARD_SECONDS, lead_with, slot_delay  # noqa: E402

CARDS = [
    {"id": "portfolio", "repo": "eldmark/game-portafolio"},
    {"id": "ecoscan", "repo": "eldmark/backend-ecoscan"},
    {"id": "teddyursa", "repo": "eldmark/teddyursa"},
]

# The repo pushed to most recently leads, the rest keep their order.
assert [c["id"] for c in lead_with(CARDS, "teddyursa")] == ["teddyursa", "portfolio", "ecoscan"]
# An active repo with no card changes nothing.
assert [c["id"] for c in lead_with(CARDS, "eldmark")] == ["portfolio", "ecoscan", "teddyursa"]

# Card i must own the screen during slot i: progress = elapsed - delay.
for count in (4, 5):
    for i in range(count):
        start = i * CARD_SECONDS
        progress = (start - slot_delay(i, count)) % (CARD_SECONDS * count)
        assert progress == 0, f"card {i} of {count} starts at {progress}s into its cycle"

# Every card referenced by the manifest has its image committed.
root = pathlib.Path(__file__).parent.parent
for card in json.loads((root / "assets/projects/projects.json").read_text())["cards"]:
    if card.get("image"):
        assert (root / "assets/projects" / card["image"]).exists(), card["image"]

print("ok")
