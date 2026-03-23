#!/usr/bin/env python3
"""Extract glove data from the GolfBox gloves category page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

BODL_PATTERN = re.compile(r'var BODL = JSON\.parse\("(?P<payload>.*)"\);')


@dataclass
class Product:
    title: str
    vendor: str | None
    handle: str
    product_url: str
    image_url: str | None
    price_text: str | None
    price_cents: int | None
    currency: str
    availability: str
    product_id: int | None


def fetch_html(url: str, timeout: int = 30) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_bodl(html: str) -> dict:
    match = BODL_PATTERN.search(html)
    if not match:
        raise ValueError("Could not locate BODL payload in GolfBox HTML.")
    payload = match.group("payload").encode("utf-8").decode("unicode_escape")
    return json.loads(payload)


def build_product(raw_product: dict) -> Product:
    price_value = raw_product.get("price", {}).get("with_tax", {}).get("value")
    price_text = raw_product.get("price", {}).get("with_tax", {}).get("formatted")
    vendor = raw_product.get("brand", {}).get("name")
    url = raw_product.get("url")
    handle = url.rstrip("/").split("/")[-1] if url else ""
    availability = (
        "available"
        if raw_product.get("availability") == "InStock"
        else "unknown"
    )

    return Product(
        title=raw_product.get("name", "").strip(),
        vendor=vendor.strip() if isinstance(vendor, str) else None,
        handle=handle,
        product_url=url,
        image_url=raw_product.get("image", {}).get("data", "").replace(
            "{:size}", "500x659"
        )
        or None,
        price_text=price_text,
        price_cents=int(round(price_value * 100)) if price_value is not None else None,
        currency=raw_product.get("price", {})
        .get("with_tax", {})
        .get("currency", "AUD"),
        availability=availability,
        product_id=raw_product.get("id"),
    )


def parse_collection(html: str, source_url: str) -> dict:
    bodl = extract_bodl(html)
    products = [build_product(product) for product in bodl.get("categoryProducts", [])]

    return {
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "product_count": len(products),
        "products": [asdict(product) for product in products],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract product data from the GolfBox gloves collection."
    )
    parser.add_argument(
        "--url",
        default="https://www.golfbox.com.au/golf-gloves/",
        help="Collection URL to scrape.",
    )
    parser.add_argument(
        "--input-file",
        help="Parse previously saved HTML instead of fetching the URL.",
    )
    parser.add_argument(
        "--output",
        help="Write JSON output to this file. Defaults to stdout.",
    )
    return parser


def load_html(args: argparse.Namespace) -> tuple[str, str]:
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8"), args.url
    return fetch_html(args.url), args.url


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        html, source_url = load_html(args)
        payload = parse_collection(html, source_url)
    except FileNotFoundError as exc:
        print(f"Input file not found: {exc}", file=sys.stderr)
        return 1
    except HTTPError as exc:
        print(f"HTTP error while fetching {args.url}: {exc.code}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Network error while fetching {args.url}: {exc.reason}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
