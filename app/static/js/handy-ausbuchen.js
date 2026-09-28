// Phone: book out a sale or other removal, reserved for branch managers and
// head office (rule 9). Each tap books exactly one piece (F15); cancelling a
// booking stays on the computer. The negative-stock warning works as on
// desktop (F9): booked anyway, but said so.
(function () {
  var P = window.SFPhone;
  var t = P.t;

  var lagerortSelect = document.getElementById('lagerort');
  var grundSelect = document.getElementById('grund');
  var freetextField = document.getElementById('freetextField');
  var freetext = document.getElementById('freitext');
  var reasonError = document.getElementById('reasonError');
  var pickView = document.getElementById('pickView');
  var itemView = document.getElementById('itemView');
  var itemStatus = document.getElementById('itemStatus');
  var book = document.getElementById('book');

  var lagerorte = [];
  var gruende = [];
  var state = { item: null, busy: false };

  function fillLagerort(preselect) {
    var current = lagerortSelect.value;
    lagerortSelect.replaceChildren();
    lagerorte.forEach(function (lo) {
      lagerortSelect.add(new Option(lo.code + ' · ' + lo.name, lo.id));
    });
    lagerortSelect.value = current || (preselect ? String(preselect) : '');
  }

  function fillGruende() {
    var current = grundSelect.value;
    grundSelect.replaceChildren();
    gruende.forEach(function (g) { grundSelect.add(new Option(t('ausbuchen.reason.' + g), g)); });
    grundSelect.value = current || gruende[0] || '';
    freetextField.hidden = grundSelect.value !== 'sonstiges';
  }

  async function loadStammdaten() {
    try {
      var data = await P.fetchJson('/api/ausbuchen/stammdaten');
      lagerorte = data.lagerorte;
      gruende = data.gruende;
      fillLagerort(data.lagerort_aktiv);
      fillGruende();
    } catch (error) {
      reasonError.hidden = false;
      reasonError.textContent = error.message;
    }
  }

  function validateReason() {
    if (grundSelect.value === 'sonstiges' && !freetext.value.trim()) {
      reasonError.hidden = false;
      reasonError.textContent = t('errors.ausbuchung.text_required');
      return false;
    }
    reasonError.hidden = true;
    return true;
  }

  function renderItem() {
    var item = state.item;
    if (!item) return;
    document.getElementById('itemBrand').textContent = item.brand || '';
    document.getElementById('itemTitle').textContent = item.description || '';
    document.getElementById('itemVariant').textContent = P.variantText(item);
    document.getElementById('itemEan').textContent = item.ean || '';
    book.disabled = state.busy;
  }

  function openItem(item) {
    if (!validateReason()) { freetext.focus(); return; }
    state.item = item;
    itemStatus.textContent = '';
    itemStatus.className = 'm-current';
    pickView.hidden = true;
    itemView.hidden = false;
    window.scrollTo(0, 0);
    renderItem();
  }

  function showPick() {
    state.item = null;
    itemView.hidden = true;
    pickView.hidden = false;
  }

  var pick = P.picker({
    container: document.getElementById('picker'),
    onPick: openItem
  });

  book.addEventListener('click', async function () {
    if (state.busy || !state.item || !validateReason()) return;
    state.busy = true;
    book.classList.add('is-loading');
    renderItem();
    try {
      var result = await P.fetchJson('/api/ausbuchen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          grund: grundSelect.value,
          freitext: grundSelect.value === 'sonstiges' ? freetext.value.trim() : null,
          varianten_id: state.item.id,
          lagerort_id: Number(lagerortSelect.value) || null
        })
      });
      var name = [result.marke, result.bezeichnung].filter(Boolean).join(' ');
      var variant = [result.farbe, result.groesse].filter(Boolean).join(' · ');
      var artikel = variant ? name + ' (' + variant + ')' : name;
      itemStatus.textContent = t(result.bestand_reicht_nicht ? 'ausbuchen.booked_negative' : 'ausbuchen.booked', {
        artikel: artikel, lagerort: result.lagerort.code, menge: P.qty(result.bestand_nachher)
      });
      itemStatus.className = result.bestand_reicht_nicht ? 'm-current warning-text' : 'm-current';
    } catch (error) {
      itemStatus.textContent = error.message;
      itemStatus.className = 'm-current warning-text';
    } finally {
      state.busy = false;
      book.classList.remove('is-loading');
      renderItem();
    }
  });

  document.getElementById('other').addEventListener('click', function () { showPick(); pick.clear(); });
  grundSelect.addEventListener('change', function () {
    freetextField.hidden = grundSelect.value !== 'sonstiges';
    if (grundSelect.value !== 'sonstiges') reasonError.hidden = true;
  });
  document.addEventListener('sportfabrik:i18n-ready', function () {
    fillGruende();
    renderItem();
  });

  loadStammdaten();
})();
