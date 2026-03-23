#!/usr/bin/env python3
"""Build a combined comparison dataset for Drummond Golf and GolfBox gloves."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


STOPWORDS = {
    "all",
    "and",
    "cadet",
    "fit",
    "golf",
    "glove",
    "gloves",
    "hand",
    "junior",
    "ladies",
    "left",
    "men",
    "mens",
    "of",
    "pack",
    "pair",
    "regular",
    "right",
    "single",
    "weatherproof",
    "women",
    "womens",
}
COLORS = {
    "black",
    "blue",
    "brown",
    "charcoal",
    "gold",
    "gray",
    "green",
    "grey",
    "lime",
    "navy",
    "orange",
    "pink",
    "red",
    "silver",
    "white",
    "yellow",
}


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def extract_pack_quantity(title: str) -> int:
    lowered = title.lower()

    for pattern in (r"pack of (\d+)", r"(\d+)\s*pack"):
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))

    if "pair of" in lowered or "pair " in lowered or lowered.endswith(" pair"):
        return 2

    return 1


def normalize_tokens(title: str, vendor: str | None) -> list[str]:
    lowered = title.lower().replace("&", " and ")
    lowered = re.sub(r"20\d{2}", " ", lowered)
    lowered = re.sub(r"\b\d+\b", " ", lowered)
    lowered = re.sub(r"[^a-z]+", " ", lowered)

    vendor_tokens = set(re.findall(r"[a-z]+", (vendor or "").lower()))
    tokens: list[str] = []

    for token in lowered.split():
        if token in vendor_tokens:
            continue
        if token in STOPWORDS or token in COLORS:
            continue
        if len(token) < 3:
            continue
        tokens.append(token)

    return tokens


def price_delta(drummond: dict, golfbox: dict) -> int | None:
    if drummond.get("price_cents") is None or golfbox.get("price_cents") is None:
        return None
    return drummond["price_cents"] - golfbox["price_cents"]


def choose_label(drummond: dict, golfbox: dict) -> str:
    left = re.sub(r"\bGolf\b", "", golfbox["title"], flags=re.IGNORECASE)
    left = re.sub(r"\s+", " ", left).strip(" -")
    right = drummond["title"]
    return left if len(left) <= len(right) else right


def confidence_from_score(score: float) -> str:
    if score >= 0.9:
        return "high"
    if score >= 0.7:
        return "medium"
    return "low"


def build_matches(drummond_products: list[dict], golfbox_products: list[dict]) -> list[dict]:
    candidates: list[dict] = []

    for golfbox in golfbox_products:
        golfbox_tokens = set(normalize_tokens(golfbox["title"], golfbox.get("vendor")))
        golfbox_pack = extract_pack_quantity(golfbox["title"])
        if len(golfbox_tokens) < 2:
            continue

        for drummond in drummond_products:
            if (drummond.get("vendor") or "").lower() != (golfbox.get("vendor") or "").lower():
                continue

            if extract_pack_quantity(drummond["title"]) != golfbox_pack:
                continue

            drummond_tokens = set(normalize_tokens(drummond["title"], drummond.get("vendor")))
            if len(drummond_tokens) < 2:
                continue

            intersection = golfbox_tokens & drummond_tokens
            union = golfbox_tokens | drummond_tokens
            score = len(intersection) / max(len(union), 1)

            if len(intersection) < 2:
                continue
            if score < 0.5 and not (
                golfbox_tokens.issubset(drummond_tokens)
                or drummond_tokens.issubset(golfbox_tokens)
            ):
                continue

            candidates.append(
                {
                    "score": score,
                    "drummond": drummond,
                    "golfbox": golfbox,
                    "intersection_size": len(intersection),
                }
            )

    candidates.sort(
        key=lambda item: (
            item["score"],
            item["intersection_size"],
            -(price_delta(item["drummond"], item["golfbox"]) or 0),
        ),
        reverse=True,
    )

    matches: list[dict] = []
    used_drummond: set[str] = set()
    used_golfbox: set[str] = set()

    for candidate in candidates:
        drummond = candidate["drummond"]
        golfbox = candidate["golfbox"]
        drummond_key = drummond["handle"]
        golfbox_key = golfbox["handle"]

        if drummond_key in used_drummond or golfbox_key in used_golfbox:
            continue

        delta = price_delta(drummond, golfbox)
        if delta is None:
            cheaper_store = "unknown"
        elif delta < 0:
            cheaper_store = "drummond"
        elif delta > 0:
            cheaper_store = "golfbox"
        else:
            cheaper_store = "same"

        matches.append(
            {
                "label": choose_label(drummond, golfbox),
                "vendor": drummond.get("vendor") or golfbox.get("vendor"),
                "confidence": confidence_from_score(candidate["score"]),
                "match_score": round(candidate["score"], 3),
                "cheaper_store": cheaper_store,
                "price_delta_cents": abs(delta) if delta is not None else None,
                "drummond": drummond,
                "golfbox": golfbox,
            }
        )
        used_drummond.add(drummond_key)
        used_golfbox.add(golfbox_key)

    matches.sort(
        key=lambda item: (
            item["vendor"] or "",
            item["label"],
        )
    )
    return matches


def build_payload(drummond: dict, golfbox: dict) -> dict:
    matches = build_matches(drummond["products"], golfbox["products"])

    return {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "drummond": {
                "url": drummond["source_url"],
                "fetched_at": drummond["fetched_at"],
                "product_count": drummond["product_count"],
            },
            "golfbox": {
                "url": golfbox["source_url"],
                "fetched_at": golfbox["fetched_at"],
                "product_count": golfbox["product_count"],
            },
        },
        "summary": {
            "matched_products": len(matches),
            "drummond_cheaper": sum(1 for match in matches if match["cheaper_store"] == "drummond"),
            "golfbox_cheaper": sum(1 for match in matches if match["cheaper_store"] == "golfbox"),
            "same_price": sum(1 for match in matches if match["cheaper_store"] == "same"),
        },
        "matches": matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a combined glove price comparison dataset.")
    parser.add_argument("--drummond", default="data/mens-gloves.json")
    parser.add_argument("--golfbox", default="data/golfbox-gloves.json")
    parser.add_argument("--output", default="data/price-matches.json")
    args = parser.parse_args()

    payload = build_payload(load_json(args.drummond), load_json(args.golfbox))
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
