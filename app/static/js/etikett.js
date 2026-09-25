// EAN nachtragen/erzeugen und Etikett drucken (Phase B, Teilaufgabe B7).
// Läuft nur auf der Artikel-Detailseite; alle Texte über i18n (Regel 7).
(function () {
  const treffer = location.pathname.match(/^\/articles\/(\d+)\/history$/);
  if (!treffer) return;
  const variante = treffer[1];
  const basis = '/api/varianten/' + variante;
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const MELDUNG = 'sportfabrikEanMeldung';
  let daten = null;

  function gemerkteMeldung() {
    // Bestätigung aus dem Durchgang vor dem Neuladen (einmalig).
    try {
      const meldung = sessionStorage.getItem(MELDUNG) || '';
      sessionStorage.removeItem(MELDUNG);
      return meldung;
    } catch (fehler) {
      return '';
    }
  }

  function stufenText(stufe) {
    return stufe ? '-' + stufe + '%' : t('etikett.reduction_none');
  }

  function eanZeigen() {
    const box = $('eanValue');
    box.replaceChildren();
    if (!daten.ean) {
      box.textContent = t('etikett.ean_none');
      box.className = 'muted';
      $('eanInput').disabled = false;
      $('saveEan').disabled = false;
      $('generateEan').disabled = false;
      return;
    }
    const art = daten.ean_intern ? t('etikett.ean_internal') : t('etikett.ean_manufacturer');
    box.textContent = t('etikett.ean_label') + ': ' + daten.ean + ' (' + art + ')';
    box.className = '';
    if (!daten.barcode) {
      const hinweis = document.createElement('p');
      hinweis.className = 'muted';
      hinweis.textContent = t('etikett.ean_not_printable');
      box.append(hinweis);
    }
    // Eine bestehende EAN wird nie überschrieben (Regel 4) - die Felder
    // bleiben deshalb gesperrt, statt einen Fehler zu provozieren.
    $('eanInput').disabled = true;
    $('saveEan').disabled = true;
    $('generateEan').disabled = true;
  }

  function rolleZeigen(rolle) {
    // Vorgedruckte Rolle je Reduktion (24.09.2026) - das System druckt die
    // Prozente nicht, es sagt nur, welche Rolle in den Drucker gehört.
    const box = $('etikettRolle');
    box.dataset.farbe = rolle.farbe;
    box.textContent = t('etikett.roll_hint', {
      prozent: rolle.prozent,
      farbe: t('etikett.roll_color.' + rolle.farbe)
    });
  }

  async function rolleNachladen() {
    // Die Zuordnung Reduktion → Rolle kennt nur der Server.
    const stufe = $('etikettReduktion').value;
    try {
      const antwort = await fetch(basis + '/etikett' + (stufe ? '?reduktion=' + stufe : ''));
      if (antwort.ok) rolleZeigen((await antwort.json()).rolle);
    } catch (fehler) {
      // Hinweis bleibt beim alten Stand; gedruckt wird trotzdem richtig.
    }
  }

  function druckParameter() {
    const parameter = new URLSearchParams({
      groesse: $('etikettGroesse').value,
      anzahl: $('etikettAnzahl').value || '1'
    });
    // Ohne Auswahl entscheidet der Server nach Regel 6 (Vorschlag).
    if ($('etikettReduktion').value !== '') parameter.set('reduktion', $('etikettReduktion').value);
    return parameter;
  }

  function auswahlFuellen() {
    const groessen = $('etikettGroesse');
    if (!groessen.options.length) {
      for (const groesse of daten.groessen) groessen.add(new Option(groesse.replace('x', ' × '), groesse));
    }
    // Nur eine Rolle im Laden: dann gibt es nichts zu wählen.
    groessen.closest('label').hidden = daten.groessen.length < 2;
    const reduktion = $('etikettReduktion');
    const gewaehlt = reduktion.value;
    reduktion.replaceChildren(
      new Option(t('etikett.reduction_suggestion', { stufe: stufenText(daten.reduktion) }), '')
    );
    for (const stufe of daten.reduktionsstufen) reduktion.add(new Option(stufenText(stufe), String(stufe)));
    reduktion.value = gewaehlt;
    $('etikettPreview').textContent = t('etikett.preview', {
      jahrgang: daten.jahrgang || t('etikett.year_unknown'),
      lieferant: daten.lieferant
        ? (daten.lieferant_code ? daten.lieferant_code + ' · ' : '') + daten.lieferant
        : t('etikett.supplier_unknown'),
      uvp: daten.uvp ? 'CHF ' + daten.uvp : t('etikett.price_unknown')
    });
    if (reduktion.value === '') rolleZeigen(daten.rolle);
  }

  async function laden() {
    $('eanStatus').textContent = t('etikett.loading');
    try {
      const antwort = await fetch(basis + '/etikett');
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('etikett.load_error'));
      daten = ergebnis;
      $('eanBox').hidden = false;
      $('eanStatus').textContent = gemerkteMeldung();
      eanZeigen();
      auswahlFuellen();
    } catch (fehler) {
      $('eanStatus').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
    }
  }

  async function eanSetzen(koerper) {
    $('generateEan').disabled = true;
    $('saveEan').disabled = true;
    $('eanStatus').textContent = t('etikett.saving');
    try {
      const antwort = await fetch(basis + '/ean', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(koerper)
      });
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('etikett.load_error'));
      $('eanInput').value = '';
      // Die EAN steht auch in der Kopfzeile der Seite (aus der Artikel-
      // Historie) - damit dort nicht weiter „EAN —" steht, wird die Seite neu
      // geladen. Die Bestätigung überlebt das im sessionStorage.
      try {
        sessionStorage.setItem(MELDUNG, t('etikett.saved', { ean: ergebnis.ean }));
      } catch (fehler) {
        // Privates Fenster o. ä.: dann eben ohne Meldung nach dem Neuladen.
      }
      location.reload();
    } catch (fehler) {
      $('eanStatus').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('generateEan').disabled = false;
      $('saveEan').disabled = false;
    }
  }

  $('generateEan').addEventListener('click', () => eanSetzen({ generieren: true }));
  $('saveEan').addEventListener('click', () => eanSetzen({ ean: $('eanInput').value.trim() }));
  $('eanInput').addEventListener('keydown', (ereignis) => {
    if (ereignis.key !== 'Enter') return;
    ereignis.preventDefault();
    eanSetzen({ ean: $('eanInput').value.trim() });
  });
  $('printEtikett').addEventListener('click', () => {
    window.open(basis + '/etikett.pdf?' + druckParameter().toString(), '_blank', 'noopener');
  });
  $('sampleEtikett').addEventListener('click', () => {
    const parameter = druckParameter();
    parameter.set('anzahl', '1');
    parameter.set('muster', 'true');
    window.open(basis + '/etikett.pdf?' + parameter.toString(), '_blank', 'noopener');
  });
  $('etikettReduktion').addEventListener('change', rolleNachladen);
  window.SportfabrikI18n.ready.then(() => {
    laden();
    document.addEventListener('sportfabrik:i18n-ready', () => {
      if (daten) {
        eanZeigen();
        auswahlFuellen();
      }
    });
  });
})();
