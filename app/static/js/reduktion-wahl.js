// Manuelle Reduktion (24.09.2026): Knöpfe „Empfehlung · −30 % · −50 % · −70 %"
// für ein Modell in einer Filiale. Genutzt in den Artikeldetails und auf der
// Seite Runterschreiben. Ob jemand darf, prüft der Server (Regel 9).
(function () {
  const t = (...a) => window.SportfabrikI18n.t(...a);

  // Kurzer Text für eine Stufe, z. B. „−50 % (von Hand)" oder „keine".
  function text(stand) {
    if (!stand) return '—';
    const wert = stand.wirksam ? '−' + stand.wirksam + ' %' : t('reduktion_wahl.none');
    return stand.manuell ? wert + ' ' + t('reduktion_wahl.manual_marker') : wert;
  }

  // Knopfleiste; `onChange(neuerStand)` nach erfolgreichem Speichern.
  function knoepfe(variantenId, lagerortId, stand, onChange, meldung) {
    const leiste = document.createElement('div');
    leiste.className = 'reduktion-wahl';
    leiste.setAttribute('role', 'group');
    leiste.setAttribute('aria-label', t('reduktion_wahl.group_aria'));
    const wahl = [[null, t('reduktion_wahl.recommendation', { stufe: stand.empfehlung ? '−' + stand.empfehlung + ' %' : t('reduktion_wahl.none') })], [30, '−30 %'], [50, '−50 %'], [70, '−70 %']];
    for (const [prozent, beschriftung] of wahl) {
      const knopf = document.createElement('button');
      knopf.type = 'button';
      knopf.textContent = beschriftung;
      const aktiv = prozent === null ? stand.manuell === null : stand.manuell === prozent;
      knopf.className = aktiv ? '' : 'secondary';
      knopf.setAttribute('aria-pressed', String(aktiv));
      knopf.addEventListener('click', async () => {
        if (aktiv) return;
        for (const k of leiste.querySelectorAll('button')) k.disabled = true;
        try {
          const antwort = prozent === null
            ? await fetch('/api/reduktion/manuell?' + new URLSearchParams({ varianten_id: variantenId, lagerort_id: lagerortId }), { method: 'DELETE' })
            : await fetch('/api/reduktion/manuell', {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ varianten_id: variantenId, lagerort_id: lagerortId, prozent })
            });
          const daten = await antwort.json().catch(() => ({}));
          if (!antwort.ok) throw new Error(typeof daten.detail === 'string' ? daten.detail : t('reduktion_wahl.save_error'));
          onChange(daten);
        } catch (fehler) {
          if (meldung) meldung.textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
          for (const k of leiste.querySelectorAll('button')) k.disabled = false;
        }
      });
      leiste.append(knopf);
    }
    return leiste;
  }

  window.SportfabrikReduktion = { text, knoepfe };
})();
