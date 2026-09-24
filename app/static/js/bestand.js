// Bestand je Variante × Lagerort (Phase C, Teilaufgabe C2).
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let offset = 0;
  let rechte = { ausbuchen: false, korrektur_lagerorte: [] };
  let lagerorteGesetzt = false;
  let suchTimer = null;
  // Welche Filiale gezeigt wird: null heisst „noch nichts gewählt" - dann
  // entscheidet der Server und nimmt die aktive Filiale. Die Auswahl im
  // `<select>` taugt dafür nicht: sie steht am Anfang auf „alle", weil die
  // Filialen erst mit der ersten Antwort ankommen.
  let wahl = null;
  // Filter aus der Adresse - Links unter „Anstehend" in der Übersicht
  // (24.09.2026): negativer Bestand oder eine fällige/baldige Reduktion.
  const adresse = new URLSearchParams(location.search);
  let vorgabe = null;
  if (adresse.get('nur_negativ') === 'true') vorgabe = { nur_negativ: 'true' };
  else if (adresse.get('reduktion')) {
    vorgabe = { reduktion: adresse.get('reduktion'), reduktion_status: adresse.get('reduktion_status') === 'bald' ? 'bald' : 'faellig' };
  }

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

  // Die Hauptgruppe bleibt, wie sie in der Kasse heisst (Regel 8) - nicht übersetzt.
  function bestandsZeile(zeile) {
    const tr = document.createElement('tr');
    tr.append(artikelZelle(zeile));
    tr.append(node('td', zeile.hauptgruppe || '—', zeile.hauptgruppe ? '' : 'muted'));
    tr.append(node('td', zeile.farbe || '—'));
    tr.append(node('td', zeile.groesse || '—'));
    tr.append(node('td', zeile.lagerort.code + ' · ' + zeile.lagerort.name));
    const mengenZelle = node('td', menge(zeile.menge));
    tr.append(mengenZelle);
    tr.append(datumsZelle(zeile));
    tr.append(abbuchenZelle(zeile, tr, mengenZelle));
    if (Number(zeile.menge) < 0) tr.className = 'warning';
    return tr;
  }

  // Menge 0 gehört nicht in die Bestandsansicht (23.09.2026) - der Artikel
  // bleibt im Stamm. Die Zeile verschwindet, sobald sie auf 0 gebucht ist.
  function ausblendenWennLeer(zeile, tr) {
    if (Number(zeile.menge) !== 0) return;
    const editor = tr.nextElementSibling;
    if (editor && editor.classList.contains('korrektur')) editor.remove();
    tr.remove();
  }

  // Vorübergehender Test-Knopf (23.09.2026): bucht ein Stück als normale
  // Lagerbewegung ab (Regel 2) - derselbe Weg wie die Seite „Ausbuchen".
  // Geht auch für Varianten ohne EAN, die sich nicht scannen lassen.
  function abbuchenZelle(zeile, tr, mengenZelle) {
    const zelle = node('td');
    const knopf = node('button', t('bestand.minus_one'), 'secondary');
    knopf.type = 'button';
    knopf.title = t('bestand.minus_one_label');
    knopf.setAttribute('aria-label', t('bestand.minus_one_label'));
    knopf.addEventListener('click', async function () {
      knopf.disabled = true;
      try {
        const antwort = await fetch('/api/ausbuchen', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            varianten_id: zeile.varianten_id,
            lagerort_id: zeile.lagerort.id,
            grund: 'test'
          })
        });
        const ergebnis = await antwort.json().catch(() => ({}));
        if (!antwort.ok) {
          throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('common.errors.request_failed'));
        }
        zeile.menge = ergebnis.bestand_nachher;
        mengenZelle.textContent = menge(zeile.menge);
        tr.className = Number(zeile.menge) < 0 ? 'warning' : '';
        ausblendenWennLeer(zeile, tr);
        const name = [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') || '—';
        $('status').textContent = t(
          ergebnis.bestand_reicht_nicht ? 'bestand.minus_one_negative' : 'bestand.minus_one_done',
          { artikel: name, lagerort: zeile.lagerort.code, menge: menge(zeile.menge) }
        );
      } catch (fehler) {
        $('status').textContent =
          fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      } finally {
        knopf.disabled = false;
      }
    });
    if (rechte.ausbuchen) zelle.append(knopf);
    if (!rechte.korrektur_lagerorte.includes(zeile.lagerort.id)) return zelle;
    const zaehlen = node('button', t('bestand.count'), 'secondary');
    zaehlen.type = 'button';
    zaehlen.addEventListener('click', () => zaehlenOeffnen(zeile, tr, mengenZelle));
    zelle.append(' ', zaehlen);
    return zelle;
  }

  // Korrektur (Phase C, Teilaufgabe C5): gezählte Menge eingeben, gebucht
  // wird die Differenz (23.09.2026). Die Gründe kommen vom Server.
  let korrekturGruende = null;

  async function gruendeLaden() {
    if (korrekturGruende) return korrekturGruende;
    const antwort = await fetch('/api/korrektur/gruende');
    const daten = await antwort.json().catch(() => ({}));
    if (!antwort.ok) throw new Error(typeof daten.detail === 'string' ? daten.detail : t('common.errors.request_failed'));
    korrekturGruende = daten.gruende || [];
    return korrekturGruende;
  }

  async function zaehlenOeffnen(zeile, tr, mengenZelle) {
    const offen = tr.nextElementSibling;
    if (offen && offen.classList.contains('korrektur')) {
      offen.remove();
      return;
    }
    let gruende;
    try {
      gruende = await gruendeLaden();
    } catch (fehler) {
      $('status').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      return;
    }
    const editor = node('tr', null, 'korrektur');
    const zelle = node('td');
    zelle.colSpan = 9;
    const form = node('form', null, 'filters');
    form.noValidate = true;

    const mengenLabel = node('label');
    mengenLabel.append(node('span', t('bestand.counted_label')));
    const feld = document.createElement('input');
    feld.type = 'number';
    feld.min = '0';
    feld.step = '1';
    feld.value = menge(zeile.menge);
    feld.style.width = '7em';
    mengenLabel.append(feld);

    const grundLabel = node('label');
    grundLabel.append(node('span', t('ausbuchen.reason_label')));
    const auswahl = document.createElement('select');
    for (const grund of gruende) auswahl.add(new Option(t('bestand.correction_reason.' + grund), grund));
    grundLabel.append(auswahl);

    const textLabel = node('label');
    textLabel.hidden = true;
    textLabel.append(node('span', t('ausbuchen.text_label')));
    const text = document.createElement('input');
    text.type = 'text';
    text.maxLength = 150;
    textLabel.append(text);
    auswahl.addEventListener('change', () => { textLabel.hidden = auswahl.value !== 'sonstiges'; });

    const buchen = node('button', t('bestand.correction_book'));
    buchen.type = 'submit';
    const abbrechen = node('button', t('common.cancel'), 'secondary');
    abbrechen.type = 'button';
    abbrechen.addEventListener('click', () => editor.remove());

    form.append(mengenLabel, grundLabel, textLabel, buchen, abbrechen);
    // Enter im Mengenfeld bucht - ausdrücklich, wie beim Scanfeld.
    for (const eingabe of [feld, text]) {
      eingabe.addEventListener('keydown', (ereignis) => {
        if (ereignis.key !== 'Enter') return;
        ereignis.preventDefault();
        form.requestSubmit();
      });
    }
    form.addEventListener('submit', async (ereignis) => {
      ereignis.preventDefault();
      buchen.disabled = true;
      try {
        const antwort = await fetch('/api/korrektur', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            varianten_id: zeile.varianten_id,
            lagerort_id: zeile.lagerort.id,
            gezaehlt: feld.value.trim(),
            grund: auswahl.value,
            freitext: auswahl.value === 'sonstiges' ? text.value.trim() : null
          })
        });
        const ergebnis = await antwort.json().catch(() => ({}));
        if (!antwort.ok) {
          throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('common.errors.request_failed'));
        }
        zeile.menge = ergebnis.bestand_nachher;
        mengenZelle.textContent = menge(zeile.menge);
        tr.className = Number(zeile.menge) < 0 ? 'warning' : '';
        ausblendenWennLeer(zeile, tr);
        const name = [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') || '—';
        const differenz = Number(ergebnis.differenz);
        $('status').textContent = ergebnis.gebucht
          ? t('bestand.correction_done', {
            artikel: name,
            vorher: menge(ergebnis.bestand_vorher),
            nachher: menge(ergebnis.bestand_nachher),
            differenz: (differenz > 0 ? '+' : '') + menge(ergebnis.differenz)
          })
          : t('bestand.correction_unchanged', { artikel: name, menge: menge(ergebnis.bestand_nachher) });
        editor.remove();
      } catch (fehler) {
        $('status').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
        buchen.disabled = false;
      }
    });
    zelle.append(form);
    editor.append(zelle);
    tr.after(editor);
    feld.focus();
    feld.select();
  }

  function tabelle(zeilen) {
    const kopf = document.createElement('tr');
    for (const key of ['table_article', 'table_hauptgruppe', 'table_color', 'table_size', 'table_lagerort', 'table_quantity', 'table_arrival_date', 'table_actions']) {
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
    // Ohne Filiale (nur Admin, „Alle Filialen") bleibt es bei „alle".
    wahl = gewaehlt === null || gewaehlt === undefined ? 'alle' : String(gewaehlt);
    auswahl.value = wahl;
    lagerorteGesetzt = true;
  }

  function vorgabeZeigen() {
    $('vorgabe').hidden = !vorgabe;
    if (!vorgabe) return;
    const key = vorgabe.nur_negativ
      ? 'bestand.filter_active.negative'
      : 'bestand.filter_active.' + (vorgabe.reduktion_status === 'bald' ? 'reduction_soon' : 'reduction_due');
    $('vorgabeText').textContent = t('filter_active.label') + ' ' + t(key, { stufe: vorgabe.reduktion });
  }

  function vorgabeWeg() {
    vorgabe = null;
    vorgabeZeigen();
    history.replaceState(null, '', location.pathname);
  }

  // Welche Filiale gezeigt wird, steht gross im Titel (Inbox 24.09.2026) -
  // die kleine Auswahl darunter bleibt zum Wechseln.
  function titelZeigen() {
    const auswahl = $('lagerort');
    const option = auswahl.options[auswahl.selectedIndex];
    $('titelFiliale').textContent = lagerorteGesetzt && option ? '· ' + option.textContent : '';
  }

  function anfrage(neuerOffset) {
    const parameter = new URLSearchParams(vorgabe || {});
    if (wahl === 'alle') parameter.set('alle', 'true');
    else if (wahl) parameter.set('lagerort_id', wahl);
    const suche = $('suche').value.trim();
    if (suche) parameter.set('q', suche);
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
      rechte = daten.rechte || { ausbuchen: false, korrektur_lagerorte: [] };
      lagerorteFuellen(daten.lagerorte || [], daten.gewaehlt);
      titelZeigen();
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

  $('lagerort').addEventListener('change', function () {
    wahl = $('lagerort').value;
    // Die Reduktion gilt je Filiale - bei einem Wechsel wieder alles zeigen.
    if (vorgabe && vorgabe.reduktion) vorgabeWeg();
    neuLaden();
  });
  $('suche').addEventListener('input', function () {
    // Tippen soll nicht bei jedem Zeichen eine Abfrage auslösen.
    clearTimeout(suchTimer);
    suchTimer = setTimeout(neuLaden, 300);
  });
  $('retry').addEventListener('click', neuLaden);
  $('vorgabeWeg').addEventListener('click', function () {
    vorgabeWeg();
    neuLaden();
  });
  // Inbox 24.09.2026: gleich lostippen können - Suchfeld beim Öffnen aktiv.
  $('suche').focus();
  $('mehr').addEventListener('click', function () { laden(true); });

  // Erst laden, wenn der Übersetzungs-Katalog da ist (sonst stünden die
  // Spaltenköpfe als Keys da), danach bei jedem Sprachwechsel neu zeichnen.
  // `ready` löst nach dem ersten i18n-ready aus, deshalb wird der Listener
  // erst danach angemeldet - sonst würde die Liste doppelt geladen.
  window.SportfabrikI18n.ready.then(() => {
    vorgabeZeigen();
    neuLaden();
    document.addEventListener('sportfabrik:i18n-ready', function () {
      vorgabeZeigen();
      neuLaden();
    });
  });
})();
