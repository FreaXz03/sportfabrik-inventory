// Listen „Anstehend" (Pending) und „Aktuelles" (letzte Buchungen): ein Punkt je offenem Vorgang der aktiven Filiale,
// dazu die Stammdaten-Hinweise. Gemeinsam für die Übersicht und /anstehend.
// Texte über window.SportfabrikI18n.t() (Regel 7).
(function () {
  const t = (...a) => window.SportfabrikI18n.t(...a);

  function zahl(wert) {
    const n = Number(wert);
    const sprache = { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' }[window.SportfabrikI18n.lang] || 'de-CH';
    return Number.isFinite(n) ? new Intl.NumberFormat(sprache).format(n) : '—';
  }

  function sprache() {
    return { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' }[window.SportfabrikI18n.lang] || 'de-CH';
  }

  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  // Ein Punkt: Zahl, Text, Ziel. Nur was etwas zu tun gibt.
  function punkt(anzahl, text, href, dringend) {
    const li = document.createElement('li');
    li.className = dringend ? 'todo is-urgent' : 'todo';
    const a = document.createElement('a');
    a.href = href;
    const count = document.createElement('span');
    count.className = 'todo-count';
    count.textContent = zahl(anzahl);
    const label = document.createElement('span');
    label.className = 'todo-text';
    label.textContent = text;
    a.append(count, label);
    li.append(a);
    return li;
  }

  // daten = Antwort von /api/dashboard.
  function zeichnen(daten, liste, leer) {
    liste.replaceChildren();
    const f = daten.filiale;
    if (f) {
      if (f.erwartet_total) liste.append(punkt(f.erwartet_total, t('dashboard.todo_expected'), '/wareneingaenge', false));
      // Offene Empfehlungen der Zentrale (30.09.2026): führt zur Runterschreiben-Seite mit ihrem Abschnitt.
      if (f.empfehlungen_offen) liste.append(punkt(f.empfehlungen_offen, t('dashboard.todo_recommendations'), '/runterschreiben#empfehlungPanel', false));
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
    // Ganzer Stamm, alle Filialen (29.09.2026): die Liste zeigt dieselbe Auswahl wie die Zahl.
    if (s.ohne_kategorie) liste.append(punkt(s.ohne_kategorie, t('dashboard.todo_no_category'), '/articles?kategorie_fehlt=true', false));
    if (s.ohne_ean) liste.append(punkt(s.ohne_ean, t('dashboard.todo_no_ean'), '/articles?ohne_ean=true', false));
    leer.hidden = liste.children.length > 0;
  }

  // Tageskopf für „Aktuelles": Heute / Gestern / Datum.
  function tagesname(zeit) {
    const heute = new Date();
    const gestern = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate() - 1);
    if (zeit.toDateString() === heute.toDateString()) return t('dashboard.day_today');
    if (zeit.toDateString() === gestern.toDateString()) return t('dashboard.day_yesterday');
    return zeit.toLocaleDateString(sprache(), { weekday: 'long', day: 'numeric', month: 'long' });
  }

  function aktuelles(daten, liste, leer) {
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
    leer.hidden = liste.children.length > 0;
  }

  window.SportfabrikAnstehend = { zeichnen, aktuelles };
})();
