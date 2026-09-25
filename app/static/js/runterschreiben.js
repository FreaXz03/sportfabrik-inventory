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
    if (artikel.stand === 'faellig') {
      const bestaetigenKnopf = node('button', t('reduktion.confirm'), 'secondary');
      bestaetigenKnopf.type = 'button';
      bestaetigenKnopf.addEventListener('click', async () => {
        bestaetigenKnopf.disabled = true;
        try {
          const antwort = await fetch('/api/reduktionen/bestaetigen', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ artikel_id: artikel.artikel_id, lagerort_id: daten.lagerort.id, stufe: artikel.stufe }),
          });
          if (!antwort.ok) throw new Error(t('reduktion.confirm_error'));
          $('status').textContent = t('reduktion.confirmed', { artikel: [artikel.marke, artikel.bezeichnung].filter(Boolean).join(' ') });
          await laden();
        } catch (fehler) {
          bestaetigenKnopf.disabled = false;
          $('status').textContent = fehler.message;
        }
      });
      aktion.append(bestaetigenKnopf);
    }
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

  // D-F3 (25.09.2026): offene Empfehlungen der Zentrale, mit Übernehmen/Ablehnen.
  function empfehlungZeile(e) {
    const tr = document.createElement('tr');
    const name = node('td');
    name.append(node('strong', [e.marke, e.bezeichnung].filter(Boolean).join(' ') || '—'));
    tr.append(name, node('td', '−' + e.prozent + ' %'), node('td', datum(e.ab_datum)));
    const aktion = node('td');
    const uebernehmen = node('button', t('empfehlung.accept'));
    uebernehmen.type = 'button';
    const ablehnen = node('button', t('empfehlung.reject'), 'secondary');
    ablehnen.type = 'button';
    async function antworten(status, grund) {
      uebernehmen.disabled = true;
      ablehnen.disabled = true;
      try {
        const antwort = await fetch('/api/empfehlungen/' + e.id + '/antwort', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status, grund }),
        });
        if (!antwort.ok) {
          const daten = await antwort.json().catch(() => ({}));
          throw new Error(typeof daten.detail === 'string' ? daten.detail : t('empfehlung.error'));
        }
        await laden();
      } catch (fehler) {
        uebernehmen.disabled = false;
        ablehnen.disabled = false;
        $('status').textContent = fehler.message;
      }
    }
    uebernehmen.addEventListener('click', () => antworten('uebernommen'));
    ablehnen.addEventListener('click', () => {
      const grund = window.prompt(t('empfehlung.reject_prompt'));
      if (grund === null) return;
      antworten('abgelehnt', grund);
    });
    aktion.append(uebernehmen, ablehnen);
    tr.append(aktion);
    return tr;
  }

  function empfehlungZeichnen() {
    const liste = (daten.empfehlungen || []);
    $('empfehlungPanel').hidden = liste.length === 0;
    if (!liste.length) return;
    $('empfehlungListe').replaceChildren(
      tabelle(['bestand.table_article', 'empfehlung.table_prozent', 'empfehlung.table_ab', 'empfehlung.table_actions'], liste.map(empfehlungZeile))
    );
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
      manuellZeichnen();
      empfehlungZeichnen();
    } catch (fehler) {
      $('gruppen').replaceChildren();
      $('status').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('retry').hidden = false;
    }
  }


  // Von Hand reduzieren (24.09.2026): Auswahl per EAN-Scan oder aus der
  // Bestandsliste dieser Filiale; je Modell eine Zeile, weil die Stufe für
  // alle Farben und Grössen gilt.
  function tabelle(kopfKeys, zeilen) {
    const kopf = document.createElement('tr');
    for (const key of kopfKeys) kopf.append(node('th', t(key)));
    const thead = document.createElement('thead');
    thead.append(kopf);
    const tbody = document.createElement('tbody');
    for (const tr of zeilen) tbody.append(tr);
    const tab = document.createElement('table');
    tab.append(thead, tbody);
    return tab;
  }

  function artikelZelle(marke, bezeichnung, nummer) {
    const zelle = node('td');
    zelle.append(node('strong', [marke, bezeichnung].filter(Boolean).join(' ') || '—'));
    if (nummer) zelle.append(document.createElement('br'), node('span', nummer, 'muted'));
    return zelle;
  }

  async function suchen() {
    if (!daten) return;
    const q = $('sucheFeld').value.trim();
    $('sucheStatus').textContent = t('bestand.loading');
    try {
      const parameter = new URLSearchParams({ lagerort_id: String(daten.lagerort.id), limit: '500' });
      if (q) parameter.set('q', q);
      const antwort = await fetch('/api/bestand?' + parameter);
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('bestand.load_error'));
      const modelle = new Map();
      for (const z of ergebnis.zeilen) {
        const m = modelle.get(z.artikel_id) || { ...z, stueck: 0 };
        m.stueck += Number(z.menge);
        modelle.set(z.artikel_id, m);
      }
      const zeilen = [];
      for (const m of modelle.values()) {
        const tr = document.createElement('tr');
        const stand = node('td', window.SportfabrikReduktion.text(m.reduktion));
        const wahl = node('td');
        if (m.reduktion) {
          wahl.append(window.SportfabrikReduktion.knoepfe(m.varianten_id, daten.lagerort.id, m.reduktion, (neu) => {
            $('sucheStatus').textContent = t('reduktion_wahl.saved', { filiale: daten.lagerort.code, stufe: window.SportfabrikReduktion.text(neu) });
            laden().then(suchen);
          }, $('sucheStatus')));
        }
        tr.append(artikelZelle(m.marke, m.bezeichnung, m.lieferanten_artikelnr), node('td', stueck(m.stueck)), stand, wahl);
        zeilen.push(tr);
      }
      $('sucheListe').replaceChildren(zeilen.length ? tabelle(['reduktion.table_article', 'reduktion.table_pieces', 'reduktion_wahl.col_effective', 'reduktion_wahl.col_choice'], zeilen) : '');
      $('sucheStatus').textContent = zeilen.length ? t('reduktion.count_line', { anzahl: zeilen.length }) : t('reduktion_wahl.pick_none');
    } catch (fehler) {
      $('sucheStatus').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
    }
  }

  function manuellZeichnen() {
    const zeilen = (daten.manuell || []).map((a) => {
      const tr = document.createElement('tr');
      tr.append(artikelZelle(a.marke, a.bezeichnung, a.lieferanten_artikelnr), node('td', '−' + a.prozent + ' %'), node('td', [a.gesetzt_von, datum((a.gesetzt_am || '').slice(0, 10))].filter(Boolean).join(' · ')));
      return tr;
    });
    $('manuellLeer').hidden = zeilen.length > 0;
    $('manuellListe').replaceChildren(zeilen.length ? tabelle(['reduktion.table_article', 'reduktion_wahl.col_effective', 'reduktion_wahl.col_set_by'], zeilen) : '');
  }

  $('suche').addEventListener('submit', (event) => {
    event.preventDefault();
    suchen();
    $('sucheFeld').select();
  });

  $('lagerort').addEventListener('change', () => {
    wahl = $('lagerort').value;
    $('sucheListe').replaceChildren();
    $('sucheStatus').textContent = '';
    laden();
  });
  $('retry').addEventListener('click', laden);
  window.SportfabrikI18n.ready.then(() => {
    laden();
    document.addEventListener('sportfabrik:i18n-ready', () => { if (daten) { zeichnen(); manuellZeichnen(); empfehlungZeichnen(); } });
  });
})();
