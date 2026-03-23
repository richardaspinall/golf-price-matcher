const state = {
  matches: [],
  filteredMatches: [],
};

const elements = {
  grid: document.querySelector("#comparison-grid"),
  template: document.querySelector("#comparison-card-template"),
  searchInput: document.querySelector("#search-input"),
  cheaperFilter: document.querySelector("#cheaper-filter"),
  sortSelect: document.querySelector("#sort-select"),
  resultsCount: document.querySelector("#results-count"),
  statMatches: document.querySelector("#stat-matches"),
  statDrummondCheaper: document.querySelector("#stat-drummond-cheaper"),
  statGolfboxCheaper: document.querySelector("#stat-golfbox-cheaper"),
  lastUpdated: document.querySelector("#last-updated"),
};

function formatTimestamp(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.valueOf())) {
    return "Snapshot time unavailable";
  }

  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatPriceDelta(priceDeltaCents) {
  if (priceDeltaCents == null) {
    return "Price difference unavailable";
  }

  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
  }).format(priceDeltaCents / 100);
}

function sortMatches(matches, sortKey) {
  const sorted = [...matches];

  sorted.sort((left, right) => {
    if (sortKey === "delta-asc") {
      return (left.price_delta_cents ?? 0) - (right.price_delta_cents ?? 0);
    }

    if (sortKey === "delta-desc") {
      return (right.price_delta_cents ?? 0) - (left.price_delta_cents ?? 0);
    }

    if (sortKey === "title-asc") {
      return left.label.localeCompare(right.label);
    }

    if (sortKey === "vendor-asc") {
      return (left.vendor ?? "").localeCompare(right.vendor ?? "") || left.label.localeCompare(right.label);
    }

    return (right.price_delta_cents ?? 0) - (left.price_delta_cents ?? 0);
  });

  return sorted;
}

function applyFilters() {
  const searchTerm = elements.searchInput.value.trim().toLowerCase();
  const cheaperStore = elements.cheaperFilter.value;
  const sortKey = elements.sortSelect.value;

  const filtered = state.matches.filter((match) => {
    const matchesCheaperStore =
      cheaperStore === "all" || match.cheaper_store === cheaperStore;

    const matchesSearch =
      searchTerm === "" ||
      `${match.vendor ?? ""} ${match.label} ${match.drummond.title} ${match.golfbox.title}`
        .toLowerCase()
        .includes(searchTerm);

    return matchesCheaperStore && matchesSearch;
  });

  state.filteredMatches = sortMatches(filtered, sortKey);
  renderMatches();
}

function buildPriceBadge(match) {
  if (match.cheaper_store === "unknown") {
    return "Price gap unavailable";
  }
  if (match.cheaper_store === "drummond") {
    return `Drummond cheaper by ${formatPriceDelta(match.price_delta_cents)}`;
  }
  if (match.cheaper_store === "golfbox") {
    return `GolfBox cheaper by ${formatPriceDelta(match.price_delta_cents)}`;
  }
  return "Same listed price";
}

function buildConfidenceNote(match) {
  return `Match confidence: ${match.confidence}. Titles are normalized before comparison.`;
}

function buildCard(match, index) {
  const fragment = elements.template.content.cloneNode(true);
  const card = fragment.querySelector(".comparison-card");
  const vendor = fragment.querySelector(".comparison-card__vendor");
  const label = fragment.querySelector(".comparison-card__label");
  const badge = fragment.querySelector(".comparison-card__badge");
  const note = fragment.querySelector(".comparison-card__note");
  const drummondImage = fragment.querySelector(".store-card__image--drummond");
  const golfboxImage = fragment.querySelector(".store-card__image--golfbox");
  const drummondTitle = fragment.querySelector(".store-card__title--drummond");
  const golfboxTitle = fragment.querySelector(".store-card__title--golfbox");
  const drummondPrice = fragment.querySelector(".store-card__price--drummond");
  const golfboxPrice = fragment.querySelector(".store-card__price--golfbox");
  const drummondLink = fragment.querySelector(".store-card__link--drummond");
  const golfboxLink = fragment.querySelector(".store-card__link--golfbox");

  card.style.animationDelay = `${Math.min(index * 35, 280)}ms`;
  vendor.textContent = match.vendor ?? "Unknown brand";
  label.textContent = match.label;
  badge.textContent = buildPriceBadge(match);
  badge.dataset.store = match.cheaper_store;
  note.textContent = buildConfidenceNote(match);

  drummondImage.src = match.drummond.image_url;
  drummondImage.alt = match.drummond.title;
  golfboxImage.src = match.golfbox.image_url;
  golfboxImage.alt = match.golfbox.title;
  drummondTitle.textContent = match.drummond.title;
  golfboxTitle.textContent = match.golfbox.title;
  drummondPrice.textContent = match.drummond.price_text ?? "Price unavailable";
  golfboxPrice.textContent = match.golfbox.price_text ?? "Price unavailable";
  drummondLink.href = match.drummond.product_url;
  golfboxLink.href = match.golfbox.product_url;

  return fragment;
}

function renderMatches() {
  elements.grid.innerHTML = "";
  elements.grid.setAttribute("aria-busy", "false");
  elements.resultsCount.textContent = `${state.filteredMatches.length} pairs`;

  if (state.filteredMatches.length === 0) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = "No matching glove pairs fit the current filters.";
    elements.grid.append(emptyState);
    return;
  }

  const fragment = document.createDocumentFragment();
  state.filteredMatches.forEach((match, index) => {
    fragment.append(buildCard(match, index));
  });

  elements.grid.append(fragment);
}

function renderSummary(payload) {
  elements.statMatches.textContent = String(payload.summary.matched_products);
  elements.statDrummondCheaper.textContent = String(payload.summary.drummond_cheaper);
  elements.statGolfboxCheaper.textContent = String(payload.summary.golfbox_cheaper);
  elements.lastUpdated.textContent =
    `Drummond ${formatTimestamp(payload.sources.drummond.fetched_at)} · GolfBox ${formatTimestamp(payload.sources.golfbox.fetched_at)}`;
}

function loadProducts() {
  const payload = window.__PRICE_MATCHER_DATA__;

  if (!payload || !Array.isArray(payload.matches)) {
    elements.grid.setAttribute("aria-busy", "false");
    elements.grid.innerHTML =
      '<div class="empty-state">Could not load the comparison dataset.</div>';
    elements.lastUpdated.textContent = "Comparison failed to load";
    return;
  }

  state.matches = payload.matches;
  renderSummary(payload);
  applyFilters();
}

elements.searchInput.addEventListener("input", applyFilters);
elements.cheaperFilter.addEventListener("change", applyFilters);
elements.sortSelect.addEventListener("change", applyFilters);

loadProducts();
