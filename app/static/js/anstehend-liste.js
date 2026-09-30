// Liste „Anstehend" (Pending): ein Punkt je offenem Vorgang der aktiven Filiale,
// dazu die Stammdaten-Hinweise. Gemeinsam für die Übersicht und /anstehend.
// Texte über window.SportfabrikI18n.t() (Regel 7).
(function () {
  const t = (...a) => window.SportfabrikI18n.t(...a);

  function zahl(wert) {
    const n = Number(wert);
    const sprache = { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' }[window.SportfabrikI18n.lang] || 'de-CH';
    return Number.isFinite(n) ? new Intl.NumberFormat(sprache).format(n) : '—';
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

  window.SportfabrikAnstehend = { zeichnen };
})();
