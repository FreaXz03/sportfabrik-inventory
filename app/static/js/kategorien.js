// Kassenkategorien in einer Auswahlliste (Phase B, Teilaufgabe B8).
// Gemeinsam genutzt von der Artikelseite und der Erfassung, damit
// „Textil · Tennis" überall gleich aussieht. Ohne Modulsystem (kein Build,
// siehe CLAUDE.md „Technik") hängt der Baustein an window.
(function () {
  // Name der Kategorie - nicht übersetzt, er steht exakt so in der Kasse
  // (Regel 7/Regel 8). Velo und Food haben keinen Sportbereich.
  function name(kategorie) {
    if (!kategorie) return '';
    return [kategorie.hauptgruppe, kategorie.sportbereich].filter(Boolean).join(' · ');
  }

  // Füllt ein <select>: leerer Eintrag zuerst, danach die Kategorien nach
  // Hauptgruppe gruppiert - 35 Einträge sind zu viele für eine flache Liste.
  // Im Eintrag steht trotzdem der volle Name: zugeklappt zeigt ein <select>
  // nur den Eintrag, und „Winter" allein gibt es dreimal (Textil, Hartware,
  // Schuhe). `optionen.wert` wählt eine Kategorie vor (Id oder null).
  function fuellen(auswahl, kategorien, optionen) {
    const einstellungen = optionen || {};
    auswahl.replaceChildren();
    auswahl.add(new Option(einstellungen.leerText || '', ''));
    let gruppe = null;
    for (const kategorie of kategorien || []) {
      if (!gruppe || gruppe.label !== kategorie.hauptgruppe) {
        gruppe = document.createElement('optgroup');
        gruppe.label = kategorie.hauptgruppe;
        auswahl.append(gruppe);
      }
      gruppe.append(new Option(name(kategorie), kategorie.id));
    }
    // Unbekannte Id fällt auf den leeren Eintrag zurück.
    auswahl.value = einstellungen.wert ? String(einstellungen.wert) : '';
  }

  window.SportfabrikKategorien = { name: name, fuellen: fuellen };
})();
