const state = {
  cards: [],
  brand: "All",
  alert: "All",
  kind: "All",
  query: "",
};

const els = {
  q: document.querySelector("#q"),
  status: document.querySelector("#status"),
  brands: document.querySelector("#brand-filters"),
  alerts: document.querySelector("#alert-filters"),
  kinds: document.querySelector("#kind-filters"),
  results: document.querySelector("#results"),
  empty: document.querySelector("#empty"),
  viewer: document.querySelector("#viewer"),
  frame: document.querySelector("#frame"),
  title: document.querySelector("#viewer-title"),
  kicker: document.querySelector("#viewer-kicker"),
  download: document.querySelector("#download"),
  openTab: document.querySelector("#open-tab"),
  close: document.querySelector("#close"),
  prev: document.querySelector("#prev"),
  next: document.querySelector("#next"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const PIC_LABEL = {
  flame: "Fl",
  gas: "G",
  health: "H",
  environment: "E",
  exclamation: "!",
  corrosion: "C",
};

function bytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function encodePath(path) {
  return path
    .split("/")
    .map((part) => encodeURIComponent(part))
    .join("/");
}

function visibleCards() {
  const q = state.query.trim().toLowerCase();
  return state.cards.filter((card) => {
    if (state.brand !== "All" && card.brand !== state.brand) return false;
    if (state.alert !== "All" && String(card.hazardAlert) !== state.alert) return false;
    if (state.kind !== "All" && card.kind !== state.kind) return false;
    if (!q) return true;
    return card.search.includes(q);
  });
}

function chip(label, active, dataset = {}) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `chip${active ? " is-active" : ""}`;
  btn.textContent = label;
  Object.entries(dataset).forEach(([k, v]) => btn.dataset[k] = v);
  return btn;
}

function renderFilters() {
  const brands = ["All", ...[...new Set(state.cards.map((c) => c.brand))].sort()];
  els.brands.replaceChildren(
    ...brands.map((brand) => {
      const btn = chip(brand, state.brand === brand);
      btn.addEventListener("click", () => {
        state.brand = brand;
        render();
      });
      return btn;
    })
  );

  const alerts = ["All", ...[...new Set(state.cards.map((c) => String(c.hazardAlert ?? "")))].filter(Boolean).sort()];
  els.alerts.replaceChildren(
    ...alerts.map((alert) => {
      const label = alert === "All" ? "All alert codes" : `Alert ${alert}`;
      const btn = chip(label, state.alert === alert, { alert });
      btn.addEventListener("click", () => {
        state.alert = alert;
        render();
      });
      return btn;
    })
  );

  const kinds = ["All", ...[...new Set(state.cards.map((c) => c.kind).filter(Boolean))]];
  els.kinds.replaceChildren(
    ...kinds.map((kind) => {
      const label = kind === "All" ? "All document types" : kind;
      const btn = chip(label, state.kind === kind);
      btn.addEventListener("click", () => {
        state.kind = kind;
        render();
      });
      return btn;
    })
  );
}

function cardEl(card) {
  const article = document.createElement("article");
  article.className = "card";
  article.innerHTML = `
    <div class="card__preview">
      <img src="${encodePath(card.thumb)}" alt="Preview of ${escapeHtml(card.title)}" loading="lazy" />
      ${card.hazardAlert != null ? `<span class="badge" data-alert="${card.hazardAlert}">Alert ${card.hazardAlert}${card.signal ? ` · ${escapeHtml(card.signal)}` : ""}</span>` : ""}
    </div>
    <div class="card__body">
      <p class="card__brand">${escapeHtml(card.brand)}</p>
      <h2 class="card__title">${escapeHtml(card.title)}</h2>
      <ul class="card__meta">
        ${card.sku ? `<li>SKU ${escapeHtml(card.sku)}</li>` : ""}
        ${card.kind ? `<li>${escapeHtml(card.kind)}</li>` : ""}
        ${card.un ? `<li>UN ${escapeHtml(card.un)}</li>` : ""}
        ${card.dgClass ? `<li>DG ${escapeHtml(card.dgClass)}</li>` : ""}
        <li>${bytes(card.bytes)}</li>
      </ul>
      <div class="pictos" aria-label="Hazard pictograms">
        ${card.pictograms.map((p) => `<span class="picto" data-kind="${p}" title="${p}">${PIC_LABEL[p] || p}</span>`).join("")}
      </div>
    </div>
    <div class="card__actions">
      <button class="btn btn--primary" type="button" data-view>View</button>
      <a class="btn" href="${encodePath(card.url)}" download="${card.file}">Download</a>
    </div>
  `;
  article.querySelector("[data-view]").addEventListener("click", () => openViewer(card));
  article.querySelector(".card__preview").addEventListener("click", () => openViewer(card));
  return article;
}

function render() {
  renderFilters();
  const cards = visibleCards();
  els.status.textContent = `${cards.length} of ${state.cards.length} SDS document${state.cards.length === 1 ? "" : "s"}`;
  els.results.replaceChildren(...cards.map(cardEl));
  els.empty.hidden = cards.length > 0;
}

function currentIndex() {
  const file = decodeURIComponent(location.hash.replace(/^#view=/, ""));
  return visibleCards().findIndex((c) => c.file === file);
}

function openViewer(card) {
  location.hash = `view=${encodeURIComponent(card.file)}`;
}

function closeViewer() {
  if (location.hash) history.pushState("", document.title, location.pathname + location.search);
  syncViewer();
}

function syncViewer() {
  const match = location.hash.match(/^#view=(.+)$/);
  if (!match) {
    els.viewer.hidden = true;
    document.body.classList.remove("viewing");
    els.frame.src = "";
    return;
  }
  const file = decodeURIComponent(match[1]);
  const card = state.cards.find((c) => c.file === file);
  if (!card) return;
  const url = encodePath(card.url);
  els.title.textContent = card.title;
  els.kicker.textContent = [card.brand, card.sku && `SKU ${card.sku}`, card.signal].filter(Boolean).join(" · ");
  els.frame.src = url;
  els.download.href = url;
  els.download.setAttribute("download", card.file);
  els.openTab.href = url;
  els.viewer.hidden = false;
  document.body.classList.add("viewing");
}

function step(delta) {
  const cards = visibleCards();
  if (!cards.length) return;
  const idx = currentIndex();
  const i = idx < 0 ? 0 : idx;
  openViewer(cards[(i + delta + cards.length) % cards.length]);
}

els.q.addEventListener("input", () => {
  state.query = els.q.value;
  render();
});
els.close.addEventListener("click", closeViewer);
els.prev.addEventListener("click", () => step(-1));
els.next.addEventListener("click", () => step(1));
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== els.q) {
    event.preventDefault();
    els.q.focus();
  }
  if (event.key === "Escape") closeViewer();
  if (!els.viewer.hidden && event.key === "ArrowRight") step(1);
  if (!els.viewer.hidden && event.key === "ArrowLeft") step(-1);
});
window.addEventListener("hashchange", syncViewer);

const catalog = await fetch("data/sds-index.json").then((r) => {
  if (!r.ok) throw new Error("Could not load Mini SDS catalog");
  return r.json();
});
state.cards = catalog.cards;
render();
syncViewer();
