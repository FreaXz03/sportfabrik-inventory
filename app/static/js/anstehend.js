// Seite „Anstehend" (Redesign 2026-09-29, Phase 4): dieselbe Liste wie auf der
// Übersicht, aber als eigene Seite. Rechte und Filialbezug wie /api/dashboard.
(function () {
  const $ = (id) => document.getElementById(id);
  const t = (...a) => window.SportfabrikI18n.t(...a);
  let daten = null;

  function zeichnen() {
    if (!daten) return;
    const f = daten.filiale;
    $('ohneFiliale').hidden = !!f;
    $('heuteText').textContent = daten.lagerort ? daten.lagerort.code + ' · ' + daten.lagerort.name : '';
    window.SportfabrikAnstehend.zeichnen(daten, $('anstehend'), $('nichtsAnstehend'));
    $('anstehendPanel').hidden = !f;
  }

  async function laden() {
    $('retry').hidden = true;
    $('status').textContent = t('dashboard.loading');
    try {
      const antwort = await fetch('/api/dashboard');
      const ergebnis = await antwort.json();
      if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('dashboard.load_error'));
      daten = ergebnis;
      zeichnen();
      $('status').textContent = '';
    } catch (fehler) {
      $('status').textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
      $('retry').hidden = false;
    }
  }

  $('retry').addEventListener('click', laden);
  window.SportfabrikI18n.ready.then(() => {
    laden();
    document.addEventListener('sportfabrik:i18n-ready', zeichnen);
  });
})();
