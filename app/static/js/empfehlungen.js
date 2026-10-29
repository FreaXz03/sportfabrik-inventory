// Empfehlung der Zentrale (D-F3, 25.09.2026): je Modell und Filiale eine
// Stufe ab einem Datum vorschlagen; Übersicht mit dem Antwortstatus je
// Filiale (Abweichungen).
(() => {
  if (location.pathname !== '/empfehlungen') return;
  const $ = id => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const node = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
  const heute = () => new Date().toISOString().slice(0, 10);
  let lagerorte = [];

  async function api(path, options) {
    const r = await fetch(path, options);
    let data;
    try { data = await r.json(); } catch { data = null; }
    if (!r.ok) throw new Error((data && typeof data.detail === 'string') ? data.detail : t('common.errors.request_failed'));
    return data;
  }

  function statusLabel(zeile) {
    if (zeile.status === 'offen') return t('empfehlung.status.offen');
    if (zeile.status === 'uebernommen') return t('empfehlung.status.uebernommen');
    if (zeile.status === 'zurueckgezogen') return t('empfehlung.status.zurueckgezogen');
    return t('empfehlung.status.abgelehnt') + (zeile.ablehnungsgrund ? ' – ' + zeile.ablehnungsgrund : '');
  }

  async function ladeUebersicht() {
    $('status').textContent = t('empfehlung.loading');
    $('status').hidden = false;
    $('retry').hidden = true;
    $('listeWrap').hidden = true;
    try {
      const daten = await api('/api/empfehlungen');
      $('status').hidden = true;
      const zeilen = daten.empfehlungen || [];
      $('leer').hidden = zeilen.length > 0;
      $('listeWrap').hidden = zeilen.length === 0;
      const body = $('rows');
      body.replaceChildren();
      for (const zeile of zeilen) {
        const tr = document.createElement('tr');
        const name = [zeile.marke, zeile.bezeichnung].filter(Boolean).join(' ') + (zeile.lieferanten_artikelnr ? ' (' + zeile.lieferanten_artikelnr + ')' : '');
        // Zurückziehen jederzeit, auch nach der Antwort (30.09.2026); eine schon gesetzte Stufe bleibt.
        const aktion = node('td');
        if (zeile.status !== 'zurueckgezogen') {
          const zurueck = node('button', t('empfehlung.withdraw'), 'secondary');
          zurueck.type = 'button';
          zurueck.addEventListener('click', async () => {
            zurueck.disabled = true;
            try {
              await api('/api/empfehlungen/' + zeile.id + '/zurueckziehen', { method: 'POST' });
              $('sucheStatus').textContent = t('empfehlung.withdraw_done');
              ladeUebersicht();
            } catch (e) {
              $('sucheStatus').textContent = e.message;
              zurueck.disabled = false;
            }
          });
          aktion.append(zurueck);
        }
        tr.append(
          node('td', name),
          node('td', zeile.lagerort.code + ' · ' + zeile.lagerort.name),
          node('td', '−' + zeile.prozent + ' %'),
          node('td', zeile.ab_datum.split('-').reverse().join('.')),
          node('td', statusLabel(zeile)),
          aktion
        );
        body.append(tr);
      }
    } catch (e) {
      $('status').textContent = e.message;
      $('retry').hidden = false;
    }
  }

  function lagerorteFuellen(quellen) {
    if (lagerorte.length) return;
    lagerorte = quellen.filter(l => l.verkauf);
    const auswahl = $('lagerort');
    // „alle" = alle Verkaufsfilialen in einer Aktion (30.09.2026).
    auswahl.add(new Option(t('empfehlung.all_branches'), 'alle'));
    for (const lagerort of lagerorte) auswahl.add(new Option(lagerort.code + ' · ' + lagerort.name, String(lagerort.id)));
  }

  function artikelZelle(marke, bezeichnung, nummer) {
    const zelle = node('td');
    zelle.append(node('strong', [marke, bezeichnung].filter(Boolean).join(' ') || '—'));
    if (nummer) zelle.append(document.createElement('br'), node('span', nummer, 'muted'));
    return zelle;
  }

  async function suchen() {
    const lagerortId = $('lagerort').value;
    if (!lagerortId) { $('sucheStatus').textContent = t('empfehlung.pick_lagerort_first'); return; }
    const q = $('sucheFeld').value.trim();
    $('sucheStatus').textContent = t('bestand.loading');
    try {
      const alleFilialen = lagerortId === 'alle';
      const parameter = new URLSearchParams(alleFilialen ? { alle: 'true', limit: '500' } : { lagerort_id: lagerortId, limit: '500' });
      if (q) parameter.set('q', q);
      const ergebnis = await api('/api/bestand?' + parameter);
      const modelle = new Map();
      for (const z of ergebnis.zeilen) {
        if (!modelle.has(z.artikel_id)) modelle.set(z.artikel_id, z);
      }
      const body = document.createElement('tbody');
      for (const m of modelle.values()) {
        const tr = document.createElement('tr');
        const prozent = document.createElement('select');
        for (const wert of [30, 50, 70]) prozent.add(new Option('−' + wert + ' %', String(wert)));
        const datum = document.createElement('input');
        datum.type = 'date';
        datum.value = heute();
        const knopf = node('button', t('empfehlung.set'));
        knopf.type = 'button';
        knopf.addEventListener('click', async () => {
          knopf.disabled = true;
          knopf.classList.add('is-loading');
          try {
            const antwort = await api('/api/empfehlungen', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                artikel_id: m.artikel_id,
                ...(alleFilialen ? { alle_filialen: true } : { lagerort_id: Number(lagerortId) }),
                prozent: Number(prozent.value),
                ab_datum: datum.value,
              }),
            });
            const artikelName = m.marke + ' ' + m.bezeichnung;
            $('sucheStatus').textContent = alleFilialen
              ? t('empfehlung.set_done_all', { artikel: artikelName, anzahl: antwort.empfehlungen.length })
              : t('empfehlung.set_done', { artikel: artikelName });
            ladeUebersicht();
          } catch (e) {
            $('sucheStatus').textContent = e.message;
          } finally {
            knopf.disabled = false;
            knopf.classList.remove('is-loading');
          }
        });
        const prozentZelle = node('td');
        prozentZelle.append(prozent);
        const datumZelle = node('td');
        datumZelle.append(datum);
        const aktionZelle = node('td');
        aktionZelle.append(knopf);
        tr.append(artikelZelle(m.marke, m.bezeichnung, m.lieferanten_artikelnr), prozentZelle, datumZelle, aktionZelle);
        body.append(tr);
      }
      const table = document.createElement('table');
      const thead = document.createElement('thead');
      const kopf = document.createElement('tr');
      for (const key of ['bestand.table_article', 'empfehlung.table_prozent', 'empfehlung.table_ab', 'empfehlung.table_actions']) kopf.append(node('th', t(key)));
      thead.append(kopf);
      table.append(thead, body);
      $('treffer').replaceChildren(modelle.size ? table : '');
      $('sucheStatus').textContent = modelle.size ? '' : t('reduktion_wahl.pick_none');
    } catch (e) {
      $('sucheStatus').textContent = e.message;
    }
  }

  $('suchen').addEventListener('click', suchen);
  $('sucheFeld').addEventListener('keydown', (ereignis) => { if (ereignis.key === 'Enter') { ereignis.preventDefault(); suchen(); } });
  $('retry').addEventListener('click', ladeUebersicht);

  window.SportfabrikI18n.ready.then(async () => {
    const stammdaten = await api('/api/umlagerung/stammdaten');
    lagerorteFuellen(stammdaten.quellen);
    ladeUebersicht();
  });
})();
