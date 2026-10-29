// Gemeinsame Diagramm-Bausteine für Übersicht und Statistik (2026-10-01):
// Ring (Donut) mit Legende, Liniendiagramm mit Achsen, Vergleichs-Pfeil.
// Nur SVG/HTML aus Tokens, keine Bibliothek (DESIGN.md 9.3); jede Zahl steht
// auch als Text. Alle Texte über window.SportfabrikI18n.t() (Regel 7).
(function () {
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const SVG = 'http://www.w3.org/2000/svg';

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

  // Kurzes Datum ohne Jahr in der Sprache der Oberfläche (Diagrammachsen).
  function datumKurz(wert) {
    return new Intl.DateTimeFormat(sprache(), { day: '2-digit', month: '2-digit' }).format(new Date(wert + 'T12:00:00'));
  }

  function summe(werte) {
    return werte.reduce((a, b) => a + b, 0);
  }

  // Ring mit Legende. eintraege = [{ name: string|null, menge: number }]; null = „ohne Kategorie".
  // Mittlere Zahl = Gesamtmenge. `leer` wird gezeigt, wenn nichts da ist.
  function donut(ring, liste, leer, eintraege) {
    const gesamt = summe(eintraege.map((e) => e.menge));
    ring.replaceChildren();
    liste.replaceChildren();
    ring.hidden = liste.hidden = gesamt === 0;
    leer.hidden = gesamt !== 0;
    if (gesamt === 0) return;
    let start = 0;
    eintraege.forEach((e, index) => {
      const anteil = e.menge / gesamt * 100;
      const farbe = e.name === null ? 'none' : String(index % 5 + 1);
      const bogen = document.createElementNS(SVG, 'circle');
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
    const mitte = document.createElementNS(SVG, 'text');
    mitte.setAttribute('class', 'donut-total');
    mitte.setAttribute('x', '21');
    mitte.setAttribute('y', '23.2');
    mitte.setAttribute('text-anchor', 'middle');
    mitte.textContent = zahl(gesamt);
    ring.append(mitte);
  }

  // Runde Achsenschritte (1, 2, 5 × 10^n): „gerundete Zahlen" auf der senkrechten Achse.
  function achsenschritt(spanne, ziel) {
    const roh = spanne / ziel;
    const zehner = Math.pow(10, Math.floor(Math.log10(roh)));
    const rest = roh / zehner;
    return (rest <= 1 ? 1 : rest <= 2 ? 2 : rest <= 5 ? 5 : 10) * zehner;
  }

  // Liniendiagramm in `huelle` (Elemente: Zahlen links, Linie, Daten unten).
  // reihe = [{ tag: 'JJJJ-MM-TT', wert: number }], ältester zuerst.
  function linie(huelle, reihe, beschriftung) {
    huelle.replaceChildren();
    if (!reihe.length) return;
    const werte = reihe.map((p) => p.wert);
    const tiefster = Math.min(...werte);
    const hoechster = Math.max(...werte);
    let unten = 0;
    let oben = 1;
    let schritt = 1;
    if (hoechster === tiefster) {
      // Flache Linie: Achse von 0 bis zum nächsten runden Wert.
      schritt = achsenschritt(Math.max(hoechster, 1), 2);
      oben = Math.max(schritt, Math.ceil(hoechster / schritt) * schritt);
    } else {
      schritt = achsenschritt(hoechster - tiefster, 3);
      unten = Math.floor(tiefster / schritt) * schritt;
      oben = Math.ceil(hoechster / schritt) * schritt;
    }
    const ticks = [];
    for (let v = unten; v <= oben + schritt / 1000; v += schritt) ticks.push(v);

    const y = (wert) => 100 - (wert - unten) / (oben - unten) * 100;
    const punkte = reihe.map((p, index) => {
      const x = reihe.length > 1 ? index / (reihe.length - 1) * 300 : 150;
      return x.toFixed(1) + ',' + y(p.wert).toFixed(1);
    });

    const achseY = node('ul', null, 'chart-y');
    ticks.slice().reverse().forEach((v) => achseY.append(node('li', zahl(v))));
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('class', 'linechart');
    svg.setAttribute('viewBox', '0 0 300 100');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', beschriftung);
    ticks.forEach((v) => {
      const raster = document.createElementNS(SVG, 'line');
      raster.setAttribute('class', 'chart-grid');
      raster.setAttribute('x1', '0');
      raster.setAttribute('x2', '300');
      raster.setAttribute('y1', y(v).toFixed(1));
      raster.setAttribute('y2', y(v).toFixed(1));
      svg.append(raster);
    });
    const flaeche = document.createElementNS(SVG, 'path');
    flaeche.setAttribute('class', 'line-area');
    flaeche.setAttribute('d', 'M' + punkte.join(' L') + ' L300,100 L0,100 Z');
    const strich = document.createElementNS(SVG, 'polyline');
    strich.setAttribute('class', 'line-stroke');
    strich.setAttribute('points', punkte.join(' '));
    svg.append(flaeche, strich);

    // Höchstens 5 Daten waagrecht, gleichmässig verteilt, immer Anfang und Ende.
    const achseX = node('ul', null, 'chart-x');
    const anzahl = Math.min(5, reihe.length);
    const nummern = new Set();
    for (let i = 0; i < anzahl; i++) nummern.add(Math.round(i * (reihe.length - 1) / Math.max(anzahl - 1, 1)));
    [...nummern].forEach((nummer) => achseX.append(node('li', datumKurz(reihe[nummer].tag))));

    huelle.append(achseY, svg, node('span'), achseX);
  }

  // Vergleich zur Vorperiode: roter Pfeil nach unten = weniger, grüner nach oben = mehr,
  // daneben die Prozentzahl. Ohne Basis (null) steht nur ein Hinweis - keine erfundene Zahl.
  // Farbe ist nie allein: Pfeil, Vorzeichen und ein verstecktes „mehr/weniger".
  function vergleich(el, prozent, vorperiode) {
    el.replaceChildren();
    el.className = 'insight-delta compare';
    if (prozent === null || prozent === undefined) {
      el.append(node('span', t('dashboard.compare_none'), 'muted'));
      return;
    }
    const wert = Number(prozent);
    const richtung = wert > 0 ? 'up' : wert < 0 ? 'down' : 'same';
    el.classList.add('is-' + richtung);
    const pfeil = node('span', wert > 0 ? '▲' : wert < 0 ? '▼' : '■', 'compare-arrow');
    pfeil.setAttribute('aria-hidden', 'true');
    const betrag = new Intl.NumberFormat(sprache(), { maximumFractionDigits: 1 }).format(Math.abs(wert));
    const zeichen = wert > 0 ? '+' : wert < 0 ? '−' : '';
    el.append(pfeil, node('strong', zeichen + betrag + ' %'),
      node('span', t('dashboard.compare_' + (wert > 0 ? 'more' : wert < 0 ? 'less' : 'same')), 'visually-hidden'),
      node('span', t('dashboard.compare_vs_' + vorperiode), 'muted'));
  }

  window.SportfabrikDiagramme = { zahl, datumKurz, summe, donut, linie, vergleich };
})();
