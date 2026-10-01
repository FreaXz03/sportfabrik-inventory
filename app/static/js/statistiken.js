(() => {
  if (location.pathname !== '/statistiken') return;
  const $ = id => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const node = (tag, text) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; return e; };
  const chf = value => new Intl.NumberFormat('de-CH', { style: 'currency', currency: 'CHF' }).format(Number(value));
  const menge = value => new Intl.NumberFormat('de-CH').format(Number(value));
  let lagerorteGesetzt = false;

  function svgNode(tag, attributes, text) {
    const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attributes)) e.setAttribute(k, v);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function kategorieLabel(zeile) {
    if (!zeile.hauptgruppe) return t('statistik.no_category');
    return zeile.sportbereich ? zeile.hauptgruppe + ' · ' + zeile.sportbereich : zeile.hauptgruppe;
  }

  function drawKategorien(kategorien) {
    $('kategorienLeer').hidden = !!kategorien.length;
    const container = $('kategorienChart');
    container.replaceChildren();
    if (!kategorien.length) return;
    const max = Math.max(...kategorien.map(k => Number(k.stueck)));
    const rowHeight = 28;
    const height = kategorien.length * rowHeight + 10;
    const svg = svgNode('svg', { viewBox: `0 0 900 ${height}`, class: 'price-chart', role: 'img', 'aria-label': t('statistik.kategorien_heading') });
    kategorien.forEach((zeile, index) => {
      const y = index * rowHeight + 5;
      const wert = Number(zeile.stueck);
      const breite = max > 0 ? (wert / max) * 620 : 0;
      svg.append(
        svgNode('text', { x: 0, y: y + 15, fill: 'var(--text)', 'font-size': 13 }, kategorieLabel(zeile)),
        svgNode('rect', { x: 260, y, width: Math.max(breite, 2), height: rowHeight - 8, fill: 'var(--accent)' }),
        svgNode('text', { x: 260 + breite + 8, y: y + 15, fill: 'var(--text-muted)', 'font-size': 13 }, menge(zeile.stueck))
      );
    });
    container.append(svg);
  }

  function drawEmpfehlung(zeilen) {
    const body = $('empfehlungRows');
    body.replaceChildren();
    for (const zeile of zeilen) {
      const tr = document.createElement('tr');
      const name = [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') + (zeile.lieferanten_artikelnr ? ' (' + zeile.lieferanten_artikelnr + ')' : '');
      tr.append(node('td', name), node('td', menge(zeile.verkauft)), node('td', menge(zeile.bestand)));
      body.append(tr);
    }
  }

  // Klarstellung 25.09.2026: Abgänge ausser Verkauf je Grund, mit Person.
  function grundText(grund, freitext) {
    const text = t('ausbuchen.reason.' + grund);
    return freitext ? text + ': ' + freitext : text;
  }

  function zeitText(wert) {
    const ort = { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' }[window.SportfabrikI18n.lang] || 'de-CH';
    const datum = new Date(wert);
    return datum.toLocaleDateString(ort) + ' ' + datum.toLocaleTimeString(ort, { hour: '2-digit', minute: '2-digit' });
  }

  function drawAbgaenge(abgaenge) {
    const leer = !abgaenge.je_grund.length;
    $('abgaengeTotal').textContent = t('statistik.abgaenge_total', { anzahl: menge(abgaenge.stueck) });
    $('abgaengeLeer').hidden = !leer;
    for (const id of ['abgaengeTotal', 'abgaengeGruende', 'abgaengeLetzte']) $(id).hidden = leer;
    $('abgaengeLetzte').previousElementSibling.hidden = leer;
    $('abgaengeGrundRows').replaceChildren(...abgaenge.je_grund.map((zeile) => {
      const tr = document.createElement('tr');
      tr.append(node('td', grundText(zeile.grund)), node('td', menge(zeile.stueck)));
      return tr;
    }));
    $('abgaengeLetzteRows').replaceChildren(...abgaenge.letzte.map((zeile) => {
      const tr = document.createElement('tr');
      tr.append(
        node('td', zeitText(zeile.zeitpunkt)),
        node('td', [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') || '—'),
        node('td', grundText(zeile.grund, zeile.freitext)),
        node('td', zeile.lagerort),
        node('td', zeile.person || '—')
      );
      return tr;
    }));
  }

  // --- Verkäufe und Bestand der aktiven Filiale (von der Übersicht hierher verschoben, 2026-10-01).
  const D = window.SportfabrikDiagramme;

  function datumKurz(wert) { return D.datumKurz(wert); }

  function verlauf(f) {
    const tage = f.verlauf || [];
    const werte = tage.map((tag) => Number(tag.verkauft));
    const woche = D.summe(werte.slice(-7));
    const davor = D.summe(werte.slice(-14, -7));
    $('trendWoche').textContent = t('dashboard.trend_week', { anzahl: D.zahl(woche) });
    const unterschied = woche - davor;
    $('trendDelta').textContent = unterschied === 0
      ? t('dashboard.trend_same')
      : t(unterschied > 0 ? 'dashboard.trend_up' : 'dashboard.trend_down', { anzahl: D.zahl(Math.abs(unterschied)) });
    const hoechster = Math.max(1, ...werte);
    const balken = $('trendBalken');
    balken.replaceChildren();
    tage.forEach((tag, index) => {
      const eintrag = document.createElement('span');
      eintrag.className = index === tage.length - 1 ? 'bar is-today' : 'bar';
      eintrag.style.setProperty('--h', String(werte[index] / hoechster));
      eintrag.title = t('dashboard.trend_bar', { datum: datumKurz(tag.tag), anzahl: D.zahl(werte[index]) });
      balken.append(eintrag);
    });
  }

  function bestseller(f) {
    const liste = $('bestsellerListe');
    liste.replaceChildren();
    const eintraege = f.bestseller || [];
    const hoechster = Math.max(1, ...eintraege.map((e) => Number(e.stueck)));
    for (const e of eintraege) {
      const li = document.createElement('li');
      li.className = 'rank';
      li.append(node('span', [e.marke, e.bezeichnung].filter(Boolean).join(' ')), node('strong', D.zahl(e.stueck)));
      li.firstChild.className = 'rank-name';
      li.lastChild.className = 'rank-qty';
      const spur = document.createElement('span');
      spur.className = 'rank-bar';
      spur.style.setProperty('--w', String(Number(e.stueck) / hoechster));
      li.append(spur);
      liste.append(li);
    }
    $('bestsellerLeer').hidden = eintraege.length > 0;
  }

  // Ein Kreisdiagramm je Hauptgruppe, aufgeschlüsselt nach Sportbereich.
  const PIE_GRUPPEN = ['Schuhe', 'Textil', 'Hartware'];

  function gruppenKreise(gruppen) {
    const raster = $('pieGrid');
    raster.replaceChildren();
    for (const gruppe of PIE_GRUPPEN) {
      const huelle = document.createElement('section');
      huelle.className = 'panel insight';
      const titel = node('h3', gruppe);
      titel.className = 'insight-title';
      const hinweis = node('p', t('statistik.pie_hint'));
      hinweis.className = 'muted';
      const wrap = document.createElement('div');
      wrap.className = 'donut-wrap';
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'donut donut-md');
      svg.setAttribute('viewBox', '0 0 42 42');
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', t('statistik.pie_aria', { gruppe: gruppe }));
      const liste = document.createElement('ul');
      liste.className = 'cat-legend';
      wrap.append(svg, liste);
      const leer = node('p', t('dashboard.cats_empty'));
      leer.className = 'muted';
      huelle.append(titel, hinweis, wrap, leer);
      raster.append(huelle);
      D.donut(svg, liste, leer, (gruppen[gruppe] || []).map((e) => ({
        name: e.sportbereich === null ? t('statistik.pie_no_area') : e.sportbereich,
        menge: Number(e.stueck),
      })));
    }
  }

  async function filialeLaden() {
    try {
      const antwort = await fetch('/api/dashboard');
      const daten = await antwort.json();
      if (!antwort.ok) return;
      const f = daten.filiale;
      $('filialeBlock').hidden = !f;
      if (!f) return;
      $('filialeTitel').textContent = t('statistik.filiale_heading', { filiale: daten.lagerort.code + ' · ' + daten.lagerort.name });
      $('verkauftHeute').textContent = D.zahl(f.verkauft_heute);
      $('abgaengeText').textContent = t('dashboard.metric_removed_today', { anzahl: D.zahl(f.abgaenge_heute) });
      verlauf(f);
      bestseller(f);
      D.donut($('catsDonut'), $('catsListe'), $('catsLeer'),
        (f.kategorien || []).map((e) => ({ name: e.hauptgruppe, menge: Number(e.stueck) })));
      gruppenKreise(f.bestand_gruppen || {});
    } catch (fehler) {
      // Beiwerk: ohne Verbindung bleibt der Block verborgen, die übrige Statistik meldet den Fehler selbst.
    }
  }

  function lagerorteFuellen(lagerorte) {
    if (lagerorteGesetzt) return;
    const auswahl = $('lagerort');
    const alle = new Option(t('statistik.filter_lagerort_alle'), '');
    auswahl.add(alle);
    for (const lagerort of lagerorte) {
      auswahl.add(new Option(lagerort.code + ' · ' + lagerort.name, String(lagerort.id)));
    }
    lagerorteGesetzt = true;
  }

  async function laden() {
    $('status').textContent = t('statistik.loading');
    $('status').hidden = false;
    $('retry').hidden = true;
    for (const id of ['einnahmenPanel', 'kategorienPanel', 'empfehlungPanel', 'abgaengePanel']) $(id).hidden = true;
    try {
      const parameter = new URLSearchParams({ zeitraum: $('zeitraum').value });
      if ($('lagerort').value) parameter.set('lagerort_id', $('lagerort').value);
      const antwort = await fetch('/api/statistik?' + parameter.toString());
      if (!antwort.ok) throw new Error(t('common.errors.request_failed'));
      const daten = await antwort.json();
      lagerorteFuellen(daten.lagerorte || []);
      $('status').hidden = true;
      $('einnahmenBetrag').textContent = chf(daten.einnahmen_geschaetzt);
      $('einnahmenPanel').hidden = false;
      drawKategorien(daten.kategorien);
      $('kategorienPanel').hidden = false;
      drawEmpfehlung(daten.bestellempfehlung);
      $('empfehlungPanel').hidden = false;
      drawAbgaenge(daten.abgaenge);
      $('abgaengePanel').hidden = false;
    } catch (e) {
      $('status').textContent = e.message;
      $('retry').hidden = false;
    }
  }

  $('retry').addEventListener('click', laden);
  $('zeitraum').addEventListener('change', laden);
  $('lagerort').addEventListener('change', laden);
  window.SportfabrikI18n.ready.then(() => { laden(); filialeLaden(); });
  document.addEventListener('sportfabrik:i18n-ready', filialeLaden);
})();
