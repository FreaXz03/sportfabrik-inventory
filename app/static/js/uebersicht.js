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

  function begruessen() {
    const stunde = new Date().getHours();
    const tageszeit = stunde < 11 ? 'morning' : stunde < 18 ? 'day' : 'evening';
    $('begruessung').textContent = name
      ? t('dashboard.greeting_' + tageszeit, { name: name })
      : t('dashboard.greeting_plain');
    const heute = new Intl.DateTimeFormat(sprache(), { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date());
    $('heuteText').textContent = daten && daten.lagerort
      ? daten.lagerort.code + ' · ' + daten.lagerort.name + ' · ' + heute
      : heute;
  }

  // Ein Punkt „Anstehend": Zahl, Text, Ziel. Nur was etwas zu tun gibt.
  function punkt(anzahl, text, href, dringend) {
    const li = node('li', null, dringend ? 'todo is-urgent' : 'todo');
    const a = node('a');
    a.href = href;
    a.append(node('span', zahl(anzahl), 'todo-count'), node('span', text, 'todo-text'));
    li.append(a);
    return li;
  }

  function anstehend() {
    const liste = $('anstehend');
    liste.replaceChildren();
    const f = daten.filiale;
    if (f) {
      if (f.erwartet_total) liste.append(punkt(f.erwartet_total, t('dashboard.todo_expected'), '/wareneingaenge', false));
      // Jeder Punkt führt zur Liste mit genau den gezählten Einträgen (24.09.2026).
      if (f.negativ) liste.append(punkt(f.negativ, t('dashboard.todo_negative'), '/bestand?nur_negativ=true', true));
      const r = f.reduktionen || {};
      for (const stufe of ['70', '50']) {
        const eintrag = r[stufe] || {};
        const ziel = '/bestand?reduktion=' + stufe + '&reduktion_status=';
        if (eintrag.faellig) liste.append(punkt(eintrag.faellig, t('dashboard.todo_reduction_due', { stufe: stufe }), ziel + 'faellig', true));
        if (eintrag.bald) liste.append(punkt(eintrag.bald, t('dashboard.todo_reduction_soon', { stufe: stufe }), ziel + 'bald', false));
      }
    }
    const s = daten.stamm || {};
    if (s.ohne_kategorie) liste.append(punkt(s.ohne_kategorie, t('dashboard.todo_no_category'), '/articles?kategorie_fehlt=true', false));
    if (s.ohne_ean) liste.append(punkt(s.ohne_ean, t('dashboard.todo_no_ean'), '/articles?ohne_ean=true', false));
    $('nichtsAnstehend').hidden = liste.children.length > 0;
  }

  function aktuelles() {
    const liste = $('aktuelles');
    liste.replaceChildren();
    for (const e of daten.aktuelles || []) {
      const li = node('li', null, 'news');
      const zeit = new Date(e.zeitpunkt);
      li.append(node('time', zeit.toLocaleDateString(sprache(), { day: '2-digit', month: '2-digit' }) + ' ' +
        zeit.toLocaleTimeString(sprache(), { hour: '2-digit', minute: '2-digit' }), 'news-time'));
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
      a.append(node('strong', t(eintrag.label)), node('span', t(eintrag.info)));
      nav.append(a);
    }
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
    const griff = node('span', '⠿', 'shortcut-pick-handle');
    griff.setAttribute('aria-hidden', 'true');
    const label = node('span', eintrag ? t(eintrag.label) : schluessel, 'shortcut-pick-label');
    const reihenfolge = node('span', null, 'shortcut-pick-order');
    const hoch = node('button', '▲');
    hoch.type = 'button';
    hoch.disabled = index === 0;
    hoch.setAttribute('aria-label', t('dashboard.shortcuts_move_up_aria', { name: label.textContent }));
    hoch.addEventListener('click', () => { schnellzugriffAuswahl.splice(index - 1, 0, schnellzugriffAuswahl.splice(index, 1)[0]); editorZeichnen(); });
    const runter = node('button', '▼');
    runter.type = 'button';
    runter.disabled = index === anzahl - 1;
    runter.setAttribute('aria-label', t('dashboard.shortcuts_move_down_aria', { name: label.textContent }));
    runter.addEventListener('click', () => { schnellzugriffAuswahl.splice(index + 1, 0, schnellzugriffAuswahl.splice(index, 1)[0]); editorZeichnen(); });
    reihenfolge.append(hoch, runter);
    const entfernen = node('button', '✕', 'secondary');
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
    }
    $('products').textContent = zahl(daten.products);
    $('invoices').textContent = zahl(daten.invoices);
    schnellzugriffeZeichnen();
    anstehend();
    aktuelles();
    belege();
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
