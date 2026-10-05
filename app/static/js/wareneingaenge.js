// Erwartete Lieferungen und ihre Ankunftsbestätigung (Phase B, Teilaufgabe B5).
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let aktiverLagerort = null;
  // Umleiten dürfen nur Filialleiter und Zentrale (Punkt 3); Ziele = buchbare Orte.
  let umleitenZiele = null;
  // Verloren / vom Lieferanten storniert erklären dürfen nur Filialleiter und Zentrale (Q8).
  let darfVerwalten = false;

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
    // Umlagerung unterwegs (28.09.2026): kein Dokument, dafür Quelle und Versanddatum.
    const u = lieferung.umlagerung;
    const titel = u
      ? t('wareneingaenge.transfer_line', { von: u.von.code })
      : t('wareneingaenge.document_line', { typ: t('document_types.' + lieferung.dokument.typ), nummer: lieferung.dokument.nummer });
    panel.append(node('h2', titel));
    const zeile = (u
      ? [lieferung.lagerort.code + ' · ' + lieferung.lagerort.name, t('wareneingaenge.sent_on', { datum: datum(u.versanddatum) }), u.tage_unterwegs !== null && u.tage_unterwegs !== undefined ? t('wareneingaenge.transit_days', { tage: u.tage_unterwegs }) : null]
      : [
        lieferung.dokument.lieferant ? t('wareneingaenge.supplier_prefix') + lieferung.dokument.lieferant : null,
        lieferung.lagerort.code + ' · ' + lieferung.lagerort.name,
        datum(lieferung.dokument.datum)
      ]).filter(Boolean).join(' · ');
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
    const umleitung = umleitenBereich(lieferung);
    if (umleitung) panel.append(umleitung);
    const rest = restBereich(lieferung);
    if (rest) panel.append(rest);
    return panel;
  }

  // Bisherige Umleitungen als Zeile, dazu (nur für Filialleiter/Zentrale und nur
  // solange nichts angekommen ist) die Wahl einer anderen Filiale.
  function umleitenBereich(lieferung) {
    if (lieferung.umlagerung) return null;
    const bereich = node('div', null, 'redirect');
    (lieferung.umleitungen || []).forEach((u) => {
      bereich.append(node('p', t('wareneingaenge.redirect_history', { von: u.von.code, nach: u.nach.code }), 'muted'));
    });
    const schonAngekommen = lieferung.positionen.some((p) => Number(p.menge_eingetroffen) > 0);
    if (!umleitenZiele || schonAngekommen) return bereich.childElementCount ? bereich : null;
    const zeile = node('div', null, 'filters');
    const label = node('label', t('wareneingaenge.redirect_label'));
    const auswahl = document.createElement('select');
    auswahl.append(new Option(t('wareneingaenge.redirect_choose'), ''));
    umleitenZiele.filter((z) => z.id !== lieferung.lagerort.id).forEach((z) => auswahl.append(new Option(z.code + ' · ' + z.name, String(z.id))));
    label.append(auswahl);
    const knopf = node('button', t('wareneingaenge.redirect_button'), 'secondary');
    knopf.type = 'button';
    const rueckmeldung = node('p', '', 'muted');
    rueckmeldung.setAttribute('role', 'status');
    knopf.addEventListener('click', async () => {
      if (!auswahl.value) return;
      knopf.disabled = true;
      try {
        const antwort = await fetch('/api/wareneingaenge/' + lieferung.id + '/umleitung', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lagerort_id: Number(auswahl.value) })
        });
        const ergebnis = await antwort.json();
        if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('wareneingaenge.load_error'));
        await laden();
        $('status').textContent = t('wareneingaenge.redirected_done', { ziel: ergebnis.nach.code });
      } catch (fehler) {
        rueckmeldung.textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
        knopf.disabled = false;
      }
    });
    zeile.append(label, knopf);
    bereich.append(zeile, node('p', t('wareneingaenge.redirect_hint'), 'muted'), rueckmeldung);
    return bereich;
  }

  // Offener Rest nach einer Teilankunft (Paket 4b): in Klärung setzen (alle),
  // als verloren oder vom Lieferanten storniert erklären (Filialleiter/Zentrale).
  function restBereich(lieferung) {
    const offene = lieferung.positionen.filter((p) => Number(p.menge_offen) > 0 && Number(p.menge_eingetroffen) > 0);
    const erklaerte = lieferung.positionen.filter((p) => (p.differenzen || []).length);
    if (!offene.length && !erklaerte.length) return null;
    const bereich = node('div', null, 'remainder');
    bereich.append(node('h3', t('wareneingaenge.remainder_heading')));
    for (const position of lieferung.positionen) {
      const name = [position.marke, position.bezeichnung, [position.farbe, position.groesse].filter(Boolean).join(' / ')].filter(Boolean).join(' ');
      for (const d of position.differenzen || []) {
        const text = t('wareneingaenge.difference.' + d.art, { menge: menge(d.menge), artikel: name }) + (d.notiz ? ': ' + d.notiz : '') + (d.aufgeloest ? ' ' + t('wareneingaenge.difference.resolved') : '');
        bereich.append(node('p', text, 'muted'));
      }
    }
    for (const position of offene) {
      const name = [position.marke, position.bezeichnung, [position.farbe, position.groesse].filter(Boolean).join(' / ')].filter(Boolean).join(' ');
      const zeile = node('div', null, 'filters');
      zeile.append(node('p', t('wareneingaenge.remainder_line', { artikel: name, offen: menge(position.menge_offen) })));
      const anzahl = document.createElement('input');
      anzahl.type = 'number';
      anzahl.min = '1';
      anzahl.step = '1';
      anzahl.value = menge(position.menge_offen);
      anzahl.setAttribute('aria-label', t('wareneingaenge.remainder_quantity'));
      const notiz = document.createElement('input');
      notiz.type = 'text';
      notiz.maxLength = 200;
      notiz.setAttribute('aria-label', t('wareneingaenge.remainder_note'));
      notiz.placeholder = t('wareneingaenge.remainder_note');
      const rueckmeldung = node('p', '', 'muted');
      rueckmeldung.setAttribute('role', 'status');
      const knoepfe = [['in_klaerung', true]];
      if (darfVerwalten) {
        knoepfe.push(['verloren', true]);
        if (!lieferung.umlagerung) knoepfe.push(['lieferant_storniert', true]);
      }
      zeile.append(anzahl, notiz);
      for (const [art] of knoepfe) {
        const knopf = node('button', t('wareneingaenge.action.' + art), 'secondary');
        knopf.type = 'button';
        knopf.addEventListener('click', () => erklaeren(lieferung, position, art, anzahl.value, notiz.value, knopf, rueckmeldung));
        zeile.append(knopf);
      }
      bereich.append(zeile, rueckmeldung);
    }
    return bereich;
  }

  async function erklaeren(lieferung, position, art, anzahl, notiz, knopf, rueckmeldung) {
    knopf.disabled = true;
    try {
      const antwort = await fetch('/api/wareneingaenge/' + lieferung.id + '/differenz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_id: position.id, art: art, menge: anzahl, notiz: notiz.trim() || null })
      });
      const ergebnis = await antwort.json().catch(() => ({}));
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('wareneingaenge.load_error'));
      await laden();
      $('status').textContent = t(ergebnis.status === 'abgeschlossen' ? 'wareneingaenge.remainder_closed' : 'wareneingaenge.remainder_saved');
    } catch (fehler) {
      rueckmeldung.textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      knopf.disabled = false;
    }
  }

  async function umleitenZieleLaden() {
    if (umleitenZiele !== null) return;
    umleitenZiele = [];
    try {
      const me = await (await fetch('/api/me')).json();
      if (!['chef', 'admin'].includes(me.role)) return;
      darfVerwalten = true;
      const stamm = await (await fetch('/api/erfassen/stammdaten')).json();
      umleitenZiele = stamm.lagerorte || [];
    } catch (fehler) {
      // Ohne Ziele bleibt nur die Anzeige - die Seite arbeitet sonst normal weiter.
    }
  }

  async function bestaetigen(lieferung, panel, datumsfeld, knopf, rueckmeldung) {
    const mengen = {};
    for (const eingabe of panel.querySelectorAll('input[data-position]')) {
      if (eingabe.value !== '' && Number(eingabe.value) !== 0) mengen[eingabe.dataset.position] = eingabe.value;
    }
    knopf.disabled = true;
    knopf.classList.add('is-loading');
    rueckmeldung.textContent = t('wareneingaenge.saving');
    try {
      const antwort = await SportfabrikOp.fetch('/api/wareneingaenge/' + lieferung.id + '/ankunft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mengen: mengen, eingangsdatum: datumsfeld ? datumsfeld.value : null })
      });
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('wareneingaenge.load_error'));
      let meldung = ['eingetroffen', 'abgeschlossen'].includes(ergebnis.status)
        ? t('wareneingaenge.confirmed_complete')
        : t('wareneingaenge.confirmed_partial', { offen: ergebnis.offene_positionen });
      // Mehr eingetroffen als erwartet: gebucht wird trotzdem, gesagt wird es
      // aber - sonst merkt es niemand.
      const mehrlieferungen = ergebnis.mehrlieferungen || [];
      if (mehrlieferungen.length) {
        meldung += ' ' + t('wareneingaenge.over_delivery', { anzahl: mehrlieferungen.length });
      }
      // Erst neu laden, dann melden: das Neuladen ersetzt diesen Abschnitt
      // samt seiner Rückmeldungszeile, die Meldung gehört also in die
      // Seitenzeile, die stehen bleibt.
      await laden();
      $('status').textContent = meldung;
    } catch (fehler) {
      rueckmeldung.textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
    } finally {
      knopf.disabled = false;
      knopf.classList.remove('is-loading');
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
      await umleitenZieleLaden();
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
