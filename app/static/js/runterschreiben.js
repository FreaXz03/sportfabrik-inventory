// Runterschreiben (Phase D, Teil 1): fällige und bald fällige Reduktionen je
// Artikel, mit Etikettendruck für alle Stück. Texte über i18n (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let wahl = null; // null = aktive Filiale (entscheidet der Server)
  let daten = null;

  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function stueck(wert) {
    const zahl = Number(wert);
    return Number.isFinite(zahl) ? String(zahl) : String(wert ?? '—');
  }

  function datum(wert) {
    return wert ? wert.split('-').reverse().join('.') : '—';
  }

  function zeile(artikel) {
    const tr = document.createElement('tr');
    const name = node('td');
    name.append(node('strong', [artikel.marke, artikel.bezeichnung].filter(Boolean).join(' ') || '—'));
    if (artikel.lieferanten_artikelnr) name.append(document.createElement('br'), node('span', artikel.lieferanten_artikelnr, 'muted'));
    tr.append(name, node('td', String(artikel.varianten)), node('td', stueck(artikel.stueck)), node('td', datum(artikel.eingang)));
    const aktion = node('td');
    const knopf = node('button', t('reduktion.print', { anzahl: stueck(artikel.stueck) }));
    knopf.type = 'button';
    knopf.addEventListener('click', () => {
      const parameter = new URLSearchParams({ reduktion: String(artikel.stufe), lagerort_id: String(daten.lagerort.id) });
      window.open('/api/artikel/' + artikel.artikel_id + '/etiketten.pdf?' + parameter.toString(), '_blank', 'noopener');
    });
    aktion.append(knopf);
    tr.append(aktion);
    return tr;
  }

  function gruppe(stufe, stand, eintraege) {
    const section = node('section', null, 'panel');
    section.append(node('h2', t('reduktion.group_' + stand, { stufe: stufe })));
    // Welche Rolle in den Drucker gehört - gross, mit dem Farbpunkt der Rolle.
    const rolle = eintraege[0].rolle;
    const hinweis = node('p', t('etikett.roll_hint', { prozent: rolle.prozent, farbe: t('etikett.roll_color.' + rolle.farbe) }), 'roll-hint');
    hinweis.dataset.farbe = rolle.farbe;
    section.append(hinweis);
    const kopf = document.createElement('tr');
    for (const key of ['table_article', 'table_variants', 'table_pieces', 'table_arrival', 'table_actions']) kopf.append(node('th', t('reduktion.' + key)));
    const thead = document.createElement('thead');
    thead.append(kopf);
    const tbody = document.createElement('tbody');
    for (const artikel of eintraege) tbody.append(zeile(artikel));
    const tabelle = document.createElement('table');
    tabelle.append(thead, tbody);
    const huelle = node('div', null, 'tablewrap');
    huelle.append(tabelle);
    section.append(huelle);
    return section;
  }

  function zeichnen() {
    const ziel = $('gruppen');
    ziel.replaceChildren();
    $('titelFiliale').textContent = '· ' + daten.lagerort.code + ' · ' + daten.lagerort.name;
    for (const stand of ['faellig', 'bald']) {
      for (const stufe of [70, 50]) {
        const eintraege = daten.artikel.filter((a) => a.stand === stand && a.stufe === stufe);
        if (eintraege.length) ziel.append(gruppe(stufe, stand, eintraege));
      }
    }
    $('empty').hidden = daten.artikel.length > 0;
    $('status').textContent = daten.artikel.length ? t('reduktion.count_line', { anzahl: daten.artikel.length }) : '';
  }

  function filialenFuellen() {
    const auswahl = $('lagerort');
    if (auswahl.options.length) return;
    for (const lagerort of daten.lagerorte) auswahl.add(new Option(lagerort.code + ' · ' + lagerort.name, String(lagerort.id)));
    auswahl.value = String(daten.lagerort.id);
  }

  async function laden() {
    $('retry').hidden = true;
    $('status').textContent = t('reduktion.loading');
    try {
      const antwort = await fetch('/api/reduktionen' + (wahl ? '?lagerort_id=' + wahl : ''));
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('reduktion.load_error'));
      daten = ergebnis;
      filialenFuellen();
      zeichnen();
    } catch (fehler) {
      $('gruppen').replaceChildren();
      $('status').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('retry').hidden = false;
    }
  }

  $('lagerort').addEventListener('change', () => {
    wahl = $('lagerort').value;
    laden();
  });
  $('retry').addEventListener('click', laden);
  window.SportfabrikI18n.ready.then(() => {
    laden();
    document.addEventListener('sportfabrik:i18n-ready', () => { if (daten) zeichnen(); });
  });
})();
