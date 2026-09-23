// Umlagern (Phase C, Teilaufgabe C4): die empfangende Filiale bucht beim
// Empfang (F5). Ware per Scan oder aus dem Bestand der Quelle sammeln, dann
// in einem Schritt buchen.
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let quellen = [];
  let ziele = [];
  // varianten_id → { variante, menge } - in der Reihenfolge des Erfassens.
  const liste = new Map();
  let suchTimer = null;
  let bucht = false;

  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function menge(wert) {
    const zahl = Number(wert);
    return Number.isFinite(zahl) ? String(zahl) : String(wert ?? '—');
  }

  function artikelName(eintrag) {
    return [eintrag.marke, eintrag.bezeichnung].filter(Boolean).join(' ') || '—';
  }

  function varianteText(eintrag) {
    return [eintrag.farbe, eintrag.groesse].filter(Boolean).join(' / ') || '—';
  }

  function fehlertext(fehler) {
    return fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
  }

  async function holen(url) {
    const antwort = await fetch(url);
    const daten = await antwort.json().catch(() => ({}));
    if (!antwort.ok) {
      throw new Error(typeof daten.detail === 'string' ? daten.detail : t('common.errors.request_failed'));
    }
    return daten;
  }

  const gewaehlt = (auswahl, lagerorte) => lagerorte.find((lo) => lo.id === Number($(auswahl).value)) || null;

  // Welche Regel für das Eingangsdatum gilt, hängt nur an `verkauf` von
  // Quelle und Ziel (Regel 6/D13, F10, F11) - nie am einzelnen Code.
  function regelZeigen() {
    const quelle = gewaehlt('quelle', quellen);
    const ziel = gewaehlt('ziel', ziele);
    let key = null;
    if (quelle && ziel && quelle.id === ziel.id) key = 'umlagern.rule_same';
    else if (ziel && !ziel.verkauf) key = 'umlagern.rule_to_external';
    else if (quelle && !quelle.verkauf) key = 'umlagern.rule_from_external';
    else if (quelle && ziel) key = 'umlagern.rule_between_branches';
    $('regel').textContent = key ? t(key) : '';
    $('regel').className = key === 'umlagern.rule_same' ? 'warning-text' : 'muted';
    $('datumFeld').hidden = !ziel || !ziel.verkauf;
    knopfSchalten();
  }

  function knopfSchalten() {
    const quelle = gewaehlt('quelle', quellen);
    const ziel = gewaehlt('ziel', ziele);
    $('buchen').disabled = bucht || !liste.size || !quelle || !ziel || quelle.id === ziel.id;
  }

  function zeichnen() {
    $('leer').hidden = liste.size > 0;
    $('liste').hidden = liste.size === 0;
    $('rows').replaceChildren();
    for (const [id, eintrag] of liste) {
      const tr = document.createElement('tr');
      tr.append(node('td', artikelName(eintrag.variante)));
      tr.append(node('td', varianteText(eintrag.variante)));
      const mengenZelle = node('td');
      const feld = document.createElement('input');
      feld.type = 'number';
      feld.min = '1';
      feld.step = '1';
      feld.value = String(eintrag.menge);
      feld.style.width = '6em';
      feld.setAttribute('aria-label', t('bestand.table_quantity'));
      feld.addEventListener('change', () => {
        const zahl = Number(feld.value);
        if (Number.isInteger(zahl) && zahl > 0) eintrag.menge = zahl;
        else feld.value = String(eintrag.menge);
      });
      mengenZelle.append(feld);
      tr.append(mengenZelle);
      const aktion = node('td');
      const knopf = node('button', t('erfassen.remove'), 'secondary');
      knopf.type = 'button';
      knopf.addEventListener('click', () => {
        liste.delete(id);
        zeichnen();
      });
      aktion.append(knopf);
      tr.append(aktion);
      $('rows').append(tr);
    }
    knopfSchalten();
  }

  function hinzufuegen(variante) {
    const eintrag = liste.get(variante.varianten_id);
    if (eintrag) eintrag.menge += 1;
    else liste.set(variante.varianten_id, { variante: variante, menge: 1 });
    zeichnen();
    $('scanStatus').className = '';
    $('scanStatus').textContent = t('umlagern.added', {
      artikel: artikelName(variante),
      menge: liste.get(variante.varianten_id).menge
    });
  }

  async function scannen(ean) {
    try {
      const daten = await holen('/api/erfassen/variante?ean=' + encodeURIComponent(ean));
      if (!daten.gefunden) {
        $('scanStatus').textContent = t('errors.ausbuchung.ean_unknown', { ean: ean });
        $('scanStatus').className = 'warning-text';
        return;
      }
      hinzufuegen(daten.variante);
    } catch (fehler) {
      $('scanStatus').textContent = fehlertext(fehler);
      $('scanStatus').className = 'warning-text';
    }
  }

  // Bestand der Quelle als Trefferliste - so lassen sich auch Varianten ohne
  // EAN (Regel 5) umlagern, und man sieht, was dort liegt.
  async function suchen() {
    const quelle = gewaehlt('quelle', quellen);
    const suche = $('suche').value.trim();
    $('treffer').replaceChildren();
    if (!quelle || !suche) return;
    try {
      const parameter = new URLSearchParams({ lagerort_id: String(quelle.id), q: suche, limit: '50' });
      const daten = await holen('/api/bestand?' + parameter.toString());
      if (!daten.zeilen.length) {
        $('treffer').append(node('p', t('bestand.empty'), 'muted'));
        return;
      }
      const tabelle = document.createElement('table');
      const kopf = document.createElement('tr');
      for (const key of ['bestand.table_article', 'bestand.table_variant', 'umlagern.table_source_stock', 'ausbuchen.table_actions']) {
        kopf.append(node('th', t(key)));
      }
      const thead = document.createElement('thead');
      thead.append(kopf);
      const tbody = document.createElement('tbody');
      for (const zeile of daten.zeilen) {
        const tr = document.createElement('tr');
        tr.append(node('td', artikelName(zeile)));
        tr.append(node('td', varianteText(zeile)));
        tr.append(node('td', menge(zeile.menge)));
        const aktion = node('td');
        const knopf = node('button', t('umlagern.add_one'), 'secondary');
        knopf.type = 'button';
        knopf.addEventListener('click', () => hinzufuegen(zeile));
        aktion.append(knopf);
        tr.append(aktion);
        tbody.append(tr);
      }
      tabelle.append(thead, tbody);
      const huelle = node('div', null, 'tablewrap');
      huelle.append(tabelle);
      $('treffer').append(huelle);
    } catch (fehler) {
      $('treffer').append(node('p', fehlertext(fehler), 'warning-text'));
    }
  }

  async function buchen() {
    const quelle = gewaehlt('quelle', quellen);
    const ziel = gewaehlt('ziel', ziele);
    bucht = true;
    knopfSchalten();
    $('bookStatus').className = '';
    $('bookStatus').textContent = t('ausbuchen.booking');
    try {
      const antwort = await fetch('/api/umlagerung', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quelle_id: quelle.id,
          ziel_id: ziel.id,
          eingangsdatum: ziel.verkauf ? $('eingangsdatum').value || null : null,
          positionen: [...liste].map(([id, eintrag]) => ({ varianten_id: id, menge: String(eintrag.menge) }))
        })
      });
      const ergebnis = await antwort.json().catch(() => ({}));
      if (!antwort.ok) {
        throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('common.errors.request_failed'));
      }
      let meldung = t('umlagern.booked', {
        stueck: menge(ergebnis.stueck),
        quelle: ergebnis.quelle.code,
        ziel: ergebnis.ziel.code
      });
      // Zu wenig Bestand an der Quelle: gebucht ist trotzdem (wie F9), gesagt
      // wird es aber - sonst merkt es niemand.
      if (ergebnis.fehlbestand.length) {
        meldung += ' ' + t('umlagern.source_short', { anzahl: ergebnis.fehlbestand.length, quelle: ergebnis.quelle.code });
        $('bookStatus').className = 'warning-text';
      }
      $('bookStatus').textContent = meldung;
      liste.clear();
      zeichnen();
      suchen();
    } catch (fehler) {
      $('bookStatus').className = 'warning-text';
      $('bookStatus').textContent = fehlertext(fehler);
    } finally {
      bucht = false;
      knopfSchalten();
    }
  }

  function lagerorteFuellen(auswahl, lagerorte, vorwahl) {
    const bisher = $(auswahl).value;
    $(auswahl).replaceChildren(new Option(t('umlagern.choose'), ''));
    for (const lagerort of lagerorte) $(auswahl).add(new Option(lagerort.code + ' · ' + lagerort.name, lagerort.id));
    $(auswahl).value = bisher || (vorwahl ? String(vorwahl) : '');
  }

  async function stammdatenLaden() {
    $('retry').hidden = true;
    try {
      const daten = await holen('/api/umlagerung/stammdaten');
      quellen = daten.quellen || [];
      ziele = daten.ziele || [];
      lagerorteFuellen('quelle', quellen, null);
      lagerorteFuellen('ziel', ziele, daten.ziel_aktiv);
      $('eingangsdatum').max = daten.heute;
      if (!$('eingangsdatum').value) $('eingangsdatum').value = daten.heute;
      $('status').textContent = '';
      regelZeigen();
    } catch (fehler) {
      $('status').textContent = fehlertext(fehler);
      $('retry').hidden = false;
    }
  }

  $('scanForm').addEventListener('submit', (ereignis) => {
    ereignis.preventDefault();
    const ean = $('ean').value.trim();
    $('ean').value = '';
    $('ean').focus();
    if (ean) scannen(ean);
  });
  // Scanner schicken nach dem Barcode ein Enter - ausdrücklich abfangen.
  $('ean').addEventListener('keydown', (ereignis) => {
    if (ereignis.key !== 'Enter') return;
    ereignis.preventDefault();
    $('scanForm').requestSubmit();
  });
  $('quelle').addEventListener('change', () => { regelZeigen(); suchen(); });
  $('ziel').addEventListener('change', regelZeigen);
  $('suche').addEventListener('input', () => {
    clearTimeout(suchTimer);
    suchTimer = setTimeout(suchen, 300);
  });
  $('buchen').addEventListener('click', buchen);
  $('retry').addEventListener('click', stammdatenLaden);

  window.SportfabrikI18n.ready.then(() => {
    stammdatenLaden();
    document.addEventListener('sportfabrik:i18n-ready', () => {
      lagerorteFuellen('quelle', quellen, null);
      lagerorteFuellen('ziel', ziele, null);
      regelZeigen();
      zeichnen();
    });
  });
})();
