# Golf Price Matcher Prototype

This prototype compares likely matching men’s golf gloves across Drummond Golf and GolfBox.

The current sources are:

- `https://drummondgolf.com.au/collections/balls-gloves-mens-gloves`
- `https://www.golfbox.com.au/golf-gloves/`

## Extractors

- `scripts/drummond_collection_scraper.py`
- `scripts/golfbox_gloves_scraper.py`
- `scripts/build_price_matches.py`

## Usage

Build Drummond data from a saved snapshot:

```bash
python3 scripts/drummond_collection_scraper.py \
  --input-file /tmp/drummond-mens-gloves.html
```

Build GolfBox data from a saved snapshot:

```bash
python3 scripts/golfbox_gloves_scraper.py \
  --input-file /tmp/golfbox-gloves.html \
  --output data/golfbox-gloves.json
```

Build the comparison dataset:

```bash
python3 scripts/build_price_matches.py
```

The static page reads `data/price-matches.js`.

## Matching notes

- Matches are conservative and based on brand plus normalized title tokens.
- Terms like `golf`, `glove`, color names, hand, and years are stripped before matching.
- Pack quantities are respected so a 2-pack should not be matched to a single glove.
