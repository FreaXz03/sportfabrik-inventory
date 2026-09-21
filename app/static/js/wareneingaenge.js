// Erwartete Lieferungen und ihre Ankunftsbestätigung (Phase B, Teilaufgabe B5).
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let aktiverLagerort = null;

  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function datum(wert) {
    return wert ? wert.slice(0, 10).split('-').reverse().join('.') : '—';
  }

  function menge(wert) {
    // Ganze Stückzahlen ohne Nachkommastellen zeigen ("5" statt "5.00").
    const zahl = Number(wert);
    return Number.isFinite(zahl) ? String(zahl) : String(wert ?? '—');
  }

  function artikelZelle(position) {
    const zelle = node('td');
    zelle.append(node('strong', [position.marke, position.bezeichnung].filter(Boolean).join(' ') || '—'));
    const nummer = [position.lieferanten_artikelnr, position.ean].filter(Boolean).join(' · ');
    if (nummer) {
      zelle.append(document.createElement('br'), node('span', nummer, 'muted'));
    }
    return zelle;
  }

  function positionsZeile(position) {
    const zeile = document.createElement('tr');
    zeile.append(artikelZelle(position));
    zeile.append(node('td', [position.farbe, position.groesse].filter(Boolean).join(' / ') || '—'));
    for (const wert of [position.menge_erwartet, position.menge_eingetroffen, position.menge_offen]) {
      zeile.append(node('td', menge(wert) + (position.einheit ? ' ' + position.einheit : '')));
    }
    const eingabe = document.createElement('input');
    eingabe.type = 'number';
    eingabe.min = '0';
    eingabe.step = '0.01';
    eingabe.value = menge(position.menge_offen);
    eingabe.dataset.position = position.id;
    eingabe.setAttribute('aria-label', t('wareneingaenge.quantity_label', { position: position.id }));
    const eingabeZelle = node('td');
    eingabeZelle.append(eingabe);
    zeile.append(eingabeZelle);
    return zeile;
  }

  function tabelle(lieferung) {
    const kopf = document.createElement('tr');
    for (const key of ['table_article', 'table_variant', 'table_expected', 'table_arrived', 'table_open', 'table_now']) {
      kopf.append(node('th', t('wareneingaenge.' + key)));
    }
    const thead = document.createElement('thead');
    thead.append(kopf);
    const tbody = document.createElement('tbody');
    for (const position of lieferung.positionen) tbody.append(positionsZeile(position));
    const tabelleEl = document.createElement('table');
    tabelleEl.append(thead, tbody);
    const huelle = node('div', null, 'tablewrap');
    huelle.append(tabelleEl);
    return huelle;
  }

  function abschnitt(lieferung) {
    const panel = node('section', null, 'panel');
    const typ = t('document_types.' + lieferung.dokument.typ);
    panel.append(node('h2', t('wareneingaenge.document_line', { typ: typ, nummer: lieferung.dokument.nummer })));
    const zeile = [
      lieferung.dokument.lieferant ? t('wareneingaenge.supplier_prefix') + lieferung.dokument.lieferant : null,
      lieferung.lagerort.code + ' · ' + lieferung.lagerort.name,
      datum(lieferung.dokument.datum)
    ].filter(Boolean).join(' · ');
    panel.append(node('p', zeile, 'muted'));
    panel.append(tabelle(lieferung));

    const steuerung = node('div', null, 'filters lagerort-choice');
    let datumsfeld = null;
    if (lieferung.lagerort.verkauf) {
      const label = node('label', t('wareneingaenge.arrival_date'));
      datumsfeld = document.createElement('input');
      datumsfeld.type = 'date';
      datumsfeld.value = new Date().toISOString().slice(0, 10);
      label.append(datumsfeld);
      steuerung.append(label);
      steuerung.append(node('p', t('wareneingaenge.arrival_date_hint'), 'muted'));
    } else {
      steuerung.append(node('p', t('wareneingaenge.no_date_for_warehouse'), 'muted'));
    }
    const knopf = node('button', t('wareneingaenge.confirm'));
    knopf.type = 'button';
    const rueckmeldung = node('p', '', 'muted');
    rueckmeldung.setAttribute('role', 'status');
    knopf.addEventListener('click', () => bestaetigen(lieferung, panel, datumsfeld, knopf, rueckmeldung));
    steuerung.append(knopf);
    panel.append(steuerung, rueckmeldung);
    return panel;
  }

  async function bestaetigen(lieferung, panel, datumsfeld, knopf, rueckmeldung) {
    const mengen = {};
    for (const eingabe of panel.querySelectorAll('input[data-position]')) {
      if (eingabe.value !== '' && Number(eingabe.value) !== 0) mengen[eingabe.dataset.position] = eingabe.value;
    }
    knopf.disabled = true;
    rueckmeldung.textContent = t('wareneingaenge.saving');
    try {
      const antwort = await fetch('/api/wareneingaenge/' + lieferung.id + '/ankunft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mengen: mengen, eingangsdatum: datumsfeld ? datumsfeld.value : null })
      });
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('wareneingaenge.load_error'));
      const meldung = ergebnis.status === 'eingetroffen'
        ? t('wareneingaenge.confirmed_complete')
        : t('wareneingaenge.confirmed_partial', { offen: ergebnis.offene_positionen });
      // Erst neu laden, dann melden: das Neuladen ersetzt diesen Abschnitt
      // samt seiner Rückmeldungszeile, die Meldung gehört also in die
      // Seitenzeile, die stehen bleibt.
      await laden();
      $('status').textContent = meldung;
    } catch (fehler) {
      rueckmeldung.textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
    } finally {
      knopf.disabled = false;
    }
  }

  async function laden() {
    $('retry').hidden = true;
    $('status').textContent = t('wareneingaenge.loading');
    try {
      const antwort = await fetch('/api/wareneingaenge');
      const daten = await antwort.json();
      if (!antwort.ok) throw new Error(typeof daten.detail === 'string' ? daten.detail : t('wareneingaenge.load_error'));
      aktiverLagerort = daten.lagerort;
      const liste = document.createDocumentFragment();
      for (const lieferung of daten.wareneingaenge) liste.append(abschnitt(lieferung));
      $('list').replaceChildren(liste);
      $('empty').hidden = daten.wareneingaenge.length > 0;
      $('empty').textContent = aktiverLagerort
        ? t('wareneingaenge.empty_for_lagerort', { lagerort: aktiverLagerort.code + ' · ' + aktiverLagerort.name })
        : t('wareneingaenge.empty');
      $('status').textContent = '';
    } catch (fehler) {
      $('status').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('retry').hidden = false;
    }
  }

  $('retry').addEventListener('click', laden);
  // Erst anzeigen, wenn der Übersetzungs-Katalog da ist (sonst stünden die
  // Spaltenköpfe als Keys da), danach bei jedem Sprachwechsel neu zeichnen.
  // `ready` löst nach dem ersten i18n-ready aus, deshalb wird der Listener
  // erst danach angemeldet - sonst würde die Liste doppelt geladen.
  window.SportfabrikI18n.ready.then(() => {
    laden();
    document.addEventListener('sportfabrik:i18n-ready', laden);
  });
})();
