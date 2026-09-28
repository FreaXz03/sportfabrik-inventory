// Phone: book in goods without a document by hand (D27) - scan or type,
// collect a list, then book as one goods receipt. Employees may book only to
// their own stores; branch managers and head office to any location (rule 9,
// checked server-side).
(function () {
  var P = window.SFPhone;
  var t = P.t;
  var el = P.el;

  var TEXTFELDER = ['marke', 'bezeichnung', 'farbe', 'groesse', 'einheit', 'lieferanten_artikelnr', 'ean'];
  var PFLICHTFELDER = { marke: 'brand', bezeichnung: 'description', menge: 'quantity', uvp: 'uvp' };
  var ZAHL = /^[0-9]+([.,][0-9]{1,2})?$/;
  var EAN = /^([0-9]{8}|[0-9]{12,14})$/;

  var lagerortSelect = document.getElementById('lagerort');
  var dateField = document.getElementById('dateField');
  var dateInput = document.getElementById('eingangsdatum');
  var lieferantSelect = document.getElementById('lieferant');
  var kategorieSelect = document.getElementById('kategorie');
  var scanStatus = document.getElementById('scanStatus');
  var addError = document.getElementById('addError');
  var bookError = document.getElementById('bookError');
  var notice = document.getElementById('notice');
  var liste = document.getElementById('liste');
  var listEmpty = document.getElementById('listEmpty');
  var bookButton = document.getElementById('book');

  var lagerorte = [];
  var kategorien = [];
  var positionen = [];
  var busy = false;

  function feld(id) { return document.getElementById(id); }
  function wert(id) { return (feld(id).value || '').trim(); }

  function gewaehlterLagerort() {
    var id = Number(lagerortSelect.value);
    return lagerorte.find(function (lo) { return lo.id === id; }) || null;
  }

  function datumUmschalten() {
    var lagerort = gewaehlterLagerort();
    var verkauf = !lagerort || lagerort.verkauf;
    dateField.hidden = !verkauf;
    if (verkauf && !dateInput.value) dateInput.value = new Date().toISOString().slice(0, 10);
  }

  async function loadStammdaten() {
    try {
      var data = await P.fetchJson('/api/erfassen/stammdaten');
      lagerorte = data.lagerorte;
      lagerortSelect.replaceChildren();
      lagerorte.forEach(function (lo) { lagerortSelect.add(new Option(lo.code + ' · ' + lo.name, lo.id)); });
      if (data.lagerort_aktiv) lagerortSelect.value = String(data.lagerort_aktiv);

      lieferantSelect.replaceChildren(new Option(t('erfassen.supplier_none'), ''));
      (data.lieferanten || []).forEach(function (l) {
        var option = new Option(l.code + ' · ' + t('lieferant_gruppe.' + l.gruppe), l.id);
        option.dataset.code = l.code;
        lieferantSelect.add(option);
      });

      kategorien = data.kategorien || [];
      window.SportfabrikKategorien.fuellen(kategorieSelect, kategorien, { leerText: t('erfassen.kategorie_none') });
      if (data.heute) dateInput.value = dateInput.value || data.heute;
      datumUmschalten();
    } catch (error) {
      bookError.hidden = false;
      bookError.textContent = error.message;
    }
  }

  function felderLeeren() {
    TEXTFELDER.concat(['uvp', 'ek']).forEach(function (id) { feld(id).value = ''; });
    feld('menge').value = '1';
    kategorieSelect.value = '';
  }

  function artikelName(item) {
    return [item.marke, item.bezeichnung].filter(Boolean).join(' ') || '—';
  }

  function vorschlagUebernehmen(variante) {
    ['marke', 'bezeichnung', 'farbe', 'groesse', 'einheit', 'lieferanten_artikelnr'].forEach(function (id) {
      if (variante[id]) feld(id).value = variante[id];
    });
    if (variante.uvp) feld('uvp').value = variante.uvp;
    if (variante.ek) feld('ek').value = variante.ek;
    if (variante.kategorie) kategorieSelect.value = String(variante.kategorie.id);
    if (variante.lieferant && !lieferantSelect.value) {
      var passend = Array.from(lieferantSelect.options).find(function (o) { return o.dataset.code === variante.lieferant.code; });
      if (passend) lieferantSelect.value = passend.value;
    }
  }

  async function suchen() {
    var ean = wert('ean');
    if (!ean) { scanStatus.textContent = t('errors.erfassung.ean_missing'); return; }
    if (!EAN.test(ean)) { scanStatus.textContent = t('errors.erfassung.ean_format'); return; }
    scanStatus.textContent = t('erfassen.scan_searching');
    try {
      var data = await P.fetchJson('/api/erfassen/variante?ean=' + encodeURIComponent(ean));
      if (data.gefunden) {
        vorschlagUebernehmen(data.variante);
        scanStatus.textContent = t('erfassen.scan_found', { artikel: artikelName(data.variante) });
      } else {
        scanStatus.textContent = t('erfassen.scan_unknown');
      }
      feld('menge').focus();
      feld('menge').select();
    } catch (error) {
      scanStatus.textContent = error.message;
    }
  }

  function gepruefteEingabe() {
    var fehlend = Object.keys(PFLICHTFELDER).filter(function (id) { return !wert(id); })
      .map(function (id) { return t('fields.' + PFLICHTFELDER[id]); });
    if (fehlend.length) return { fehler: t('erfassen.missing_fields', { felder: fehlend.join(', ') }) };
    var menge = wert('menge');
    if (!ZAHL.test(menge) || Number(menge.replace(',', '.')) <= 0) return { fehler: t('erfassen.invalid_quantity') };
    for (var i = 0; i < 2; i++) {
      var id = ['uvp', 'ek'][i];
      if (wert(id) && !ZAHL.test(wert(id))) {
        return { fehler: t('erfassen.invalid_price', { field: t('fields.' + id) }) };
      }
    }
    var ean = wert('ean');
    if (ean && !EAN.test(ean)) return { fehler: t('errors.erfassung.ean_format') };
    var position = { menge: menge.replace(',', '.'), uvp: wert('uvp').replace(',', '.') };
    if (wert('ek')) position.ek = wert('ek').replace(',', '.');
    TEXTFELDER.forEach(function (id) { if (wert(id)) position[id] = wert(id); });
    if (wert('kategorie')) position.kategorie_id = Number(wert('kategorie'));
    return { position: position };
  }

  function renderList() {
    listEmpty.hidden = positionen.length > 0;
    liste.hidden = positionen.length === 0;
    liste.replaceChildren();
    positionen.forEach(function (position, index) {
      var li = el('li', 'm-position');
      var head = el('div', 'm-position-head');
      head.append(
        el('strong', null, artikelName(position)),
        el('span', 'm-sub', [
          [position.farbe, position.groesse].filter(Boolean).join(' · '),
          position.menge + (position.einheit ? ' ' + position.einheit : ''),
          position.uvp ? P.money(position.uvp) : null
        ].filter(Boolean).join(' · '))
      );
      var field = el('div', 'm-position-field');
      var remove = el('button', 'ghost', t('erfassen.remove'));
      remove.type = 'button';
      remove.addEventListener('click', function () {
        if (busy) return;
        positionen.splice(index, 1);
        renderList();
      });
      field.append(remove);
      li.append(head, field);
      liste.append(li);
    });
    bookButton.disabled = busy || positionen.length === 0;
  }

  document.getElementById('cameraButton').addEventListener('click', async function () {
    var code = await P.scan();
    if (!code) return;
    feld('ean').value = code;
    suchen();
  });
  document.getElementById('lookup').addEventListener('click', suchen);
  feld('ean').addEventListener('keydown', function (event) {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    suchen();
  });
  lagerortSelect.addEventListener('change', datumUmschalten);

  document.getElementById('add').addEventListener('click', function () {
    if (busy) return;
    var result = gepruefteEingabe();
    if (result.fehler) { addError.hidden = false; addError.textContent = result.fehler; return; }
    addError.hidden = true;
    positionen.push(result.position);
    renderList();
    felderLeeren();
    scanStatus.textContent = '';
    notice.hidden = true;
    feld('ean').focus();
  });

  bookButton.addEventListener('click', async function () {
    if (busy || !positionen.length) return;
    var lagerort = gewaehlterLagerort();
    busy = true;
    bookButton.classList.add('is-loading');
    bookError.hidden = true;
    renderList();
    try {
      var result = await P.fetchJson('/api/erfassen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          positionen: positionen,
          lagerort_id: lagerort ? lagerort.id : null,
          lieferant_id: lieferantSelect.value ? Number(lieferantSelect.value) : null,
          eingangsdatum: lagerort && !lagerort.verkauf ? null : dateInput.value || null
        })
      });
      positionen = [];
      renderList();
      notice.textContent = t('erfassen.booked', {
        positionen: result.positionen,
        lagerort: result.lagerort.code + ' · ' + result.lagerort.name,
        neu: result.neue_varianten,
        bekannt: result.bekannte_varianten
      }) + (result.eingangsdatum ? '' : ' ' + t('erfassen.booked_no_date'));
      notice.hidden = false;
      scanStatus.textContent = '';
    } catch (error) {
      bookError.hidden = false;
      bookError.textContent = error.message;
    } finally {
      busy = false;
      bookButton.classList.remove('is-loading');
      renderList();
    }
  });

  document.addEventListener('sportfabrik:i18n-ready', function () {
    renderList();
    datumUmschalten();
    if (lieferantSelect.options.length) lieferantSelect.options[0].textContent = t('erfassen.supplier_none');
    window.SportfabrikKategorien.fuellen(kategorieSelect, kategorien, { leerText: t('erfassen.kategorie_none'), wert: kategorieSelect.value });
  });

  loadStammdaten();
  renderList();
})();
