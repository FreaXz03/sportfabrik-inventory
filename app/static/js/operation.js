// Wiederholungsschutz (Paket 2, 01.10.2026): jede bewusste Buchung bekommt eine
// Operations-ID (Header X-Operation-Id). Geht die Antwort verloren und der
// Benutzer wiederholt dieselbe Aktion, bleibt die ID gleich - der Server
// liefert dann die gespeicherte Antwort und bucht nichts doppelt. Nach einer
// echten Antwort gilt die nächste Aktion als neu (neue ID), auch derselbe Scan.
// Nur bei Netzwerkfehlern und Serverfehlern (5xx) bleibt die ID bestehen.
(function () {
  var PFAD = /^\/api\/(ausbuchen|korrektur|umlagerung|erfassen)$|^\/api\/wareneingaenge\/\d+\/ankunft$/;
  var offen = {};

  function neueId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return Array.prototype.map.call(bytes, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
  }

  async function senden(url, optionen) {
    var pfad = String(url).split('?')[0];
    if (!optionen || String(optionen.method).toUpperCase() !== 'POST' || !PFAD.test(pfad)) {
      return fetch(url, optionen);
    }
    var schluessel = pfad + '|' + String(optionen.body || '');
    var id = offen[schluessel] || (offen[schluessel] = neueId());
    var kopf = Object.assign({}, optionen.headers, { 'X-Operation-Id': id });
    var antwort = await fetch(url, Object.assign({}, optionen, { headers: kopf }));
    if (antwort.status < 500) delete offen[schluessel];
    return antwort;
  }

  window.SportfabrikOp = { fetch: senden };
})();
