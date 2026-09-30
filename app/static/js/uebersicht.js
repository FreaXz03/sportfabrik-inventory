// Übersicht (neu gestaltet 24.09.2026): Begrüssung, Schnellzugriffe,
// Kennzahlen der aktiven Filiale, Anstehendes und Aktuelles.
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
    const n = Number(wert);
    return Number.isFinite(n) ? new Intl.NumberFormat(sprache()).format(n) : '—';
  }

  function datum(wert) {
    return wert ? wert.slice(0, 10).split('-').reverse().join('.') : '—';
  }

  // Kurzes Datum ohne Jahr in der Sprache der Oberfläche (Diagrammachsen).
  function datumKurz(wert) {
    return new Intl.DateTimeFormat(sprache(), { day: '2-digit', month: '2-digit' }).format(new Date(wert + 'T12:00:00'));
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

  // Redesign 29.09.2026 (DESIGN.md 9.3): kleine Diagramme - Verkaufsverlauf,
  // Stufenverteilung, Bestseller. Farbe nie allein: jede Zahl steht auch als Text.
  function summe(werte) {
    return werte.reduce((a, b) => a + b, 0);
  }

  function verlauf(f) {
    const tage = f.verlauf || [];
    const werte = tage.map((tag) => Number(tag.verkauft));
    const woche = summe(werte.slice(-7));
    const davor = summe(werte.slice(-14, -7));
    $('trendWoche').textContent = t('dashboard.trend_week', { anzahl: zahl(woche) });
    const unterschied = woche - davor;
    $('trendDelta').textContent = unterschied === 0
      ? t('dashboard.trend_same')
      : t(unterschied > 0 ? 'dashboard.trend_up' : 'dashboard.trend_down', { anzahl: zahl(Math.abs(unterschied)) });
    const hoechster = Math.max(1, ...werte);
    const balken = $('trendBalken');
    balken.replaceChildren();
    tage.forEach((tag, index) => {
      const eintrag = node('span', null, index === tage.length - 1 ? 'bar is-today' : 'bar');
      eintrag.style.setProperty('--h', String(werte[index] / hoechster));
      eintrag.title = t('dashboard.trend_bar', { datum: datumKurz(tag.tag), anzahl: zahl(werte[index]) });
      balken.append(eintrag);
    });
  }

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

  // Bestand der letzten 30 Tage als Linie (ohne Achsen; Anfang, Ende und Änderung stehen als Text daneben).
  function bestandsverlauf(f) {
    const tage = f.bestandsverlauf || [];
    if (!tage.length) return;
    const werte = tage.map((tag) => Number(tag.bestand));
    const jetzt = werte[werte.length - 1];
    const unterschied = jetzt - werte[0];
    $('stockNow').textContent = t('dashboard.stock_now', { anzahl: zahl(jetzt) });
    $('stockDelta').textContent = unterschied === 0
      ? t('dashboard.stock_same')
      : t(unterschied > 0 ? 'dashboard.stock_up' : 'dashboard.stock_down', { anzahl: zahl(Math.abs(unterschied)) });
    $('stockVon').textContent = datumKurz(tage[0].tag);
    const tiefster = Math.min(...werte);
    const spanne = Math.max(...werte) - tiefster;
    const punkte = werte.map((wert, index) => {
      const x = tage.length > 1 ? index / (tage.length - 1) * 300 : 0;
      const y = spanne === 0 ? 40 : 74 - (wert - tiefster) / spanne * 68;
      return x.toFixed(1) + ',' + y.toFixed(1);
    });
    $('stockLinie').setAttribute('points', punkte.join(' '));
    $('stockFlaeche').setAttribute('d', 'M' + punkte.join(' L') + ' L300,80 L0,80 Z');
  }

  // Bestand nach Hauptgruppe der Kassenkategorie als Ring; jede Zahl steht auch in der Liste.
  function kategorien(f) {
    const eintraege = (f.kategorien || []).map((e) => ({ name: e.hauptgruppe, menge: Number(e.stueck) }));
    const gesamt = summe(eintraege.map((e) => e.menge));
    const ring = $('catsDonut');
    const liste = $('catsListe');
    ring.replaceChildren();
    liste.replaceChildren();
    ring.hidden = liste.hidden = gesamt === 0;
    $('catsLeer').hidden = gesamt !== 0;
    if (gesamt === 0) return;
    const svgNs = 'http://www.w3.org/2000/svg';
    let start = 0;
    eintraege.forEach((e, index) => {
      const anteil = e.menge / gesamt * 100;
      const farbe = e.name === null ? 'none' : String(index % 5 + 1);
      const bogen = document.createElementNS(svgNs, 'circle');
      bogen.setAttribute('class', 'donut-seg');
      bogen.setAttribute('cx', '21');
      bogen.setAttribute('cy', '21');
      bogen.setAttribute('r', '15.9155');
      bogen.setAttribute('pathLength', '100');
      bogen.setAttribute('stroke-dasharray', anteil.toFixed(3) + ' ' + (100 - anteil).toFixed(3));
      bogen.setAttribute('stroke-dashoffset', (25 - start).toFixed(3));
      bogen.dataset.cat = farbe;
      ring.append(bogen);
      start += anteil;
      const li = node('li', null, 'cat-row');
      const punkt = node('span', null, 'cat-dot');
      punkt.dataset.cat = farbe;
      punkt.setAttribute('aria-hidden', 'true');
      li.append(punkt, node('span', e.name === null ? t('dashboard.cats_none') : e.name, 'cat-name'),
        node('span', t('dashboard.stages_pieces', { anzahl: zahl(e.menge) }), 'stage-qty'),
        node('span', Math.round(e.menge / gesamt * 100) + ' %', 'stage-share muted'));
      liste.append(li);
    });
    const mitte = document.createElementNS(svgNs, 'text');
    mitte.setAttribute('class', 'donut-total');
    mitte.setAttribute('x', '21');
    mitte.setAttribute('y', '23.2');
    mitte.setAttribute('text-anchor', 'middle');
    mitte.textContent = zahl(gesamt);
    ring.append(mitte);
  }

  function bestseller(f) {
    const liste = $('bestsellerListe');
    liste.replaceChildren();
    const eintraege = f.bestseller || [];
    const hoechster = Math.max(1, ...eintraege.map((e) => Number(e.stueck)));
    for (const e of eintraege) {
      const li = node('li', null, 'rank');
      li.append(node('span', [e.marke, e.bezeichnung].filter(Boolean).join(' '), 'rank-name'),
        node('strong', zahl(e.stueck), 'rank-qty'));
      const spur = node('span', null, 'rank-bar');
      spur.style.setProperty('--w', String(Number(e.stueck) / hoechster));
      li.append(spur);
      liste.append(li);
    }
    $('bestsellerLeer').hidden = eintraege.length > 0;
  }

  // Tageskopf für „Aktuelles": Heute / Gestern / Datum.
  function tagesname(zeit) {
    const heute = new Date();
    const gestern = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate() - 1);
    if (zeit.toDateString() === heute.toDateString()) return t('dashboard.day_today');
    if (zeit.toDateString() === gestern.toDateString()) return t('dashboard.day_yesterday');
    return zeit.toLocaleDateString(sprache(), { weekday: 'long', day: 'numeric', month: 'long' });
  }

  function aktuelles() {
    const liste = $('aktuelles');
    liste.replaceChildren();
    let letzterTag = null;
    for (const e of daten.aktuelles || []) {
      const zeit = new Date(e.zeitpunkt);
      if (zeit.toDateString() !== letzterTag) {
        letzterTag = zeit.toDateString();
        liste.append(node('li', tagesname(zeit), 'news-day'));
      }
      const li = node('li', null, 'news');
      li.append(node('time', zeit.toLocaleTimeString(sprache(), { hour: '2-digit', minute: '2-digit' }), 'news-time'));
      const text = node('span', null, 'news-text');
      let menge;
      if (e.art === 'abgang') {
        const artikel = [e.marke, e.bezeichnung].filter(Boolean).join(' ');
        const variante = [e.farbe, e.groesse].filter(Boolean).join(' / ');
        const grund = e.grund ? t('ausbuchen.reason.' + e.grund) : '';
        text.append(node('strong', t('dashboard.news.abgang')), ' ' + artikel + (variante ? ' (' + variante + ')' : '') + (grund ? ' – ' + grund : ''));
        menge = node('span', zahl(e.menge), 'news-qty is-out');
      } else if (e.art === 'umlagerung') {
        text.append(node('strong', t('dashboard.news.umlagerung')), ' ' + t('dashboard.news.von_nach', { von: e.von, nach: e.nach }) +
          ' · ' + t('dashboard.news.artikel', { anzahl: e.positionen }));
        menge = node('span', zahl(e.stueck) + ' ' + t('dashboard.news.stueck'), 'news-qty');
      } else {
        const beleg = [e.lieferant, e.dokumentnummer].filter(Boolean).join(' ');
        text.append(node('strong', t('dashboard.news.lieferung')), ' ' + (beleg || t('dashboard.news.von_hand')) +
          ' → ' + e.lagerort + ' · ' + t('dashboard.news.artikel', { anzahl: e.positionen }));
        menge = node('span', '+' + zahl(e.stueck) + ' ' + t('dashboard.news.stueck'), 'news-qty');
      }
      li.append(text);
      li.append(menge);
      li.append(node('span', e.person || '—', 'news-person muted'));
      liste.append(li);
    }
    $('nichtsNeues').hidden = liste.children.length > 0;
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
      for (const wert of [datum(i.invoice_date), i.supplier, datum(i.uploaded_at), von]) tr.append(node('td', wert ?? '—'));
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
      $('stueck').textContent = zahl(f.stueck);
      $('variantenText').textContent = t('dashboard.metric_stock_variants', { anzahl: zahl(f.varianten) });
      $('verkauftHeute').textContent = zahl(f.verkauft_heute);
      $('abgaengeText').textContent = t('dashboard.metric_removed_today', { anzahl: zahl(f.abgaenge_heute) });
      verlauf(f);
      stufen(f);
      bestseller(f);
      bestandsverlauf(f);
      kategorien(f);
    }
    $('products').textContent = zahl(daten.products);
    $('invoices').textContent = zahl(daten.invoices);
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
  $('schnellzugriffeBearbeiten').addEventListener('click', editorOeffnen);
  $('schnellzugriffeAbbrechen').addEventListener('click', () => { $('schnellzugriffeEditor').hidden = true; });
  $('schnellzugriffeSpeichern').addEventListener('click', editorSpeichern);
  window.SportfabrikI18n.ready.then(() => {
    laden();
    document.addEventListener('sportfabrik:i18n-ready', zeichnen);
  });
})();
