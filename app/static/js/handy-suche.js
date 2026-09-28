// Phone: find an article by EAN (scanner or typed), supplier number or name,
// then show price, sizes/colours and stock in every location.
(function () {
  var P = window.SFPhone;
  var t = P.t;
  var el = P.el;
  var STORE_KEY = 'sfPhoneSearch';

  var form = document.getElementById('searchForm');
  var input = document.getElementById('searchInput');
  var status = document.getElementById('status');
  var results = document.getElementById('results');
  var searchView = document.getElementById('searchView');
  var articleView = document.getElementById('articleView');
  var back = document.getElementById('back');

  var state = { query: '', items: [], total: 0, article: null, stock: null, stockError: null };
  var me = null;
  var searchSeq = 0;

  function remember() {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify({ query: state.query, items: state.items, total: state.total })); } catch (e) { }
  }

  function restore() {
    try {
      var saved = JSON.parse(sessionStorage.getItem(STORE_KEY) || 'null');
      if (saved) { state.query = saved.query || ''; state.items = saved.items || []; state.total = saved.total || 0; }
    } catch (e) { }
  }

  function variantText(item) {
    return [item.color, item.size].filter(Boolean).join(' · ');
  }

  function renderResults() {
    results.replaceChildren();
    if (!state.query) { status.textContent = ''; return; }
    if (!state.items.length) { status.textContent = t('phone.search_none'); return; }
    status.textContent = state.total > state.items.length
      ? t('phone.search_more', { shown: state.items.length, total: state.total })
      : t('phone.search_count', { n: state.total });
    state.items.forEach(function (item) {
      var li = document.createElement('li');
      var button = el('button');
      button.type = 'button';
      button.append(
        el('strong', null, [item.brand, item.description].filter(Boolean).join(' ')),
        el('span', 'm-num', P.money(item.latest_uvp) || ''),
        el('span', 'm-sub', [variantText(item), item.supplier_article_no].filter(Boolean).join(' · '))
      );
      button.addEventListener('click', function () { openArticle(item, true); });
      li.append(button);
      results.append(li);
    });
  }

  async function search(query) {
    query = query.trim();
    if (!query) return;
    var seq = ++searchSeq;
    state.query = query;
    status.textContent = t('phone.searching');
    results.replaceChildren();
    try {
      if (/^\d{8,14}$/.test(query)) {
        var exact = await P.fetchJson('/api/articles?page_size=25&ean=' + encodeURIComponent(query));
        if (seq !== searchSeq) return;
        if (exact.items.length === 1) {
          state.items = exact.items; state.total = 1; remember();
          openArticle(exact.items[0], true);
          return;
        }
      }
      var data = await P.fetchJson('/api/articles?page_size=25&q=' + encodeURIComponent(query));
      if (seq !== searchSeq) return;
      state.items = data.items; state.total = data.total;
      remember();
      renderResults();
    } catch (error) {
      if (seq === searchSeq) status.textContent = error.message;
    }
  }

  function showSearch() {
    state.article = null;
    articleView.hidden = true;
    searchView.hidden = false;
    renderResults();
  }

  function stageChip(prozent) {
    var chip = el('span', 'chip chip-stage');
    chip.dataset.stage = String(prozent);
    chip.append(el('span', 'chip-dot'), document.createTextNode('−' + prozent + ' %'));
    return chip;
  }

  function renderArticle() {
    var item = state.article;
    if (!item) return;
    document.getElementById('articleBrand').textContent = item.brand || '';
    document.getElementById('articleTitle').textContent = item.description || '';
    var meta = document.getElementById('articleMeta');
    meta.replaceChildren();
    if (item.supplier_article_no) meta.append(document.createTextNode(t('phone.supplier_no') + ' ' + item.supplier_article_no));
    if (item.ean) {
      if (item.supplier_article_no) meta.append(document.createTextNode(' · '));
      meta.append(document.createTextNode(t('phone.ean') + ' '), el('span', 'm-mono', item.ean));
    }
    var price = document.getElementById('articlePrice');
    price.textContent = P.money(item.latest_uvp) || t('phone.no_uvp');
    price.classList.toggle('is-missing', !P.money(item.latest_uvp));
    document.getElementById('articleVariant').textContent = variantText(item);
    renderStock();
  }

  function renderStock() {
    var box = document.getElementById('stock');
    var stockStatus = document.getElementById('stockStatus');
    box.replaceChildren();
    if (state.stockError) { stockStatus.textContent = state.stockError; return; }
    if (!state.stock) { stockStatus.textContent = t('phone.stock_loading'); return; }
    if (!state.stock.length) { stockStatus.textContent = t('phone.stock_none'); return; }
    stockStatus.textContent = '';

    var groups = {};
    state.stock.forEach(function (row) {
      var g = groups[row.lagerort.id] || (groups[row.lagerort.id] = { lagerort: row.lagerort, rows: [], total: 0, reduktion: null });
      g.rows.push(row);
      g.total += Number(row.menge);
      if (row.reduktion) g.reduktion = row.reduktion;
    });
    var activeId = me && me.lagerort ? me.lagerort.id : null;
    Object.keys(groups).map(function (id) { return groups[id]; })
      .sort(function (a, b) {
        function rank(g) { return g.lagerort.id === activeId ? 0 : g.lagerort.verkauf ? 1 : 2; }
        return rank(a) - rank(b) || a.lagerort.code.localeCompare(b.lagerort.code);
      })
      .forEach(function (g) {
        var card = el('section', 'm-store' + (g.lagerort.id === activeId ? ' is-active' : ''));
        var head = el('div', 'm-store-head');
        head.append(el('span', null, g.lagerort.code + ' · ' + g.lagerort.name));
        if (!g.lagerort.verkauf) head.append(el('span', 'chip chip-neutral', t('phone.external')));
        if (g.reduktion && Number(g.reduktion.wirksam) > 0) head.append(stageChip(g.reduktion.wirksam));
        head.append(el('span', 'm-num', t('phone.pieces', { n: P.qty(g.total) })));
        var list = el('ul');
        g.rows.forEach(function (row) {
          var li = el('li', row.varianten_id === state.article.id ? 'is-selected' : null);
          li.append(
            el('span', null, [row.farbe, row.groesse].filter(Boolean).join(' · ') || t('phone.no_variant')),
            el('span', 'm-num' + (Number(row.menge) < 0 ? ' negative' : ''), P.qty(row.menge))
          );
          list.append(li);
        });
        card.append(head, list);
        box.append(card);
      });
  }

  async function loadStock(item) {
    state.stock = null; state.stockError = null;
    renderStock();
    try {
      var data = await P.fetchJson('/api/bestand?alle=true&limit=500&artikel_von=' + item.id);
      if (state.article !== item) return;
      state.stock = data.zeilen;
    } catch (error) {
      if (state.article !== item) return;
      state.stockError = error.message;
    }
    renderStock();
  }

  function openArticle(item, push) {
    if (push) history.pushState({ v: item.id }, '', '?v=' + item.id);
    state.article = item;
    searchView.hidden = true;
    articleView.hidden = false;
    window.scrollTo(0, 0);
    renderArticle();
    loadStock(item);
  }

  function fromUrl() {
    var id = Number(new URLSearchParams(location.search).get('v'));
    var item = id ? state.items.find(function (i) { return i.id === id; }) : null;
    if (item) { openArticle(item, false); return; }
    if (id) history.replaceState(null, '', location.pathname);
    showSearch();
  }

  back.addEventListener('click', function (event) {
    if (!articleView.hidden) { event.preventDefault(); history.back(); }
  });
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    input.blur();
    search(input.value);
  });
  window.addEventListener('popstate', fromUrl);
  document.addEventListener('sportfabrik:me', function (event) { me = event.detail; renderStock(); });
  document.addEventListener('sportfabrik:i18n-ready', function () {
    if (state.article) renderArticle(); else renderResults();
  });

  restore();
  input.value = state.query;
  fromUrl();
})();
