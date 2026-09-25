// Übersicht (neu gestaltet 24.09.2026): Begrüssung, Schnellzugriffe,
// Kennzahlen der aktiven Filiale, Anstehendes und Aktuelles.
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let daten = null;
  let name = null;

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
      const menge = Number(e.menge);
      const artikel = [e.marke, e.bezeichnung].filter(Boolean).join(' ');
      const variante = [e.farbe, e.groesse].filter(Boolean).join(' / ');
      const text = node('span', null, 'news-text');
      text.append(node('strong', t('dashboard.movement.' + e.typ)), ' ' + artikel + (variante ? ' (' + variante + ')' : ''));
      li.append(text);
      li.append(node('span', (menge > 0 ? '+' : '') + zahl(menge), menge < 0 ? 'news-qty is-out' : 'news-qty'));
      li.append(node('span', e.person || '—', 'news-person muted'));
      liste.append(li);
    }
    $('nichtsNeues').hidden = liste.children.length > 0;
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
  });
  $('retry').addEventListener('click', laden);
  window.SportfabrikI18n.ready.then(() => {
    laden();
    document.addEventListener('sportfabrik:i18n-ready', zeichnen);
  });
})();
