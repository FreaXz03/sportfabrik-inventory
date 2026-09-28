// Phone: transfer goods between locations, reserved for branch managers and
// head office (rule 9). Booked on receipt: removal at the source and
// addition at the destination in one step (F5).
(function () {
  var P = window.SFPhone;
  var t = P.t;
  var el = P.el;

  var quelleSelect = document.getElementById('quelle');
  var zielSelect = document.getElementById('ziel');
  var regel = document.getElementById('regel');
  var dateInput = document.getElementById('eingangsdatum');
  var liste = document.getElementById('liste');
  var leer = document.getElementById('leer');
  var buchen = document.getElementById('buchen');
  var bookError = document.getElementById('bookError');
  var notice = document.getElementById('notice');

  var quellen = [];
  var ziele = [];
  var items = new Map(); // varianten_id -> { item, menge }
  var busy = false;

  function fill(select, lagerorte, preselect) {
    var current = select.value;
    select.replaceChildren(new Option(t('umlagern.choose'), ''));
    lagerorte.forEach(function (lo) {
      select.add(new Option(lo.code + ' · ' + lo.name, lo.id));
    });
    select.value = current || (preselect ? String(preselect) : '');
  }

  function chosen(select, lagerorte) {
    var id = Number(select.value);
    return lagerorte.find(function (lo) { return lo.id === id; }) || null;
  }

  function showRule() {
    var quelle = chosen(quelleSelect, quellen);
    var ziel = chosen(zielSelect, ziele);
    var key = null;
    if (quelle && ziel && quelle.id === ziel.id) key = 'umlagern.rule_same';
    else if (ziel && !ziel.verkauf) key = 'umlagern.rule_to_external';
    else if (quelle && !quelle.verkauf) key = 'umlagern.rule_from_external';
    else if (quelle && ziel) key = 'umlagern.rule_between_branches';
    regel.textContent = key ? t(key) : '';
    regel.className = key === 'umlagern.rule_same' ? 'warning-text' : 'm-hint';
    updateButton();
  }

  function updateButton() {
    var quelle = chosen(quelleSelect, quellen);
    var ziel = chosen(zielSelect, ziele);
    buchen.disabled = busy || !items.size || !quelle || !ziel || quelle.id === ziel.id;
  }

  function renderList() {
    leer.hidden = items.size > 0;
    liste.hidden = items.size === 0;
    liste.replaceChildren();
    items.forEach(function (entry, id) {
      var li = el('li', 'm-position');
      var head = el('div', 'm-position-head');
      head.append(
        el('strong', null, [entry.item.brand, entry.item.description].filter(Boolean).join(' ') || '—'),
        el('span', 'm-sub', P.variantText(entry.item))
      );
      var field = el('div', 'm-position-field');
      var stepper = el('div', 'm-stepper m-stepper-inline');
      var minus = el('button', null);
      minus.type = 'button';
      minus.className = 'secondary icon-only';
      minus.append(P.icon('minus'));
      minus.setAttribute('aria-label', t('phone.count_minus'));
      var input = el('input');
      input.type = 'text';
      input.inputMode = 'numeric';
      input.value = String(entry.menge);
      var plus = el('button', null);
      plus.type = 'button';
      plus.className = 'secondary icon-only';
      plus.append(P.icon('plus'));
      plus.setAttribute('aria-label', t('phone.count_plus'));
      function setMenge(value) {
        var n = Math.max(1, Math.round(value));
        entry.menge = n;
        input.value = String(n);
      }
      minus.addEventListener('click', function () { setMenge(entry.menge - 1); });
      plus.addEventListener('click', function () { setMenge(entry.menge + 1); });
      input.addEventListener('change', function () {
        var n = parseInt(input.value, 10);
        setMenge(isNaN(n) ? entry.menge : n);
      });
      stepper.append(minus, input, plus);
      var remove = el('button', 'ghost', t('erfassen.remove'));
      remove.type = 'button';
      remove.addEventListener('click', function () { items.delete(id); renderList(); });
      field.append(stepper, remove);
      li.append(head, field);
      liste.append(li);
    });
    updateButton();
  }

  function addItem(item) {
    var entry = items.get(item.id);
    if (entry) entry.menge += 1;
    else items.set(item.id, { item: item, menge: 1 });
    renderList();
  }

  var pick = P.picker({
    container: document.getElementById('picker'),
    onPick: addItem
  });

  async function loadStammdaten() {
    try {
      var data = await P.fetchJson('/api/umlagerung/stammdaten');
      quellen = data.quellen;
      ziele = data.ziele;
      fill(quelleSelect, quellen, data.quelle_aktiv);
      fill(zielSelect, ziele, null);
      dateInput.max = data.heute;
      if (!dateInput.value) dateInput.value = data.heute;
      showRule();
    } catch (error) {
      bookError.hidden = false;
      bookError.textContent = error.message;
    }
  }

  buchen.addEventListener('click', async function () {
    var quelle = chosen(quelleSelect, quellen);
    var ziel = chosen(zielSelect, ziele);
    if (busy || !quelle || !ziel || quelle.id === ziel.id || !items.size) return;
    busy = true;
    bookError.hidden = true;
    buchen.classList.add('is-loading');
    updateButton();
    try {
      var result = await P.fetchJson('/api/umlagerung', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quelle_id: quelle.id,
          ziel_id: ziel.id,
          versanddatum: dateInput.value || null,
          positionen: Array.from(items, function (pair) {
            return { varianten_id: pair[0], menge: String(pair[1].menge) };
          })
        })
      });
      var message = t('umlagern.booked', { stueck: P.qty(result.stueck), quelle: result.quelle.code, ziel: result.ziel.code });
      if (result.fehlbestand && result.fehlbestand.length) {
        message += ' ' + t('umlagern.source_short', { anzahl: result.fehlbestand.length, quelle: result.quelle.code });
      }
      items.clear();
      renderList();
      pick.clear();
      notice.textContent = message;
      notice.hidden = false;
    } catch (error) {
      bookError.hidden = false;
      bookError.textContent = error.message;
    } finally {
      busy = false;
      buchen.classList.remove('is-loading');
      updateButton();
    }
  });

  quelleSelect.addEventListener('change', showRule);
  zielSelect.addEventListener('change', showRule);
  document.addEventListener('sportfabrik:i18n-ready', function () {
    fill(quelleSelect, quellen, null);
    fill(zielSelect, ziele, null);
    showRule();
    renderList();
  });

  loadStammdaten();
})();
