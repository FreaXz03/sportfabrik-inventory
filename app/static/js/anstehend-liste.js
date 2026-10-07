// Listen „Anstehend" (Pending) und „Aktuelles" (letzte Buchungen): ein Punkt je offenem Vorgang der aktiven Filiale,
// dazu die Stammdaten-Hinweise. Gemeinsam für die Übersicht und /anstehend.
// Texte über window.SportfabrikI18n.t() (Regel 7).
(function () {
  const t = (...a) => window.SportfabrikI18n.t(...a);

  function sprache() {
    return { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' }[window.SportfabrikI18n.lang] || 'de-CH';
  }

  function zahl(wert) {
    const n = Number(wert);
    return Number.isFinite(n) ? new Intl.NumberFormat(sprache()).format(n) : '—';
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

  // daten = Antwort von /api/dashboard; daten.meldungen kommt fertig vom Server
  // (Reihenfolge, Ziel und Dringlichkeit je Punkt, wie bei der Glocke).
  function zeichnen(daten, liste, leer) {
    liste.replaceChildren();
    for (const m of daten.meldungen || []) {
      liste.append(punkt(m.anzahl, t('dashboard.todo_' + m.art, { stufe: m.stufe }), m.href, m.dringend));
    }
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
