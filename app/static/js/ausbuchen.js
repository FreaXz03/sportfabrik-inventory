// Ausbuchen per Scan (Phase C, Teilaufgabe C3): ein Scan = ein Stück (F15).
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  // Liste der Ausbuchungen aus dem Journal (`lagerbewegungen`), neueste
  // zuerst - mit Zeit, Person und Grund (23.09.2026).
  let buchungen = [];
  let listenOffset = 0;
  let listenWahl = null;
  // Der Scanner tippt schneller, als der Server antwortet: Scans werden
  // gesammelt und der Reihe nach gebucht, damit keiner verloren geht.
  const warteschlange = [];
  let bucht = false;
  let geladen = false;

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
    const name = [eintrag.marke, eintrag.bezeichnung].filter(Boolean).join(' ') || '—';
    const variante = [eintrag.farbe, eintrag.groesse].filter(Boolean).join(' / ');
    return variante ? name + ' (' + variante + ')' : name;
  }

  function grundText(grund) {
    // „sonstiges: <freier Text>" - der freie Text bleibt, wie er erfasst wurde.
    const [code, ...rest] = String(grund || '').split(': ');
    const bezeichnung = t('ausbuchen.reason.' + code);
    return rest.length ? bezeichnung + ': ' + rest.join(': ') : bezeichnung;
  }

  function fehlertext(fehler) {
    return fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
  }

  async function post(url, daten) {
    const antwort = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: daten === undefined ? undefined : JSON.stringify(daten)
    });
    const ergebnis = await antwort.json().catch(() => ({}));
    if (!antwort.ok) {
      throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('common.errors.request_failed'));
    }
    return ergebnis;
  }

  function zeitText(wert) {
    // Datum im Format der gewählten Sprache (de-CH: 24.09.2026), nicht des Browsers.
    const ort = { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' }[window.SportfabrikI18n.lang] || 'de-CH';
    const datum = new Date(wert);
    return datum.toLocaleDateString(ort) + ' ' + datum.toLocaleTimeString(ort, { hour: '2-digit', minute: '2-digit' });
  }

  function zeichnen() {
    $('leer').hidden = buchungen.length > 0;
    $('liste').hidden = buchungen.length === 0;
    $('rows').replaceChildren();
    for (const buchung of buchungen) {
      const tr = document.createElement('tr');
      tr.append(node('td', zeitText(buchung.zeitpunkt)));
      tr.append(node('td', [buchung.marke, buchung.bezeichnung].filter(Boolean).join(' ') || '—'));
      tr.append(node('td', [buchung.farbe, buchung.groesse].filter(Boolean).join(' / ') || '—'));
      tr.append(node('td', buchung.lagerort.code));
      tr.append(node('td', grundText(buchung.grund)));
      tr.append(node('td', buchung.benutzer_name || buchung.benutzer_kassennummer || '—'));
      const aktion = node('td');
      if (buchung.storniert) {
        aktion.append(node('span', t('ausbuchen.undone'), 'muted'));
      } else {
        const knopf = node('button', t('ausbuchen.undo'), 'secondary');
        knopf.type = 'button';
        knopf.addEventListener('click', () => rueckgaengig(buchung, knopf));
        aktion.append(knopf);
      }
      tr.append(aktion);
      $('rows').append(tr);
    }
  }

  async function listeLaden(anhaengen) {
    const parameter = new URLSearchParams();
    if (listenWahl === 'alle') parameter.set('alle', 'true');
    else if (listenWahl) parameter.set('lagerort_id', listenWahl);
    parameter.set('offset', String(anhaengen ? listenOffset : 0));
    try {
      const antwort = await fetch('/api/ausbuchungen?' + parameter.toString());
      const daten = await antwort.json().catch(() => ({}));
      if (!antwort.ok) throw new Error(typeof daten.detail === 'string' ? daten.detail : t('common.errors.request_failed'));
      buchungen = anhaengen ? buchungen.concat(daten.zeilen) : daten.zeilen;
      listenOffset = daten.offset + daten.zeilen.length;
      if (listenWahl === null) {
        listenWahl = daten.gewaehlt === null ? 'alle' : String(daten.gewaehlt);
        $('listeLagerort').value = listenWahl;
      }
      $('mehr').hidden = !daten.hat_mehr;
      zeichnen();
    } catch (fehler) {
      $('status').textContent = fehlertext(fehler);
    }
  }

  function meldung(ergebnis, key) {
    const text = t(key, {
      artikel: artikelName(ergebnis),
      lagerort: ergebnis.lagerort.code,
      menge: menge(ergebnis.bestand_nachher)
    });
    $('scanStatus').textContent = text;
    $('scanStatus').className = Number(ergebnis.bestand_nachher) < 0 ? 'warning-text' : '';
  }

  async function abarbeiten() {
    if (bucht) return;
    bucht = true;
    try {
      while (warteschlange.length) {
        const auftrag = warteschlange.shift();
        $('scanStatus').textContent = t('ausbuchen.booking');
        $('scanStatus').className = '';
        try {
          const ergebnis = await post('/api/ausbuchen', auftrag);
          listeLaden(false);
          // Reichte der Bestand nicht, ist trotzdem gebucht (F9) - gesagt
          // wird es aber, sonst merkt es niemand.
          meldung(ergebnis, ergebnis.bestand_reicht_nicht ? 'ausbuchen.booked_negative' : 'ausbuchen.booked');
        } catch (fehler) {
          $('scanStatus').textContent = fehlertext(fehler);
          $('scanStatus').className = 'warning-text';
        }
      }
    } finally {
      bucht = false;
    }
  }

  async function rueckgaengig(buchung, knopf) {
    knopf.disabled = true;
    try {
      const ergebnis = await post('/api/ausbuchen/' + buchung.bewegung_id + '/storno');
      listeLaden(false);
      meldung(ergebnis, 'ausbuchen.undo_done');
    } catch (fehler) {
      knopf.disabled = false;
      $('scanStatus').textContent = fehlertext(fehler);
      $('scanStatus').className = 'warning-text';
    }
  }

  function freitextUmschalten() {
    $('freitextFeld').hidden = $('grund').value !== 'sonstiges';
  }

  function gruendeFuellen(gruende) {
    const auswahl = $('grund');
    const gewaehlt = auswahl.value;
    auswahl.replaceChildren();
    for (const grund of gruende) auswahl.add(new Option(t('ausbuchen.reason.' + grund), grund));
    if (gewaehlt) auswahl.value = gewaehlt;
    freitextUmschalten();
  }

  let gruende = [];

  async function stammdatenLaden() {
    $('retry').hidden = true;
    try {
      const antwort = await fetch('/api/ausbuchen/stammdaten');
      const daten = await antwort.json();
      if (!antwort.ok) throw new Error(typeof daten.detail === 'string' ? daten.detail : t('ausbuchen.load_error'));
      const auswahl = $('lagerort');
      auswahl.replaceChildren();
      for (const lagerort of daten.lagerorte || []) {
        auswahl.add(new Option(lagerort.code + ' · ' + lagerort.name, lagerort.id));
      }
      if (daten.lagerort_aktiv) auswahl.value = String(daten.lagerort_aktiv);
      const filter = $('listeLagerort');
      while (filter.options.length > 1) filter.remove(1);
      for (const lagerort of daten.lagerorte || []) {
        filter.add(new Option(lagerort.code + ' · ' + lagerort.name, lagerort.id));
      }
      if (listenWahl) filter.value = listenWahl;
      gruende = daten.gruende || [];
      gruendeFuellen(gruende);
      geladen = true;
      $('status').textContent = '';
    } catch (fehler) {
      $('status').textContent = fehlertext(fehler);
      $('retry').hidden = false;
    }
  }

  // Ein Stück in die Warteschlange - per EAN (Scan) oder per Variante
  // (Auswahl aus dem Bestand, 24.09.2026). Der Grund gilt für beide Wege.
  function einreihen(ziel) {
    const grund = $('grund').value;
    const freitext = $('freitext').value.trim();
    if (grund === 'sonstiges' && !freitext) {
      $('scanStatus').textContent = t('errors.ausbuchung.text_required');
      $('scanStatus').className = 'warning-text';
      $('freitext').focus();
      return;
    }
    warteschlange.push({
      ...ziel,
      grund: grund,
      freitext: grund === 'sonstiges' ? freitext : null,
      lagerort_id: Number($('lagerort').value) || null
    });
    abarbeiten();
  }

  $('scanForm').addEventListener('submit', (ereignis) => {
    ereignis.preventDefault();
    const ean = $('ean').value.trim();
    $('ean').value = '';
    $('ean').focus();
    if (!ean || !geladen) return;
    einreihen({ ean: ean });
  });

  async function bestandZeigen() {
    if (!geladen) return;
    $('pickStatus').textContent = t('bestand.loading');
    try {
      const parameter = new URLSearchParams({ limit: '500' });
      if ($('lagerort').value) parameter.set('lagerort_id', $('lagerort').value);
      const q = $('pickFeld').value.trim();
      if (q) parameter.set('q', q);
      const antwort = await fetch('/api/bestand?' + parameter.toString());
      const daten = await antwort.json();
      if (!antwort.ok) throw new Error(typeof daten.detail === 'string' ? daten.detail : t('bestand.load_error'));
      const kopf = document.createElement('tr');
      for (const key of ['bestand.table_article', 'bestand.table_color', 'bestand.table_size', 'bestand.table_quantity', 'bestand.table_actions']) kopf.append(node('th', t(key)));
      const thead = document.createElement('thead');
      thead.append(kopf);
      const tbody = document.createElement('tbody');
      for (const zeile of daten.zeilen) {
        const tr = document.createElement('tr');
        const name = node('td');
        name.append(node('strong', [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') || '—'));
        const nummern = [zeile.lieferanten_artikelnr, zeile.ean].filter(Boolean).join(' · ');
        if (nummern) name.append(document.createElement('br'), node('span', nummern, 'muted'));
        const mengenZelle = node('td', menge(zeile.menge));
        const aktion = node('td');
        const knopf = node('button', t('ausbuchen.book'));
        knopf.type = 'button';
        knopf.addEventListener('click', () => {
          einreihen({ varianten_id: zeile.varianten_id });
          // Sofort sichtbar weniger; die genaue Zahl kommt mit der Meldung oben.
          zeile.menge = String(Number(zeile.menge) - 1);
          mengenZelle.textContent = menge(zeile.menge);
        });
        aktion.append(knopf);
        tr.append(name, node('td', zeile.farbe || '—'), node('td', zeile.groesse || '—'), mengenZelle, aktion);
        tbody.append(tr);
      }
      const tabelle = document.createElement('table');
      tabelle.append(thead, tbody);
      $('pickListe').replaceChildren(tabelle);
      $('pickListe').hidden = !daten.zeilen.length;
      $('pickStatus').textContent = daten.zeilen.length ? t('bestand.count_line', { anzahl: daten.total, summe: menge(daten.summe) }) : t('bestand.empty');
    } catch (fehler) {
      $('pickStatus').textContent = fehlertext(fehler);
    }
  }
  $('pickForm').addEventListener('submit', (ereignis) => {
    ereignis.preventDefault();
    bestandZeigen();
  });
  $('lagerort').addEventListener('change', () => {
    if ($('pickListe').childElementCount) bestandZeigen();
  });
  // Scanner schicken nach dem Barcode ein Enter - ausdrücklich abfangen,
  // statt sich auf das implizite Absenden des Formulars zu verlassen.
  $('ean').addEventListener('keydown', (ereignis) => {
    if (ereignis.key !== 'Enter') return;
    ereignis.preventDefault();
    $('scanForm').requestSubmit();
  });
  $('grund').addEventListener('change', freitextUmschalten);
  $('retry').addEventListener('click', stammdatenLaden);
  $('listeLagerort').addEventListener('change', () => {
    listenWahl = $('listeLagerort').value;
    listeLaden(false);
  });
  $('mehr').addEventListener('click', () => listeLaden(true));

  window.SportfabrikI18n.ready.then(async () => {
    await stammdatenLaden();
    listeLaden(false);
    document.addEventListener('sportfabrik:i18n-ready', () => {
      gruendeFuellen(gruende);
      zeichnen();
    });
  });
})();
