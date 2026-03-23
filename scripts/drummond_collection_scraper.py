#!/usr/bin/env python3
"""Extract product data from a Drummond Golf collection page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

CARD_PATTERN = re.compile(
    r'<li class="js-pagination-result"><product-card\b.*?</product-card></li>',
    re.DOTALL,
)
TITLE_PATTERN = re.compile(
    r'<a href="(?P<href>/products/[^"]+)" class="card-link text-current js-prod-link">'
    r"(?P<title>.*?)</a>",
    re.DOTALL,
)
VENDOR_PATTERN = re.compile(
    r'<p class="card__vendor[^"]*">(?P<vendor>.*?)</p>',
    re.DOTALL,
)
PRICE_PATTERN = re.compile(
    r'<div class="price__default">.*?<span class="js-value">\s*(?P<price>[^<]+?)\s*</span>',
    re.DOTALL,
)
IMAGE_PATTERN = re.compile(r'<img [^>]* src="(?P<src>[^"]+)"', re.DOTALL)
PRODUCT_ID_PATTERN = re.compile(
    r'<input type="hidden" name="product-id" value="(?P<product_id>\d+)"'
)
RESULT_COUNT_PATTERN = re.compile(r'data-num-results="(?P<count>\d+)"')


@dataclass
class Product:
    title: str
    vendor: Optional[str]
    handle: str
    product_url: str
    image_url: Optional[str]
    price_text: Optional[str]
    price_cents: Optional[int]
    currency: str
    availability: str
    product_id: Optional[int]


def collapse_whitespace(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_price_cents(price_text: Optional[str]) -> Optional[int]:
    if not price_text:
        return None
    match = re.search(r"(\d+(?:\.\d{2})?)", price_text.replace(",", ""))
    if not match:
        return None
    return int(round(float(match.group(1)) * 100))


def normalize_image_url(src: Optional[str]) -> Optional[str]:
    if not src:
        return None
    if src.startswith("//"):
        return "https:" + src
    return src


def parse_collection(html: str, source_url: str) -> dict:
    products: list[Product] = []

    for block in CARD_PATTERN.findall(html):
        title_match = TITLE_PATTERN.search(block)
        if not title_match:
            continue

        href = title_match.group("href")
        title = collapse_whitespace(title_match.group("title"))
        vendor_match = VENDOR_PATTERN.search(block)
        price_match = PRICE_PATTERN.search(block)
        image_match = IMAGE_PATTERN.search(block)
        product_id_match = PRODUCT_ID_PATTERN.search(block)

        price_text = (
            collapse_whitespace(price_match.group("price")) if price_match else None
        )
        product_url = urljoin(source_url, href)
        handle = urlparse(product_url).path.rstrip("/").split("/")[-1]

        products.append(
            Product(
                title=title,
                vendor=collapse_whitespace(vendor_match.group("vendor"))
                if vendor_match
                else None,
                handle=handle,
                product_url=product_url,
                image_url=normalize_image_url(image_match.group("src"))
                if image_match
                else None,
                price_text=price_text,
                price_cents=parse_price_cents(price_text),
                currency="AUD",
                availability="unknown",
                product_id=int(product_id_match.group("product_id"))
                if product_id_match
                else None,
            )
        )

    result_count_match = RESULT_COUNT_PATTERN.search(html)

    return {
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "result_count_hint": int(result_count_match.group("count"))
        if result_count_match
        else None,
        "product_count": len(products),
        "products": [asdict(product) for product in products],
    }


def fetch_html(url: str, timeout: int = 30) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def load_html(args: argparse.Namespace) -> tuple[str, str]:
    if args.input_file:
        html = Path(args.input_file).read_text(encoding="utf-8")
        return html, args.url

    return fetch_html(args.url), args.url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract product cards from a Drummond Golf collection page."
    )
    parser.add_argument(
        "--url",
        default="https://drummondgolf.com.au/collections/balls-gloves-mens-gloves",
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

    output = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
