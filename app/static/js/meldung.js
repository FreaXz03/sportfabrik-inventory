// Fehler melden und unbekanntes Dokument senden (Punkte 4 und 5, 2026-10-01).
// Beides geht nur auf ausdrücklichen Klick an Fabians Postfach (Server: app/services/mail.py);
// der Dialog zeigt vor dem Senden, was und wohin gesendet wird. Alle Texte über
// SportfabrikI18n (Regel 7). Kein Modulsystem: der Baustein hängt an window.
(function () {
  var MAX_BILDER = 4;
  function t(key, vars) { return window.SportfabrikI18n ? window.SportfabrikI18n.t(key, vars) : key; }

  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text !== undefined && text !== null) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }

  function groesse(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(bytes / 1024)) + ' KB';
  }

  async function status() {
    try {
      var antwort = await fetch('/api/meldungen/status');
      return antwort.ok ? await antwort.json() : null;
    } catch (fehler) { return null; }
  }

  // Gemeinsames Fenster: Kopf, Inhalt, Rückmeldungszeile, Knöpfe. `senden` gibt eine FormData zurück.
  function dialog(titel, bauen, url, sendenText, erfolgText) {
    var d = el('dialog', null, 'settings-dialog');
    var kopf = el('div', null, 'settings-head');
    kopf.append(el('h2', titel));
    var zu = el('button', t('meldung.close'), 'secondary');
    zu.type = 'button';
    kopf.append(zu);
    var form = el('form');
    form.noValidate = true;
    var inhalt = bauen(form);
    var rueck = el('p', '', 'muted');
    rueck.setAttribute('role', 'status');
    rueck.setAttribute('aria-live', 'polite');
    var knoepfe = el('div', null, 'filters');
    var senden = el('button', sendenText);
    senden.type = 'submit';
    var abbrechen = el('button', t('meldung.cancel'), 'secondary');
    abbrechen.type = 'button';
    knoepfe.append(senden, abbrechen);
    form.append(rueck, knoepfe);
    d.append(kopf, form);
    document.body.append(d);
    function schliessen() { d.close(); d.remove(); }
    zu.addEventListener('click', schliessen);
    abbrechen.addEventListener('click', schliessen);
    d.addEventListener('cancel', function () { d.remove(); });
    status().then(function (s) {
      if (s && !s.konfiguriert) { rueck.textContent = t('meldung.not_configured'); senden.disabled = true; }
      if (s && inhalt.empfaenger) inhalt.empfaenger(s.empfaenger);
    });
    form.addEventListener('submit', async function (ereignis) {
      ereignis.preventDefault();
      senden.disabled = true;
      rueck.textContent = t('meldung.sending');
      try {
        var antwort = await fetch(url, { method: 'POST', body: inhalt.daten() });
        var ergebnis = await antwort.json().catch(function () { return {}; });
        if (!antwort.ok) throw new Error(typeof ergebnis.detail === 'string' ? ergebnis.detail : t('common.errors.request_failed'));
        rueck.textContent = erfolgText;
        form.querySelectorAll('input, textarea').forEach(function (f) { f.disabled = true; });
        abbrechen.textContent = t('meldung.close');
      } catch (fehler) {
        rueck.textContent = fehler.message === 'Failed to fetch' ? t('common.connection_lost') : fehler.message;
        senden.disabled = false;
      }
    });
    d.showModal();
    return d;
  }

  function fehlerFenster() {
    return dialog(t('meldung.heading'), function (form) {
      var intro = el('p', t('meldung.intro', { empfaenger: '…' }), 'muted');
      var titel = document.createElement('input');
      titel.type = 'text'; titel.maxLength = 120; titel.required = true; titel.autocomplete = 'off';
      var nachricht = document.createElement('textarea');
      nachricht.rows = 5; nachricht.maxLength = 4000; nachricht.required = true;
      var bilder = document.createElement('input');
      bilder.type = 'file'; bilder.multiple = true; bilder.accept = 'image/png,image/jpeg,image/gif,image/webp';
      var l1 = el('label', t('meldung.title')); l1.append(titel);
      var l2 = el('label', t('meldung.message')); l2.append(nachricht);
      var l3 = el('label', t('meldung.images', { max: MAX_BILDER })); l3.append(bilder);
      form.append(intro, l1, l2, l3, el('p', t('meldung.context'), 'muted'));
      return {
        empfaenger: function (adresse) { intro.textContent = t('meldung.intro', { empfaenger: adresse }); },
        daten: function () {
          var daten = new FormData();
          daten.append('titel', titel.value);
          daten.append('nachricht', nachricht.value);
          daten.append('seite', location.pathname);
          Array.prototype.forEach.call(bilder.files, function (f) { daten.append('bilder', f); });
          return daten;
        }
      };
    }, '/api/fehlermeldung', t('meldung.send'), t('meldung.sent'));
  }

  // Auf der Seite „Beleg hochladen": ein vom System nicht erkanntes Dokument senden.
  function dokumentSenden(datei) {
    return dialog(t('meldung.doc.heading'), function (form) {
      var was = el('p', t('meldung.doc.what', { filename: datei.name, size: groesse(datei.size), empfaenger: '…' }));
      var notiz = document.createElement('textarea');
      notiz.rows = 3; notiz.maxLength = 1000;
      var l = el('label', t('meldung.doc.note')); l.append(notiz);
      form.append(was, l);
      return {
        empfaenger: function (adresse) { was.textContent = t('meldung.doc.what', { filename: datei.name, size: groesse(datei.size), empfaenger: adresse }); },
        daten: function () {
          var daten = new FormData();
          daten.append('file', datei);
          daten.append('notiz', notiz.value);
          return daten;
        }
      };
    }, '/api/dokument-melden', t('meldung.doc.send'), t('meldung.doc.sent'));
  }

  window.SportfabrikMeldung = { dokumentSenden: dokumentSenden };

  // Knopf in der Kopfzeile (jede Seite): session.js baut die Werkzeugleiste nach dem Ereignis.
  document.addEventListener('sportfabrik:me', function () {
    setTimeout(function () {
      var leiste = document.querySelector('.header-tools');
      if (!leiste || leiste.querySelector('.report-button')) return;
      var knopf = el('button', null, 'report-button secondary');
      knopf.type = 'button';
      var symbol = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      symbol.setAttribute('class', 'icon icon-16');
      symbol.setAttribute('aria-hidden', 'true');
      var verweis = document.createElementNS('http://www.w3.org/2000/svg', 'use');
      verweis.setAttribute('href', '/static/img/icons.svg#icon-bug');
      symbol.append(verweis);
      var beschriftung = el('span', null, 'report-label');
      knopf.append(symbol, beschriftung);
      function beschriften() {
        beschriftung.textContent = t('meldung.button');
        knopf.setAttribute('aria-label', t('meldung.button_aria'));
        knopf.title = t('meldung.button');
      }
      beschriften();
      document.addEventListener('sportfabrik:i18n-ready', beschriften);
      knopf.addEventListener('click', fehlerFenster);
      leiste.prepend(knopf);
    }, 0);
  });
})();
