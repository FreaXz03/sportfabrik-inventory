// Phone: count an article on the shelf and correct the stock of the active
// store. The server books only the difference (lagerbewegungen, rule 2) and
// checks that the user may book in this store (rule 9).
(function () {
  var P = window.SFPhone;
  var t = P.t;

  var pickView = document.getElementById('pickView');
  var countView = document.getElementById('countView');
  var notice = document.getElementById('notice');
  var form = document.getElementById('countForm');
  var counted = document.getElementById('counted');
  var reason = document.getElementById('reason');
  var freetextField = document.getElementById('freetextField');
  var freetext = document.getElementById('freetext');
  var formError = document.getElementById('formError');
  var book = document.getElementById('book');
  var current = document.getElementById('current');
  var staleBox = document.getElementById('staleBox');
  var staleText = document.getElementById('staleText');
  var staleMoves = document.getElementById('staleMoves');
  var forceBook = document.getElementById('forceBook');

  var me = null;
  var reasons = [];
  var state = { item: null, stock: null, marker: null, allowed: false, error: null, busy: false, pending: null };

  var pick = P.picker({
    container: document.getElementById('picker'),
    onPick: function (item) { openCount(item, true); }
  });

  function store() { return me && me.lagerort ? me.lagerort : null; }

  function renderStore() {
    var line = document.getElementById('storeLine');
    var s = store();
    line.textContent = s ? t('phone.count_in', { store: s.code + ' · ' + s.name }) : (me ? t('phone.choose_store') : '');
    line.classList.toggle('error', !!me && !s);
    pickView.hidden = !s || !!state.item;
  }

  function renderReasons() {
    var selected = reason.value || 'inventur';
    reason.replaceChildren();
    reasons.forEach(function (key) { reason.add(new Option(t('bestand.correction_reason.' + key), key)); });
    reason.value = selected;
    freetextField.hidden = reason.value !== 'sonstiges';
  }

  function renderCount() {
    var item = state.item;
    if (!item) return;
    document.getElementById('countBrand').textContent = item.brand || '';
    document.getElementById('countTitle').textContent = item.description || '';
    document.getElementById('countVariant').textContent = P.variantText(item);
    document.getElementById('countEan').textContent = item.ean || '';
    var s = store();
    if (state.error) current.textContent = state.error;
    else if (state.stock === null) current.textContent = t('phone.stock_loading');
    else current.textContent = t('phone.count_current', { store: s ? s.code : '', n: P.qty(state.stock) });
    form.hidden = state.stock === null || !!state.error;
    book.disabled = state.busy || !state.allowed;
    if (state.stock !== null && !state.allowed) showError(t('errors.auth.no_lagerort_access'));
  }

  function showError(text) {
    formError.hidden = !text;
    formError.textContent = text || '';
  }

  async function loadStock(item) {
    var s = store();
    state.stock = null; state.marker = null; state.error = null; state.allowed = false;
    hideStale();
    renderCount();
    try {
      var data = await P.fetchJson('/api/bestand?nur_vorhanden=false&limit=500&lagerort_id=' + s.id + '&artikel_von=' + item.id);
      if (state.item !== item) return;
      var row = data.zeilen.find(function (z) { return z.varianten_id === item.id; });
      state.stock = row ? row.menge : '0';
      state.marker = row ? row.letzte_bewegung_id : 0;
      state.allowed = (data.rechte.korrektur_lagerorte || []).indexOf(s.id) !== -1;
    } catch (error) {
      if (state.item !== item) return;
      state.error = error.message;
    }
    renderCount();
  }

  function openCount(item, push) {
    if (!store()) return;
    if (push) history.pushState({ count: item.id }, '', '?v=' + item.id);
    state.item = item;
    notice.hidden = true;
    counted.value = '';
    freetext.value = '';
    showError('');
    pickView.hidden = true;
    countView.hidden = false;
    window.scrollTo(0, 0);
    loadStock(item);
    counted.focus();
  }

  function showPick() {
    state.item = null;
    countView.hidden = true;
    renderStore();
  }

  function step(delta) {
    var n = parseInt(counted.value, 10);
    if (isNaN(n)) n = state.stock !== null ? Math.max(0, Math.round(Number(state.stock))) : 0;
    counted.value = String(Math.max(0, n + delta));
  }

  function hideStale() {
    state.pending = null;
    staleBox.hidden = true;
    staleMoves.replaceChildren();
  }

  // Der Bestand hat sich seit Zählbeginn bewegt (Paket 2): nichts gebucht.
  // Neu zählen (Marke und Bestand sind aktualisiert), oder die letzte Zählung
  // ausdrücklich gegen den Stand von jetzt buchen.
  function showStale(data, pendingValue) {
    state.stock = data.bestand_jetzt;
    state.marker = data.stand_bewegung_id;
    state.pending = pendingValue;
    staleText.textContent = t('phone.count_stale', { n: P.qty(data.bestand_jetzt) });
    staleMoves.replaceChildren();
    (data.seit_zaehlbeginn || []).forEach(function (move) {
      var li = document.createElement('li');
      var time = new Date(move.zeitpunkt).toLocaleTimeString(P.locale ? P.locale() : undefined, { hour: '2-digit', minute: '2-digit' });
      li.textContent = time + ' · ' + t('phone.move_type.' + move.typ) + ' ' + (Number(move.menge) > 0 ? '+' : '') + P.qty(move.menge) + (move.benutzer_name ? ' · ' + move.benutzer_name : '');
      staleMoves.append(li);
    });
    forceBook.textContent = t('phone.count_force', { n: pendingValue });
    staleBox.hidden = false;
    counted.value = '';
    counted.focus();
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    await submitCount(counted.value.trim(), false);
  });
  forceBook.addEventListener('click', function () {
    if (state.pending !== null) submitCount(state.pending, true);
  });

  async function submitCount(value, confirmed) {
    if (state.busy || !state.item) return;
    if (!/^\d+$/.test(value)) { showError(t('errors.korrektur.invalid_quantity')); counted.focus(); return; }
    if (reason.value === 'sonstiges' && !freetext.value.trim()) { showError(t('phone.count_text_required')); freetext.focus(); return; }
    showError('');
    hideStale();
    state.busy = true;
    book.classList.add('is-loading');
    renderCount();
    var item = state.item;
    try {
      var result = await P.fetchJson('/api/korrektur', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          varianten_id: item.id,
          lagerort_id: store().id,
          gezaehlt: value,
          grund: reason.value,
          freitext: reason.value === 'sonstiges' ? freetext.value.trim() : null,
          stand_bewegung_id: state.marker,
          bestaetigt: confirmed
        })
      });
      var name = [item.brand, item.description, P.variantText(item)].filter(Boolean).join(' ');
      var diff = Number(result.differenz);
      notice.textContent = result.gebucht
        ? t('bestand.correction_done', {
          artikel: name,
          vorher: P.qty(result.bestand_vorher),
          nachher: P.qty(result.bestand_nachher),
          differenz: (diff > 0 ? '+' : '') + P.qty(result.differenz)
        })
        : t('bestand.correction_unchanged', { artikel: name, menge: P.qty(result.bestand_nachher) });
      pick.clear();
      history.back();
      notice.hidden = false;
    } catch (error) {
      if (error.data && error.data.code === 'bestand_geaendert') showStale(error.data, value);
      else showError(error.message);
    } finally {
      state.busy = false;
      book.classList.remove('is-loading');
      renderCount();
    }
  }

  document.getElementById('minus').addEventListener('click', function () { step(-1); });
  document.getElementById('plus').addEventListener('click', function () { step(1); });
  document.getElementById('other').addEventListener('click', function () { history.back(); });
  document.getElementById('back').addEventListener('click', function (event) {
    if (state.item) { event.preventDefault(); history.back(); }
  });
  reason.addEventListener('change', function () { freetextField.hidden = reason.value !== 'sonstiges'; });
  window.addEventListener('popstate', function () { if (state.item) showPick(); });
  document.addEventListener('sportfabrik:me', function (event) { me = event.detail; renderStore(); });
  document.addEventListener('sportfabrik:i18n-ready', function () { renderStore(); renderReasons(); renderCount(); });

  if (location.search) history.replaceState(null, '', location.pathname);
  P.fetchJson('/api/korrektur/gruende').then(function (data) { reasons = data.gruende; renderReasons(); })
    .catch(function (error) { showError(error.message); });
})();
