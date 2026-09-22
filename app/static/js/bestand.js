// Bestand je Variante × Lagerort (Phase C, Teilaufgabe C2).
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let offset = 0;
  let lagerorteGesetzt = false;
  let suchTimer = null;

  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function menge(wert) {
    // Ganze Stückzahlen ohne Nachkommastellen zeigen ("5" statt "5.00").
    const zahl = Number(wert);
    return Number.isFinite(zahl) ? String(zahl) : String(wert ?? '—');
  }

  function datum(wert) {
    return wert ? wert.slice(0, 10).split('-').reverse().join('.') : null;
  }

  function artikelZelle(zeile) {
    const zelle = node('td');
    zelle.append(node('strong', [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') || '—'));
    const nummern = [zeile.lieferanten_artikelnr, zeile.ean].filter(Boolean).join(' · ');
    if (nummern) zelle.append(document.createElement('br'), node('span', nummern, 'muted'));
    return zelle;
  }

  function datumsZelle(zeile) {
    const gezeigt = datum(zeile.aeltestes_eingangsdatum);
    if (gezeigt) return node('td', gezeigt);
    // Ohne Verkauf gibt es bewusst kein Eingangsdatum (Regel 6/D13); fehlt es
    // in einer Filiale, stammt der Bestand aus einer Zeit ohne Datum.
    const key = zeile.lagerort.verkauf ? 'bestand.no_arrival_date' : 'bestand.external_no_date';
    return node('td', t(key), 'muted');
  }

  function bestandsZeile(zeile) {
    const tr = document.createElement('tr');
    tr.append(artikelZelle(zeile));
    tr.append(node('td', [zeile.farbe, zeile.groesse].filter(Boolean).join(' / ') || '—'));
    tr.append(node('td', zeile.lagerort.code + ' · ' + zeile.lagerort.name));
    tr.append(node('td', menge(zeile.menge)));
    tr.append(datumsZelle(zeile));
    return tr;
  }

  function tabelle(zeilen) {
    const kopf = document.createElement('tr');
    for (const key of ['table_article', 'table_variant', 'table_lagerort', 'table_quantity', 'table_arrival_date']) {
      kopf.append(node('th', t('bestand.' + key)));
    }
    const thead = document.createElement('thead');
    thead.append(kopf);
    const tbody = document.createElement('tbody');
    tbody.id = 'zeilen';
    for (const zeile of zeilen) tbody.append(bestandsZeile(zeile));
    const tabelleEl = document.createElement('table');
    tabelleEl.append(thead, tbody);
    const huelle = node('div', null, 'tablewrap');
    huelle.append(tabelleEl);
    return huelle;
  }

  function lagerorteFuellen(lagerorte, gewaehlt) {
    if (lagerorteGesetzt) return;
    const auswahl = $('lagerort');
    for (const lagerort of lagerorte) {
      const option = document.createElement('option');
      option.value = String(lagerort.id);
      option.textContent = lagerort.code + ' · ' + lagerort.name;
      auswahl.append(option);
    }
    if (gewaehlt !== null && gewaehlt !== undefined) auswahl.value = String(gewaehlt);
    lagerorteGesetzt = true;
  }

  function anfrage(neuerOffset) {
    const parameter = new URLSearchParams();
    const wahl = $('lagerort').value;
    if (wahl === 'alle') parameter.set('alle', 'true');
    else if (wahl) parameter.set('lagerort_id', wahl);
    const suche = $('suche').value.trim();
    if (suche) parameter.set('q', suche);
    parameter.set('nur_vorhanden', $('nurVorhanden').checked ? 'true' : 'false');
    parameter.set('offset', String(neuerOffset));
    return '/api/bestand?' + parameter.toString();
  }

  async function laden(anhaengen) {
    $('retry').hidden = true;
    $('status').textContent = t('bestand.loading');
    try {
      const antwort = await fetch(anfrage(anhaengen ? offset : 0));
      const daten = await antwort.json();
      if (!antwort.ok) {
        throw new Error(typeof daten.detail === 'string' ? daten.detail : t('bestand.load_error'));
      }
      lagerorteFuellen(daten.lagerorte || [], daten.gewaehlt);
      if (anhaengen && $('zeilen')) {
        for (const zeile of daten.zeilen) $('zeilen').append(bestandsZeile(zeile));
      } else {
        $('tabelle').replaceChildren();
        if (daten.zeilen.length) $('tabelle').append(tabelle(daten.zeilen));
      }
      offset = daten.offset + daten.zeilen.length;
      $('empty').hidden = daten.total !== 0;
      $('mehr').hidden = !daten.hat_mehr;
      $('status').textContent = daten.total
        ? t('bestand.count_line', { anzahl: daten.total, summe: menge(daten.summe) })
        : '';
    } catch (fehler) {
      $('tabelle').replaceChildren();
      $('mehr').hidden = true;
      $('status').textContent =
        fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('retry').hidden = false;
    }
  }

  function neuLaden() {
    offset = 0;
    laden(false);
  }

  $('lagerort').addEventListener('change', neuLaden);
  $('nurVorhanden').addEventListener('change', neuLaden);
  $('suche').addEventListener('input', function () {
    // Tippen soll nicht bei jedem Zeichen eine Abfrage auslösen.
    clearTimeout(suchTimer);
    suchTimer = setTimeout(neuLaden, 300);
  });
  $('retry').addEventListener('click', neuLaden);
  $('mehr').addEventListener('click', function () { laden(true); });

  // Erst laden, wenn der Übersetzungs-Katalog da ist (sonst stünden die
  // Spaltenköpfe als Keys da), danach bei jedem Sprachwechsel neu zeichnen.
  // `ready` löst nach dem ersten i18n-ready aus, deshalb wird der Listener
  // erst danach angemeldet - sonst würde die Liste doppelt geladen.
  window.SportfabrikI18n.ready.then(() => {
    neuLaden();
    document.addEventListener('sportfabrik:i18n-ready', neuLaden);
  });
})();
