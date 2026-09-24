// Ware von Hand erfassen: scannen oder eintippen, Liste sammeln, als
// Wareneingang ohne Beleg buchen (Phase B, Teilaufgabe B6).
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  // Feldname im Formular → Übersetzungs-Key des Feldnamens (für Meldungen).
  const PFLICHTFELDER = { marke: 'brand', bezeichnung: 'description', menge: 'quantity', uvp: 'uvp' };
  const TEXTFELDER = ['marke', 'bezeichnung', 'farbe', 'groesse', 'einheit', 'lieferanten_artikelnr', 'ean'];
  const ZAHL = /^[0-9]+([.,][0-9]{1,2})?$/;
  const EAN = /^([0-9]{8}|[0-9]{12,14})$/;

  let positionen = [];
  let lagerorte = [];
  let kategorien = [];
  let busy = false;
  // Zuletzt gebuchter Wareneingang - dafür lassen sich die Etiketten drucken
  // (Teilaufgabe B7): erfassen, dann auszeichnen.
  let letzterWareneingang = null;

  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function wert(id) {
    return ($(id).value || '').trim();
  }

  function artikelName(position) {
    return [position.marke, position.bezeichnung].filter(Boolean).join(' ') || '—';
  }

  function gewaehlterLagerort() {
    const id = Number($('lagerort').value);
    return lagerorte.find((eintrag) => eintrag.id === id) || null;
  }

  function datumUmschalten() {
    // Regel 6/D13: Ein Standort ohne Verkauf (GEWA, VEBO, Dietikon) bekommt
    // kein Eingangsdatum - die Reduktionsuhr startet erst in der Filiale.
    const lagerort = gewaehlterLagerort();
    const verkauf = !lagerort || lagerort.verkauf;
    $('datumFeld').hidden = !verkauf;
    $('datumHinweis').textContent = verkauf
      ? t('wareneingaenge.arrival_date_hint')
      : t('wareneingaenge.no_date_for_warehouse');
  }

  function kategorieAuswahlFuellen(wert) {
    window.SportfabrikKategorien.fuellen($('kategorie'), kategorien, {
      leerText: t('erfassen.kategorie_none'),
      wert: wert
    });
  }

  async function stammdatenLaden() {
    $('retry').hidden = true;
    $('status').textContent = '';
    try {
      const antwort = await fetch('/api/erfassen/stammdaten');
      const daten = await antwort.json();
      if (!antwort.ok) throw new Error(typeof daten.detail === 'string' ? daten.detail : t('erfassen.load_error'));
      lagerorte = daten.lagerorte || [];
      const auswahl = $('lagerort');
      auswahl.replaceChildren();
      for (const lagerort of lagerorte) auswahl.add(new Option(lagerort.code + ' · ' + lagerort.name, lagerort.id));
      if (daten.lagerort_aktiv) auswahl.value = String(daten.lagerort_aktiv);
      const lieferanten = $('lieferant');
      lieferanten.replaceChildren(new Option(t('erfassen.supplier_none'), ''));
      for (const lieferant of daten.lieferanten || []) {
        const option = new Option(lieferant.code + ' · ' + t('lieferant_gruppe.' + lieferant.gruppe), lieferant.id);
        option.dataset.code = lieferant.code;
        lieferanten.add(option);
      }
      // Kassenkategorie (Teilaufgabe B8): freiwillig - ohne Beleg gibt es
      // keinen FEDAS-Code, der sie vorschlagen könnte.
      kategorien = daten.kategorien || [];
      kategorieAuswahlFuellen('');
      // Datum vom Server: die Kassenrechner im Laden gehen nicht immer richtig.
      if (daten.heute && !$('eingangsdatum').value) $('eingangsdatum').value = daten.heute;
      datumUmschalten();
    } catch (fehler) {
      $('status').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('retry').hidden = false;
    }
  }

  function felderLeeren() {
    for (const id of TEXTFELDER) $(id).value = '';
    for (const id of ['uvp', 'ek']) $(id).value = '';
    $('menge').value = '1';
    $('kategorie').value = '';
  }

  function vorschlagUebernehmen(variante) {
    for (const id of ['marke', 'bezeichnung', 'farbe', 'groesse', 'einheit', 'lieferanten_artikelnr']) {
      if (variante[id]) $(id).value = variante[id];
    }
    // Letzter bekannter Preis als Vorschlag - änderbar (der UVP kann sich
    // zwischen zwei Lieferungen ändern).
    if (variante.uvp) $('uvp').value = variante.uvp;
    if (variante.ek) $('ek').value = variante.ek;
    // Bestehende Kategorie nur zeigen - gespeichert wird sie nicht neu, der
    // Server überschreibt sie ohnehin nie.
    if (variante.kategorie) $('kategorie').value = String(variante.kategorie.id);
    // Lieferant nur setzen, solange keiner gewählt ist: die Wahl gilt für den
    // ganzen Wareneingang, ein Scan soll sie nicht überschreiben.
    if (variante.lieferant && !$('lieferant').value) {
      const passend = Array.from($('lieferant').options).find((option) => option.dataset.code === variante.lieferant.code);
      if (passend) $('lieferant').value = passend.value;
    }
  }

  async function suchen() {
    const ean = wert('ean');
    if (!ean) {
      $('scanStatus').textContent = t('errors.erfassung.ean_missing');
      return;
    }
    if (!EAN.test(ean)) {
      $('scanStatus').textContent = t('errors.erfassung.ean_format');
      return;
    }
    $('scanStatus').textContent = t('erfassen.scan_searching');
    try {
      const antwort = await fetch('/api/erfassen/variante?ean=' + encodeURIComponent(ean));
      const daten = await antwort.json();
      if (!antwort.ok) throw new Error(typeof daten.detail === 'string' ? daten.detail : t('erfassen.lookup_failed'));
      if (daten.gefunden) {
        vorschlagUebernehmen(daten.variante);
        $('scanStatus').textContent = t('erfassen.scan_found', { artikel: artikelName(daten.variante) });
      } else {
        $('scanStatus').textContent = t('erfassen.scan_unknown');
      }
      $('menge').focus();
      $('menge').select();
    } catch (fehler) {
      $('scanStatus').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
    }
  }

  function gepruefteEingabe() {
    // Erste Prüfung im Browser, damit die Rückmeldung sofort kommt; die
    // verbindliche Prüfung macht der Server (app/services/manuelle_erfassung.py).
    const fehlend = Object.entries(PFLICHTFELDER)
      .filter(([id]) => !wert(id))
      .map(([, key]) => t('fields.' + key));
    if (fehlend.length) return { fehler: t('erfassen.missing_fields', { felder: fehlend.join(', ') }) };
    const menge = wert('menge');
    if (!ZAHL.test(menge) || Number(menge.replace(',', '.')) <= 0) {
      return { fehler: t('erfassen.invalid_quantity') };
    }
    for (const id of ['uvp', 'ek']) {
      if (wert(id) && !ZAHL.test(wert(id))) {
        return { fehler: t('erfassen.invalid_price', { field: t('fields.' + (id === 'uvp' ? 'uvp' : 'ek')) }) };
      }
    }
    const ean = wert('ean');
    if (ean && !EAN.test(ean)) return { fehler: t('errors.erfassung.ean_format') };
    const position = { menge: menge.replace(',', '.'), uvp: wert('uvp').replace(',', '.') };
    if (wert('ek')) position.ek = wert('ek').replace(',', '.');
    for (const id of TEXTFELDER) if (wert(id)) position[id] = wert(id);
    if (wert('kategorie')) position.kategorie_id = Number(wert('kategorie'));
    return { position: position };
  }

  function listeZeichnen() {
    const koerper = document.createDocumentFragment();
    positionen.forEach((position, index) => {
      const zeile = document.createElement('tr');
      zeile.append(node('td', artikelName(position)));
      zeile.append(node('td', [position.farbe, position.groesse].filter(Boolean).join(' / ') || '—'));
      zeile.append(node('td', position.ean || '—', 'id'));
      zeile.append(node('td', position.menge + (position.einheit ? ' ' + position.einheit : '')));
      zeile.append(node('td', position.uvp));
      const kategorie = kategorien.find((eintrag) => eintrag.id === position.kategorie_id);
      zeile.append(node('td', window.SportfabrikKategorien.name(kategorie) || '—'));
      const knopf = node('button', t('erfassen.remove'), 'secondary');
      knopf.type = 'button';
      knopf.setAttribute('aria-label', t('erfassen.remove_label', { artikel: artikelName(position) }));
      knopf.addEventListener('click', () => {
        if (busy) return;
        positionen.splice(index, 1);
        listeZeichnen();
      });
      const zelle = node('td');
      zelle.append(knopf);
      zeile.append(zelle);
      koerper.append(zeile);
    });
    $('rows').replaceChildren(koerper);
    $('listWrap').hidden = positionen.length === 0;
    $('listEmpty').hidden = positionen.length > 0;
    $('book').disabled = busy || positionen.length === 0;
  }

  async function buchen() {
    if (busy) return;
    if (!positionen.length) {
      $('bookStatus').textContent = t('erfassen.book_empty');
      return;
    }
    const lagerort = gewaehlterLagerort();
    busy = true;
    $('book').disabled = true;
    $('bookStatus').textContent = t('erfassen.booking');
    try {
      const antwort = await fetch('/api/erfassen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          positionen: positionen,
          lagerort_id: lagerort ? lagerort.id : null,
          lieferant_id: $('lieferant').value ? Number($('lieferant').value) : null,
          eingangsdatum: lagerort && !lagerort.verkauf ? null : $('eingangsdatum').value || null
        })
      });
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('erfassen.load_error'));
      positionen = [];
      listeZeichnen();
      const meldung = t('erfassen.booked', {
        positionen: ergebnis.positionen,
        lagerort: ergebnis.lagerort.code + ' · ' + ergebnis.lagerort.name,
        neu: ergebnis.neue_varianten,
        bekannt: ergebnis.bekannte_varianten
      });
      $('bookStatus').textContent = ergebnis.eingangsdatum ? meldung : meldung + ' ' + t('erfassen.booked_no_date');
      letzterWareneingang = ergebnis.wareneingang_id;
      $('printBox').hidden = false;
      $('addStatus').textContent = '';
      $('scanStatus').textContent = '';
      $('ean').focus();
    } catch (fehler) {
      $('bookStatus').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
    } finally {
      busy = false;
      listeZeichnen();
    }
  }

  $('printLabels').addEventListener('click', () => {
    if (!letzterWareneingang) return;
    window.open('/api/wareneingaenge/' + letzterWareneingang + '/etiketten.pdf', '_blank', 'noopener');
  });
  $('artikelForm').addEventListener('submit', (ereignis) => {
    ereignis.preventDefault();
    if (busy) return;
    const geprueft = gepruefteEingabe();
    if (geprueft.fehler) {
      $('addStatus').textContent = geprueft.fehler;
      return;
    }
    positionen.push(geprueft.position);
    $('printBox').hidden = true;
    listeZeichnen();
    felderLeeren();
    $('addStatus').textContent = t('erfassen.added');
    $('scanStatus').textContent = '';
    $('bookStatus').textContent = '';
    $('ean').focus();
  });
  // Scanner: Barcode + Enter im EAN-Feld sucht, statt die Position zu speichern.
  $('ean').addEventListener('keydown', (ereignis) => {
    if (ereignis.key !== 'Enter') return;
    ereignis.preventDefault();
    suchen();
  });
  $('lookup').addEventListener('click', suchen);
  $('lagerort').addEventListener('change', datumUmschalten);
  $('book').addEventListener('click', buchen);
  $('retry').addEventListener('click', stammdatenLaden);
  // Erst starten, wenn der Übersetzungs-Katalog da ist (sonst stünden die
  // Texte als Keys da). `ready` löst nach dem ersten i18n-ready aus, deshalb
  // wird der Listener für Sprachwechsel erst danach angemeldet.
  window.SportfabrikI18n.ready.then(() => {
    stammdatenLaden();
    listeZeichnen();
    document.addEventListener('sportfabrik:i18n-ready', () => {
      // Sprachwechsel: die vom Skript erzeugten Texte neu schreiben.
      listeZeichnen();
      datumUmschalten();
      const lieferanten = $('lieferant');
      if (lieferanten.options.length) lieferanten.options[0].textContent = t('erfassen.supplier_none');
      kategorieAuswahlFuellen($('kategorie').value);
    });
  });
})();
