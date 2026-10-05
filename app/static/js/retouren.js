// Kundenretouren (Paket 4a): Ware kommt in die Prüfung (gesperrt), nicht in den Verkauf.
// Alle Texte über window.SportfabrikI18n.t() - keine harten Zeichenketten (Regel 7).
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const STATUS = ['beantragt', 'in_pruefung', 'abgeschlossen', 'abgelehnt'];
  let stamm = { gruende: [], zustaende: [], darf_verwalten: false };
  let artikel = null;
  let retouren = [];
  let offset = 0;
  let listenWahl = null;
  let bucht = false;

  function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function menge(wert) {
    const zahl = Number(wert);
    return Number.isFinite(zahl) ? String(zahl) : String(wert ?? '—');
  }

  function fehlertext(fehler) {
    return fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
  }

  async function anfrage(url, daten, methode) {
    const optionen = { method: methode || (daten === undefined ? 'GET' : 'POST') };
    if (optionen.method === 'POST') {
      optionen.headers = { 'Content-Type': 'application/json' };
      if (daten !== undefined) optionen.body = JSON.stringify(daten);
    }
    const antwort = await (optionen.method === 'POST' ? SportfabrikOp.fetch(url, optionen) : fetch(url));
    const ergebnis = await antwort.json().catch(() => ({}));
    if (!antwort.ok) {
      throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('common.errors.request_failed'));
    }
    return ergebnis;
  }

  function zeitText(wert) {
    const ort = { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' }[window.SportfabrikI18n.lang] || 'de-CH';
    const datum = new Date(wert);
    return datum.toLocaleDateString(ort) + ' ' + datum.toLocaleTimeString(ort, { hour: '2-digit', minute: '2-digit' });
  }

  function artikelName(eintrag) {
    const name = [eintrag.marke || eintrag.brand, eintrag.bezeichnung || eintrag.description].filter(Boolean).join(' ') || '—';
    const variante = [eintrag.farbe || eintrag.color, eintrag.groesse || eintrag.size].filter(Boolean).join(' / ');
    return variante ? name + ' (' + variante + ')' : name;
  }

  // --- Formular --------------------------------------------------------

  function auswahlFuellen() {
    const grund = $('grund').value;
    $('grund').replaceChildren();
    for (const eintrag of stamm.gruende) {
      $('grund').add(new Option(t('retouren.reason.' + eintrag.grund), eintrag.grund));
    }
    if (grund) $('grund').value = grund;
    const zustand = $('zustand').value;
    $('zustand').replaceChildren();
    for (const code of stamm.zustaende) $('zustand').add(new Option(t('retouren.condition.' + code), code));
    if (zustand) $('zustand').value = zustand;
    const status = $('listeStatus').value;
    $('listeStatus').replaceChildren(new Option(t('retouren.status_all'), ''));
    for (const code of STATUS) $('listeStatus').add(new Option(t('retouren.status.' + code), code));
    $('listeStatus').value = status;
    formularUmschalten();
  }

  function formularUmschalten() {
    const eintrag = stamm.gruende.find((g) => g.grund === $('grund').value);
    $('antragHinweis').hidden = !eintrag || eintrag.direkt;
    $('freitextFeld').hidden = $('grund').value !== 'sonstiges';
    // Sofort freigeben: nur bei direkt buchbarem Grund und neuwertiger Ware.
    const sofort = !!eintrag && eintrag.direkt && $('zustand').value === 'neuwertig';
    $('sofortFeld').hidden = !sofort;
    if (!sofort) $('sofort').checked = false;
  }

  function artikelWaehlen(eintrag) {
    artikel = eintrag;
    $('gewaehlt').textContent = t('retouren.chosen', { artikel: artikelName(eintrag) });
    $('gewaehlt').hidden = false;
    $('retoureForm').hidden = false;
    $('suchListe').replaceChildren();
    $('suchStatus').textContent = '';
    $('buchStatus').textContent = '';
    $('grund').focus();
  }

  async function suchen() {
    const q = $('suchFeld').value.trim();
    if (!q) return;
    $('suchStatus').textContent = t('bestand.loading');
    try {
      const daten = await anfrage('/api/articles?page_size=20&q=' + encodeURIComponent(q));
      const items = daten.items || [];
      if (items.length === 1) {
        artikelWaehlen(items[0]);
        return;
      }
      const tbody = document.createElement('tbody');
      for (const eintrag of items) {
        const tr = document.createElement('tr');
        const name = node('td');
        name.append(node('strong', [eintrag.brand, eintrag.description].filter(Boolean).join(' ') || '—'));
        const nummern = [eintrag.supplier_article_no, eintrag.ean].filter(Boolean).join(' · ');
        if (nummern) name.append(document.createElement('br'), node('span', nummern, 'muted'));
        const aktion = node('td');
        const knopf = node('button', t('retouren.choose'), 'secondary');
        knopf.type = 'button';
        knopf.addEventListener('click', () => artikelWaehlen(eintrag));
        aktion.append(knopf);
        tr.append(name, node('td', eintrag.color || '—'), node('td', eintrag.size || '—'), aktion);
        tbody.append(tr);
      }
      const tabelle = document.createElement('table');
      tabelle.append(tbody);
      $('suchListe').replaceChildren(tabelle);
      $('suchListe').hidden = !items.length;
      $('suchStatus').textContent = items.length ? '' : t('retouren.search_empty');
    } catch (fehler) {
      $('suchStatus').textContent = fehlertext(fehler);
    }
  }

  async function buchen(ereignis) {
    ereignis.preventDefault();
    if (!artikel || bucht) return;
    const grund = $('grund').value;
    const freitext = $('freitext').value.trim();
    if (grund === 'sonstiges' && !freitext) {
      $('buchStatus').textContent = t('errors.ausbuchung.text_required');
      $('buchStatus').className = 'warning-text';
      $('freitext').focus();
      return;
    }
    bucht = true;
    $('buchStatus').className = '';
    $('buchStatus').textContent = t('ausbuchen.booking');
    try {
      const ergebnis = await anfrage('/api/retouren', {
        varianten_id: artikel.id ?? artikel.varianten_id,
        lagerort_id: Number($('lagerort').value) || null,
        grund: grund,
        zustand: $('zustand').value,
        menge: Number($('menge').value) || 1,
        freitext: grund === 'sonstiges' ? freitext : null,
        erstattungsreferenz: $('referenz').value.trim() || null,
        sofort_freigeben: $('sofort').checked
      });
      const key = ergebnis.status === 'beantragt' ? 'retouren.booked_request'
        : ergebnis.status === 'abgeschlossen' ? 'retouren.booked_released' : 'retouren.booked_held';
      $('buchStatus').textContent = t(key, { artikel: artikelName(artikel), menge: menge(ergebnis.menge) });
      $('freitext').value = '';
      $('referenz').value = '';
      $('menge').value = '1';
      listeLaden(false);
    } catch (fehler) {
      $('buchStatus').textContent = fehlertext(fehler);
      $('buchStatus').className = 'warning-text';
    } finally {
      bucht = false;
    }
  }

  // --- Liste -----------------------------------------------------------

  async function aktion(retoure, pfad, daten) {
    try {
      await anfrage('/api/retouren/' + retoure.id + pfad, daten === undefined ? {} : daten, 'POST');
      $('status').textContent = '';
      listeLaden(false);
    } catch (fehler) {
      $('status').textContent = fehlertext(fehler);
    }
  }

  function knopf(text, handler, cls) {
    const el = node('button', text, cls || 'secondary');
    el.type = 'button';
    el.addEventListener('click', handler);
    return el;
  }

  function aktionen(retoure) {
    const zelle = node('td');
    const direkt = ['passform', 'geschmack'].includes(retoure.grund);
    if (retoure.status === 'beantragt' && stamm.darf_verwalten) {
      zelle.append(
        knopf(t('retouren.action.approve'), () => aktion(retoure, '/genehmigen'), ''),
        knopf(t('retouren.action.reject'), () => aktion(retoure, '/ablehnen'))
      );
    } else if (retoure.status === 'in_pruefung') {
      if (stamm.darf_verwalten || direkt) {
        zelle.append(knopf(t('retouren.action.release'), () => aktion(retoure, '/ergebnis', { ergebnis: 'freigeben' }), ''));
      }
      if (stamm.darf_verwalten) {
        zelle.append(
          knopf(t('retouren.action.supplier'), () => aktion(retoure, '/ergebnis', { ergebnis: 'lieferant' })),
          knopf(t('retouren.action.writeoff'), () => aktion(retoure, '/ergebnis', { ergebnis: 'abschreiben' }))
        );
      }
    }
    return zelle;
  }

  function zeichnen() {
    $('leer').hidden = retouren.length > 0;
    $('liste').hidden = retouren.length === 0;
    $('rows').replaceChildren();
    for (const retoure of retouren) {
      const tr = document.createElement('tr');
      tr.append(node('td', zeitText(retoure.erfasst_am)));
      const name = node('td', [retoure.marke, retoure.bezeichnung].filter(Boolean).join(' ') || '—');
      if (retoure.erstattungsreferenz) {
        name.append(document.createElement('br'), node('span', retoure.erstattungsreferenz, 'muted'));
      }
      tr.append(name);
      tr.append(node('td', [retoure.farbe, retoure.groesse].filter(Boolean).join(' / ') || '—'));
      tr.append(node('td', retoure.lagerort.code));
      tr.append(node('td', menge(retoure.menge)));
      const grund = t('retouren.reason.' + retoure.grund) + (retoure.freitext ? ': ' + retoure.freitext : '');
      tr.append(node('td', grund));
      tr.append(node('td', t('retouren.condition.' + retoure.zustand)));
      const status = t('retouren.status.' + retoure.status) + (retoure.ergebnis ? ' · ' + t('retouren.outcome.' + retoure.ergebnis) : '');
      tr.append(node('td', status));
      tr.append(aktionen(retoure));
      $('rows').append(tr);
    }
  }

  async function listeLaden(anhaengen) {
    const parameter = new URLSearchParams();
    if (listenWahl === 'alle') parameter.set('alle', 'true');
    else if (listenWahl) parameter.set('lagerort_id', listenWahl);
    if ($('listeStatus').value) parameter.set('status', $('listeStatus').value);
    parameter.set('offset', String(anhaengen ? offset : 0));
    try {
      const daten = await anfrage('/api/retouren?' + parameter.toString());
      retouren = anhaengen ? retouren.concat(daten.zeilen) : daten.zeilen;
      offset = daten.offset + daten.zeilen.length;
      if (listenWahl === null) {
        listenWahl = daten.gewaehlt === null ? 'alle' : String(daten.gewaehlt);
        $('listeLagerort').value = listenWahl;
      }
      $('mehr').hidden = !daten.hat_mehr;
      zeichnen();
    } catch (fehler) {
      $('status').textContent = fehlertext(fehler);
    }
  }

  async function stammdatenLaden() {
    $('retry').hidden = true;
    try {
      const [retourStamm, ausbuchStamm] = await Promise.all([
        anfrage('/api/retouren/stammdaten'),
        anfrage('/api/ausbuchen/stammdaten')
      ]);
      stamm = retourStamm;
      $('lagerort').replaceChildren();
      for (const lagerort of ausbuchStamm.lagerorte || []) {
        $('lagerort').add(new Option(lagerort.code + ' · ' + lagerort.name, lagerort.id));
        $('listeLagerort').add(new Option(lagerort.code + ' · ' + lagerort.name, lagerort.id));
      }
      if (ausbuchStamm.lagerort_aktiv) $('lagerort').value = String(ausbuchStamm.lagerort_aktiv);
      auswahlFuellen();
      $('status').textContent = '';
    } catch (fehler) {
      $('status').textContent = fehlertext(fehler);
      $('retry').hidden = false;
    }
  }

  $('suchForm').addEventListener('submit', (ereignis) => {
    ereignis.preventDefault();
    suchen();
  });
  $('retoureForm').addEventListener('submit', buchen);
  $('grund').addEventListener('change', formularUmschalten);
  $('zustand').addEventListener('change', formularUmschalten);
  $('retry').addEventListener('click', stammdatenLaden);
  $('listeLagerort').addEventListener('change', () => {
    listenWahl = $('listeLagerort').value;
    listeLaden(false);
  });
  $('listeStatus').addEventListener('change', () => listeLaden(false));
  $('mehr').addEventListener('click', () => listeLaden(true));

  window.SportfabrikI18n.ready.then(async () => {
    await stammdatenLaden();
    listeLaden(false);
    document.addEventListener('sportfabrik:i18n-ready', () => {
      auswahlFuellen();
      zeichnen();
    });
  });
})();
