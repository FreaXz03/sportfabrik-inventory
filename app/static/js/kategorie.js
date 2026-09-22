// Kassenkategorie von Hand wählen (Phase B, Teilaufgabe B8).
// Läuft nur auf der Artikel-Detailseite; alle Texte über i18n (Regel 7).
(function () {
  const treffer = location.pathname.match(/^\/articles\/(\d+)\/history$/);
  if (!treffer) return;
  const basis = '/api/articles/' + treffer[1];
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  const name = (kategorie) => window.SportfabrikKategorien.name(kategorie);
  let stand = null;
  let kategorien = [];

  // Woher die Kategorie kommt - das entscheidet, wie sehr man ihr trauen
  // darf: die FEDAS-Tabelle kennt erst die bestätigten Codes.
  function herkunft() {
    if (stand.kategorie) {
      if (stand.manuell) return t('kategorie.source_manual');
      return (
        t('kategorie.source_fedas') +
        (stand.fedas_code ? ' · ' + t('kategorie.fedas_code', { code: stand.fedas_code }) : '')
      );
    }
    if (!stand.fedas_code) return t('kategorie.fedas_missing');
    if (!stand.vorschlag) return t('kategorie.fedas_unknown', { code: stand.fedas_code });
    return t('kategorie.fedas_code', { code: stand.fedas_code });
  }

  function zeigen() {
    const wert = $('kategorieWert');
    wert.textContent = stand.kategorie ? name(stand.kategorie) : t('kategorie.none');
    wert.className = stand.kategorie ? '' : 'muted';
    $('kategorieHerkunft').textContent = herkunft();
    window.SportfabrikKategorien.fuellen($('kategorieAuswahl'), kategorien, {
      leerText: t('kategorie.select_none'),
      wert: stand.kategorie ? stand.kategorie.id : null
    });
    $('kategorieBox').hidden = false;
  }

  async function laden() {
    $('kategorieStatus').textContent = t('kategorie.loading');
    try {
      const hole = async (pfad) => {
        const antwort = await fetch(pfad);
        const daten = await antwort.json();
        if (!antwort.ok) {
          throw new Error(typeof daten.detail === 'string' ? daten.detail : t('kategorie.load_error'));
        }
        return daten;
      };
      const [auswahl, aktuell] = await Promise.all([
        hole('/api/kategorien'),
        hole(basis + '/kategorie')
      ]);
      kategorien = auswahl.items || [];
      stand = aktuell;
      $('kategorieStatus').textContent = '';
      zeigen();
    } catch (fehler) {
      $('kategorieStatus').textContent =
        fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
    }
  }

  async function speichern() {
    if (!stand) return;
    const gewaehlt = $('kategorieAuswahl').value;
    $('kategorieSpeichern').disabled = true;
    $('kategorieStatus').textContent = t('kategorie.saving');
    try {
      const antwort = await fetch(basis + '/kategorie', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kategorie_id: gewaehlt ? Number(gewaehlt) : null })
      });
      const ergebnis = await antwort.json();
      if (!antwort.ok) {
        throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('kategorie.load_error'));
      }
      stand = ergebnis;
      zeigen();
      $('kategorieStatus').textContent = stand.kategorie
        ? t('kategorie.saved', { kategorie: name(stand.kategorie) })
        : t('kategorie.cleared');
    } catch (fehler) {
      $('kategorieStatus').textContent =
        fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
    } finally {
      $('kategorieSpeichern').disabled = false;
    }
  }

  $('kategorieSpeichern').addEventListener('click', speichern);
  window.SportfabrikI18n.ready.then(() => {
    laden();
    // Sprachwechsel: die vom Skript erzeugten Texte neu schreiben.
    document.addEventListener('sportfabrik:i18n-ready', () => {
      if (stand) zeigen();
    });
  });
})();
