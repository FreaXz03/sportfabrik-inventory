// Übersicht (neu gestaltet 24.09.2026): Begrüssung, Schnellzugriffe,
// Bestandsdiagramme der aktiven Filiale, Anstehendes und Aktuelles.
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let daten = null;
  let name = null;

  // Punkt 14 (Entscheid 24.09.2026): Katalog der wählbaren Funktionen - Ziel,
  // Beschriftung und Erklärung je Funktion. Muss zum Server-Katalog passen
  // (app/core/schnellzugriffe.py); der Server prüft die Auswahl ohnehin.
  const SCHNELLZUGRIFF_KATALOG = {
    bestand: { href: '/bestand', label: 'nav.bestand', info: 'nav.info.bestand' },
    erfassen: { href: '/erfassen', label: 'nav.erfassen', info: 'nav.info.erfassen' },
    wareneingaenge: { href: '/wareneingaenge', label: 'nav.wareneingaenge', info: 'nav.info.wareneingaenge' },
    umlagern: { href: '/umlagern', label: 'nav.umlagern', info: 'nav.info.umlagern' },
    ausbuchen: { href: '/ausbuchen', label: 'nav.ausbuchen', info: 'nav.info.ausbuchen' },
    runterschreiben: { href: '/runterschreiben', label: 'nav.runterschreiben', info: 'nav.info.runterschreiben' },
    articles: { href: '/articles', label: 'nav.articles', info: 'nav.info.articles' },
    invoices: { href: '/invoices', label: 'nav.invoices', info: 'nav.info.invoices' },
    upload: { href: '/preview', label: 'nav.upload', info: 'nav.info.upload' },
  };
  let schnellzugriffAuswahl = [];
  let schnellzugriffAktuell = [];

  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  // Icon aus /static/img/icons.svg (DESIGN.md §7) statt Unicode-Zeichen.
  function icon(name) {
    const svgNs = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNs, 'svg');
    svg.setAttribute('class', 'icon icon-16');
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS(svgNs, 'use');
    use.setAttribute('href', '/static/img/icons.svg#icon-' + name);
    svg.append(use);
    return svg;
  }

  function sprache() {
    return { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' }[window.SportfabrikI18n.lang] || 'de-CH';
  }

  function zahl(wert) {
    return window.SportfabrikDiagramme.zahl(wert);
  }

  function datum(wert) {
    return wert ? wert.slice(0, 10).split('-').reverse().join('.') : '—';
  }

  function begruessen() {
    const stunde = new Date().getHours();
    const tageszeit = stunde < 11 ? 'morning' : stunde < 18 ? 'day' : 'evening';
    const begruessung = $('begruessung');
    begruessung.className = 'title-mixed';
    if (name) {
      // Mixed-Weight-Titel (DESIGN.md §5.3): der Name traegt die Bedeutung,
      // darum fett - der Rest der Begruessung bleibt leise (300). Ohne
      // Werte abgerufen, damit der Platzhalter "{name}" literal bleibt -
      // ein Name, der zufaellig im festen Satzteil vorkommt (z. B. "Tag"
      // in "Guten Tag, {name}"), soll nicht faelschlich fett werden.
      const vorlage = t('dashboard.greeting_' + tageszeit);
      const index = vorlage.indexOf('{name}');
      begruessung.replaceChildren();
      if (index === -1) {
        begruessung.textContent = vorlage.split('{name}').join(name);
      } else {
        begruessung.append(vorlage.slice(0, index));
        const stark = document.createElement('strong');
        stark.textContent = name;
        begruessung.append(stark, vorlage.slice(index + '{name}'.length));
      }
    } else {
      begruessung.textContent = t('dashboard.greeting_plain');
    }
    const heute = new Intl.DateTimeFormat(sprache(), { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date());
    $('heuteText').textContent = daten && daten.lagerort
      ? daten.lagerort.code + ' · ' + daten.lagerort.name + ' · ' + heute
      : heute;
  }

  function anstehend() {
    window.SportfabrikAnstehend.zeichnen(daten, $('anstehend'), $('nichtsAnstehend'));
  }

  // Redesign 29.09.2026 (DESIGN.md 9.3): kleine Diagramme - Stufenverteilung,
  // Bestandsverlauf, Kategorien. Farbe nie allein: jede Zahl steht auch als Text.
  // Verkaufsdiagramme (Verlauf 14 Tage, Bestseller) sind seit 2026-10-01 auf /statistiken.
  const D = window.SportfabrikDiagramme;
  const summe = D.summe;

  function stufen(f) {
    const je = f.stufen || {};
    const gesamt = summe(['30', '50', '70'].map((stufe) => Number(je[stufe] || 0)));
    const balken = $('stufenBalken');
    const liste = $('stufenListe');
    balken.replaceChildren();
    liste.replaceChildren();
    balken.hidden = liste.hidden = gesamt === 0;
    $('stufenLeer').hidden = gesamt !== 0;
    if (gesamt === 0) return;
    for (const stufe of ['30', '50', '70']) {
      const menge = Number(je[stufe] || 0);
      const segment = node('span', null, 'stage-seg');
      segment.dataset.stage = stufe;
      segment.style.setProperty('--w', String(menge / gesamt));
      balken.append(segment);
      const li = node('li', null, 'stage-row');
      const chip = node('span', null, 'chip chip-stage');
      chip.dataset.stage = stufe;
      const punkt = node('span', null, 'chip-dot');
      punkt.setAttribute('aria-hidden', 'true');
      chip.append(punkt, '−' + stufe + ' %');
      li.append(chip, node('span', t('dashboard.stages_pieces', { anzahl: zahl(menge) }), 'stage-qty'),
        node('span', Math.round(menge / gesamt * 100) + ' %', 'stage-share muted'));
      liste.append(li);
    }
  }

  // Bestand und neu erfasste Varianten über den gewählten Zeitraum (2026-10-01),
  // mit vergleich zur Periode davor. Bestand gehört zur aktiven Filiale, die neuen
  // Varianten zum ganzen Artikelstamm.
  const VORPERIODE = { 7: 'week', 30: 'month', 180: 'half_year' };
  let periode = '30';
  let verlaufAnfrage = 0;

  async function verlaeufeLaden() {
    const nummer = ++verlaufAnfrage;
    try {
      const antwort = await fetch('/api/uebersicht/verlaeufe?tage=' + periode);
      const ergebnis = await antwort.json();
      if (!antwort.ok || nummer !== verlaufAnfrage) return;
      const vor = VORPERIODE[periode];
      const bestand = ergebnis.bestand;
      if (bestand) {
        $('stockNow').textContent = t('dashboard.stock_now', { anzahl: zahl(bestand.jetzt) });
        D.linie($('stockChart'), bestand.reihe.map((p) => ({ tag: p.tag, wert: Number(p.bestand) })), t('dashboard.stock_aria'));
        D.vergleich($('stockDelta'), bestand.prozent, vor);
      }
      const neu = ergebnis.neu;
      $('neuNow').textContent = t('dashboard.new_now', { anzahl: zahl(neu.summe) });
      D.linie($('neuChart'), neu.reihe.map((p) => ({ tag: p.tag, wert: p.anzahl })), t('dashboard.new_aria'));
      D.vergleich($('neuDelta'), neu.prozent, vor);
    } catch (fehler) {
      // Die Diagramme sind Beiwerk: bei Verbindungsproblemen bleiben sie leer, der Rest der Seite arbeitet.
    }
  }

  // Bestand nach Hauptgruppe der Kassenkategorie als Ring; jede Zahl steht auch in der Liste.
  function kategorien(f) {
    D.donut($('catsDonut'), $('catsListe'), $('catsLeer'),
      (f.kategorien || []).map((e) => ({ name: e.hauptgruppe, menge: Number(e.stueck) })));
  }

  function aktuelles() {
    window.SportfabrikAnstehend.aktuelles(daten, $('aktuelles'), $('nichtsNeues'));
  }

  // Rendert die gewählten Schnellzugriffe als Knöpfe (Punkt 14). Gleiche Höhe
  // aller Knöpfe kommt automatisch von .quick-actions (grid-auto-rows: 1fr).
  function schnellzugriffeZeichnen(liste) {
    if (liste) schnellzugriffAktuell = liste;
    const nav = $('schnellzugriffe');
    nav.replaceChildren();
    for (const schluessel of schnellzugriffAktuell) {
      const eintrag = SCHNELLZUGRIFF_KATALOG[schluessel];
      if (!eintrag) continue;
      const a = node('a', null, 'quick-action');
      a.href = eintrag.href;
      a.append(node('strong', t(eintrag.label)));
      nav.append(a);
    }
    // Immer die ganze Breite füllen, egal wie viele gewählt sind (30.09.2026).
    nav.style.setProperty('--anzahl', String(Math.max(nav.children.length, 1)));
  }

  // --- Schnellzugriffe bearbeiten (Punkt 14): Auswahl per Klick, Reihenfolge
  // per Ziehen (Maus) oder Pfeil-Knöpfen (Tastatur/Touch). Gespeichert wird
  // erst auf Knopfdruck; der Server prüft Anzahl, Duplikate und Rolle.
  let ziehIndex = null;

  function editorZeile(schluessel, index, anzahl) {
    const eintrag = SCHNELLZUGRIFF_KATALOG[schluessel];
    const li = node('li', null, 'shortcut-pick');
    li.draggable = true;
    li.dataset.schluessel = schluessel;
    const griff = node('span', null, 'shortcut-pick-handle');
    griff.append(icon('grip-vertical'));
    griff.setAttribute('aria-hidden', 'true');
    const label = node('span', eintrag ? t(eintrag.label) : schluessel, 'shortcut-pick-label');
    const reihenfolge = node('span', null, 'shortcut-pick-order');
    const hoch = node('button', null, 'ghost icon-only');
    hoch.append(icon('chevron-up'));
    hoch.type = 'button';
    hoch.disabled = index === 0;
    hoch.setAttribute('aria-label', t('dashboard.shortcuts_move_up_aria', { name: label.textContent }));
    hoch.addEventListener('click', () => { schnellzugriffAuswahl.splice(index - 1, 0, schnellzugriffAuswahl.splice(index, 1)[0]); editorZeichnen(); });
    const runter = node('button', null, 'ghost icon-only');
    runter.append(icon('chevron-down'));
    runter.type = 'button';
    runter.disabled = index === anzahl - 1;
    runter.setAttribute('aria-label', t('dashboard.shortcuts_move_down_aria', { name: label.textContent }));
    runter.addEventListener('click', () => { schnellzugriffAuswahl.splice(index + 1, 0, schnellzugriffAuswahl.splice(index, 1)[0]); editorZeichnen(); });
    reihenfolge.append(hoch, runter);
    const entfernen = node('button', null, 'secondary icon-only');
    entfernen.append(icon('x'));
    entfernen.type = 'button';
    entfernen.setAttribute('aria-label', t('dashboard.shortcuts_remove_aria', { name: label.textContent }));
    entfernen.addEventListener('click', () => { schnellzugriffAuswahl.splice(index, 1); editorZeichnen(); });
    li.append(griff, label, reihenfolge, entfernen);
    li.addEventListener('dragstart', () => { ziehIndex = index; li.classList.add('is-dragging'); });
    li.addEventListener('dragend', () => { li.classList.remove('is-dragging'); ziehIndex = null; });
    li.addEventListener('dragover', (ereignis) => ereignis.preventDefault());
    li.addEventListener('drop', (ereignis) => {
      ereignis.preventDefault();
      if (ziehIndex === null || ziehIndex === index) return;
      schnellzugriffAuswahl.splice(index, 0, schnellzugriffAuswahl.splice(ziehIndex, 1)[0]);
      editorZeichnen();
    });
    return li;
  }

  function editorZeichnen() {
    const auswahlListe = $('schnellzugriffeAuswahl');
    auswahlListe.replaceChildren();
    schnellzugriffAuswahl.forEach((schluessel, index) => auswahlListe.append(editorZeile(schluessel, index, schnellzugriffAuswahl.length)));

    const verfuegbarBox = $('schnellzugriffeVerfuegbar');
    verfuegbarBox.replaceChildren();
    const rest = (daten && daten.schnellzugriffeVerfuegbar || []).filter((k) => !schnellzugriffAuswahl.includes(k));
    for (const schluessel of rest) {
      const eintrag = SCHNELLZUGRIFF_KATALOG[schluessel];
      const knopf = node('button', t('dashboard.shortcuts_add') + ' ' + (eintrag ? t(eintrag.label) : schluessel), 'secondary');
      knopf.type = 'button';
      knopf.setAttribute('aria-label', t('dashboard.shortcuts_add_aria', { name: eintrag ? t(eintrag.label) : schluessel }));
      knopf.disabled = schnellzugriffAuswahl.length >= 5;
      knopf.addEventListener('click', () => { schnellzugriffAuswahl.push(schluessel); editorZeichnen(); });
      verfuegbarBox.append(knopf);
    }
    $('schnellzugriffeFehler').hidden = true;
  }

  async function editorOeffnen() {
    $('schnellzugriffeFehler').hidden = true;
    try {
      const antwort = await fetch('/api/schnellzugriffe');
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(t('dashboard.shortcuts_save_error'));
      schnellzugriffAuswahl = ergebnis.schnellzugriffe.slice();
      if (!daten) daten = {};
      daten.schnellzugriffeVerfuegbar = ergebnis.verfuegbar;
      editorZeichnen();
      $('schnellzugriffeEditor').hidden = false;
    } catch (fehler) {
      $('schnellzugriffeFehler').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('schnellzugriffeFehler').hidden = false;
    }
  }

  async function editorSpeichern() {
    const knopf = $('schnellzugriffeSpeichern');
    knopf.disabled = true;
    knopf.classList.add('is-loading');
    try {
      const antwort = await fetch('/api/schnellzugriffe', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schnellzugriffe: schnellzugriffAuswahl }),
      });
      const ergebnis = await antwort.json().catch(() => ({}));
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('dashboard.shortcuts_save_error'));
      schnellzugriffeZeichnen(ergebnis.schnellzugriffe);
      $('schnellzugriffeEditor').hidden = true;
    } catch (fehler) {
      $('schnellzugriffeFehler').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('schnellzugriffeFehler').hidden = false;
    } finally {
      knopf.disabled = false;
      knopf.classList.remove('is-loading');
    }
  }

  function belege() {
    const fragment = document.createDocumentFragment();
    for (const i of daten.recent_invoices) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      const a = document.createElement('a');
      a.href = '/invoices/' + i.id;
      a.textContent = i.invoice_number;
      td.append(a);
      tr.append(td);
      const von = (i.imported_by_name || i.imported_by_kassennummer || '—') + (i.ocr_used ? ' ' + t('dashboard.ocr_scan_suffix') : '');
      for (const wert of [datum(i.invoice_date), i.supplier, i.lagerort, datum(i.uploaded_at), von]) tr.append(node('td', wert ?? '—'));
      fragment.append(tr);
    }
    $('rows').replaceChildren(fragment);
    $('table').hidden = !daten.recent_invoices.length;
    $('empty').hidden = !!daten.recent_invoices.length;
  }

  function zeichnen() {
    if (!daten) return;
    begruessen();
    const f = daten.filiale;
    document.querySelectorAll('.filiale-only').forEach((el) => { el.hidden = !f; });
    $('ohneFiliale').hidden = !!f;
    if (f) {
      stufen(f);
      kategorien(f);
    }
    schnellzugriffeZeichnen();
    anstehend();
    aktuelles();
    hinweise();
    belege();
  }

  // D-F2 (25.09.2026): Nachlieferungs-Hinweis - ein Modell mit bereits
  // reduziertem Altbestand hat Nachschub bekommen (Regel 6 startet die Uhr
  // fürs ganze Modell neu, keine Chargentrennung im Bestand).
  function hinweise() {
    const liste = $('hinweise');
    liste.replaceChildren();
    for (const h of daten.hinweise || []) {
      const li = node('li', null, 'news');
      const zeit = new Date(h.erstellt_am);
      li.append(node('time', zeit.toLocaleDateString(sprache(), { day: '2-digit', month: '2-digit' }) + ' ' +
        zeit.toLocaleTimeString(sprache(), { hour: '2-digit', minute: '2-digit' }), 'news-time'));
      const artikel = [h.marke, h.bezeichnung].filter(Boolean).join(' ');
      const text = node('span', t('dashboard.hinweise.nachlieferung', { artikel: artikel, prozent: h.alte_stufe }), 'news-text');
      li.append(text);
      liste.append(li);
    }
    $('hinweisePanel').hidden = liste.children.length === 0;
  }

  async function laden() {
    $('retry').hidden = true;
    $('status').textContent = t('dashboard.loading');
    try {
      const antwort = await fetch('/api/dashboard');
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('dashboard.load_error'));
      daten = ergebnis;
      zeichnen();
      verlaeufeLaden();
      $('status').textContent = '';
    } catch (fehler) {
      $('status').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('retry').hidden = false;
    }
  }

  document.addEventListener('sportfabrik:me', (ereignis) => {
    const me = ereignis.detail || {};
    name = (me.name || '').trim().split(/\s+/)[0] || null;
    if (daten) begruessen();
    schnellzugriffeZeichnen(me.schnellzugriffe);
  });
  $('retry').addEventListener('click', laden);
  $('periode').addEventListener('change', () => { periode = $('periode').value; verlaeufeLaden(); });
  $('schnellzugriffeBearbeiten').addEventListener('click', editorOeffnen);
  $('schnellzugriffeAbbrechen').addEventListener('click', () => { $('schnellzugriffeEditor').hidden = true; });
  $('schnellzugriffeSpeichern').addEventListener('click', editorSpeichern);
  window.SportfabrikI18n.ready.then(() => {
    laden();
    document.addEventListener('sportfabrik:i18n-ready', () => { zeichnen(); verlaeufeLaden(); });
  });
})();
