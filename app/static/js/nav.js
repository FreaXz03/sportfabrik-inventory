// Seitenleiste - an einer Stelle statt in jeder Seite (23.09.2026, als
// Seitenleiste seit 29.09.2026). Gruppiert, markiert die aktive Seite und
// klappt auf schmalen Bildschirmen in ein Menü zusammen. Alle Texte über window.SportfabrikI18n.t() (Regel 7).
// Filterformulare ohne Absenden (Enter lädt sonst die Seite neu) - hier
// statt als onsubmit-Attribut, das die CSP nicht erlaubt (S7).
document.querySelectorAll('form[data-kein-absenden]').forEach(function (form) {
  form.addEventListener('submit', function (event) { event.preventDefault(); });
});

(function () {
  var nav = document.querySelector('header nav');
  if (!nav || !window.SportfabrikI18n) return;
  var t = function (key) { return window.SportfabrikI18n.t(key); };

  // Seitenleiste (Redesign 29.09.2026), Reihenfolge laut docs/redesign-2026-09-29.md.
  // `nur` = Rollen, die den Eintrag sehen (Regel 9: Belege hochladen nur
  // Filialleiter und Zentrale). Ohne `nur` sehen ihn alle. Der Eintrag mit dem
  // `bald: true` = Seite gibt es noch nicht, der Eintrag bleibt unsichtbar. Jeder Eintrag
  // steht in einer Zeile - tests/test_navigation.py liest die Liste.
  var EINTRAEGE = [
    { href: '/', key: 'nav.overview', info: 'nav.info.overview', genau: true },
    { href: '/articles', key: 'nav.articles', info: 'nav.info.articles' },
    {
      gruppe: 'nav.group_bestand', eintraege: [
        { href: '/bestand', key: 'nav.bestand', info: 'nav.info.bestand' },
        { href: '/runterschreiben', key: 'nav.runterschreiben', info: 'nav.info.runterschreiben' }
      ]
    },
    {
      gruppe: 'nav.group_wareneingang', eintraege: [
        { href: '/wareneingaenge', key: 'nav.wareneingaenge', info: 'nav.info.wareneingaenge' },
        { href: '/erfassen', key: 'nav.erfassen', info: 'nav.info.erfassen' }
      ]
    },
    {
      gruppe: 'nav.group_warenausgang', eintraege: [
        { href: '/ausbuchen', key: 'nav.ausbuchen', info: 'nav.info.ausbuchen' }
      ]
    },
    { href: '/umlagern', key: 'nav.umlagern', info: 'nav.info.umlagern', nur: ['chef', 'admin'] },
    {
      gruppe: 'nav.group_belege', eintraege: [
        { href: '/invoices', key: 'nav.invoices', info: 'nav.info.invoices' },
        { href: '/preview', key: 'nav.upload', info: 'nav.info.upload', nur: ['chef', 'admin'] }
      ]
    },
    { href: '/statistiken', key: 'nav.statistiken', info: 'nav.info.statistiken', nur: ['chef', 'admin'] },
    { href: '/anstehend', key: 'nav.anstehend', info: 'nav.info.anstehend' },
    {
      gruppe: 'nav.group_verwaltung', eintraege: [
        { href: '/konten', key: 'nav.konten', info: 'nav.info.konten', nur: ['admin'] },
        { href: '/empfehlungen', key: 'nav.empfehlungen', info: 'nav.info.empfehlungen', nur: ['admin'] }
      ]
    }
  ];

  var rolle = null;
  var bereit = false;
  // Gruppen, die der Nutzer selbst auf- oder zugeklappt hat (überlebt das Neuzeichnen).
  var manuell = {};

  function aktiv(eintrag) {
    var pfad = location.pathname.replace(/\/$/, '') || '/';
    if (eintrag.genau) return pfad === eintrag.href;
    return pfad === eintrag.href || pfad.indexOf(eintrag.href + '/') === 0;
  }

  function sichtbar(eintrag) {
    if (eintrag.bald) return false;
    return !eintrag.nur || (rolle !== null && eintrag.nur.indexOf(rolle) !== -1);
  }

  function link(eintrag) {
    var a = document.createElement('a');
    a.href = eintrag.href;
    a.textContent = t(eintrag.key);
    if (aktiv(eintrag)) a.setAttribute('aria-current', 'page');
    return a;
  }

  // Eine Gruppe steht offen, wenn ihre aktive Seite darin liegt - sonst
  // entscheidet die letzte Wahl des Nutzers.
  function gruppe(eintrag, nummer) {
    var eintraege = eintrag.eintraege.filter(sichtbar);
    if (!eintraege.length) return null;
    var hatAktive = eintraege.some(aktiv);
    var auf = eintrag.gruppe in manuell ? manuell[eintrag.gruppe] : hatAktive;
    var huelle = document.createElement('div');
    huelle.className = 'nav-group' + (auf ? ' is-open' : '');
    var knopf = document.createElement('button');
    knopf.type = 'button';
    knopf.className = 'nav-group-toggle' + (hatAktive ? ' is-active' : '');
    knopf.textContent = t(eintrag.gruppe);
    knopf.id = 'navGruppe' + nummer;
    knopf.setAttribute('aria-expanded', String(auf));
    var menue = document.createElement('div');
    menue.className = 'nav-menu';
    menue.setAttribute('role', 'group');
    menue.setAttribute('aria-labelledby', knopf.id);
    eintraege.forEach(function (e) { menue.append(link(e)); });
    knopf.addEventListener('click', function () {
      var jetztAuf = huelle.classList.toggle('is-open');
      knopf.setAttribute('aria-expanded', String(jetztAuf));
      manuell[eintrag.gruppe] = jetztAuf;
    });
    huelle.append(knopf, menue);
    return huelle;
  }

  // Funktionssuche (Redesign 29.09.2026, Phase 5): oben im Inhalt, findet nur
  // Seiten, die der Nutzer laut Rolle sehen darf (sichtbar()). Sie öffnet nur
  // Links - die Rechte prüft weiterhin der Server je Seite (Regel 9).
  var suche = null;

  function normal(text) {
    return text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function sucheEintraege() {
    var alle = [];
    EINTRAEGE.forEach(function (eintrag) {
      if (eintrag.gruppe) {
        eintrag.eintraege.filter(sichtbar).forEach(function (e) { alle.push({ e: e, gruppe: eintrag.gruppe }); });
      } else if (sichtbar(eintrag)) {
        alle.push({ e: eintrag, gruppe: null });
      }
    });
    return alle;
  }

  function treffer(frage) {
    var woerter = normal(frage).split(/\s+/).filter(Boolean);
    if (!woerter.length) return [];
    return sucheEintraege().filter(function (x) {
      var text = normal([t(x.e.key), x.gruppe ? t(x.gruppe) : '', t(x.e.info)].join(' '));
      return woerter.every(function (w) { return text.indexOf(w) !== -1; });
    }).slice(0, 8);
  }

  // Glocke / „Alerts" (2026-10-01): ein Klick öffnet ein kleines Fenster mit den
  // ersten fünf Meldungen aus „Anstehend" (Reihenfolge vom Server, dringende zuerst);
  // ein Link führt zur ganzen Liste. Das Zeichen zeigt die Zahl aller Meldungen.
  // Daten von /api/anstehend/anzahl; ohne Meldungen bleibt das Zeichen weg.
  var glocke = null;
  var meldungen = 0;
  var meldungsliste = [];
  var ALERTS_MAX = 5;

  function glockeBeschriften() {
    if (!glocke) return;
    var text = meldungen
      ? window.SportfabrikI18n.t('nav.bell_aria', { anzahl: meldungen })
      : t('nav.bell_none');
    glocke.knopf.setAttribute('aria-label', text);
    glocke.knopf.title = text;
    glocke.zeichen.textContent = meldungen > 99 ? '99+' : String(meldungen);
    glocke.zeichen.hidden = !meldungen;
    glocke.titel.textContent = t('nav.alerts_title');
    glocke.alle.textContent = t('nav.alerts_all');
    alertsZeichnen();
  }

  function alertsZeichnen() {
    if (!glocke) return;
    glocke.liste.replaceChildren();
    meldungsliste.slice(0, ALERTS_MAX).forEach(function (m) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = m.href;
      if (m.dringend) a.className = 'is-urgent';
      var anzahl = document.createElement('span');
      anzahl.className = 'todo-count';
      anzahl.textContent = String(m.anzahl);
      var text = document.createElement('span');
      text.className = 'todo-text';
      text.textContent = window.SportfabrikI18n.t('dashboard.todo_' + m.art, { stufe: m.stufe });
      a.append(anzahl, text);
      li.append(a);
      glocke.liste.append(li);
    });
    glocke.leer.textContent = t('nav.alerts_empty');
    glocke.leer.hidden = meldungsliste.length > 0;
    glocke.alle.hidden = meldungsliste.length === 0;
  }

  function glockeAktualisieren() {
    return fetch('/api/anstehend/anzahl').then(function (r) { return r.ok ? r.json() : null; }).then(function (daten) {
      if (!daten) return;
      meldungen = daten.anzahl;
      meldungsliste = daten.meldungen || [];
      glockeBeschriften();
    }).catch(function () { });
  }

  function glockeBauen() {
    var huelle = document.createElement('div');
    huelle.className = 'bell-wrap';
    var knopf = document.createElement('button');
    knopf.type = 'button';
    knopf.className = 'bell';
    knopf.id = 'alertsKnopf';
    knopf.setAttribute('aria-expanded', 'false');
    knopf.setAttribute('aria-controls', 'alertsFenster');
    var svgNs = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(svgNs, 'svg');
    svg.setAttribute('class', 'icon icon-16');
    svg.setAttribute('aria-hidden', 'true');
    var use = document.createElementNS(svgNs, 'use');
    use.setAttribute('href', '/static/img/icons.svg#icon-bell');
    svg.append(use);
    var zeichen = document.createElement('span');
    zeichen.className = 'bell-badge';
    zeichen.setAttribute('aria-hidden', 'true');
    zeichen.hidden = true;
    knopf.append(svg, zeichen);

    var fenster = document.createElement('div');
    fenster.id = 'alertsFenster';
    fenster.className = 'alerts-popup';
    fenster.setAttribute('aria-labelledby', 'alertsTitel');
    fenster.hidden = true;
    var titel = document.createElement('h2');
    titel.id = 'alertsTitel';
    var liste = document.createElement('ul');
    liste.className = 'alerts-list';
    var leer = document.createElement('p');
    leer.className = 'muted';
    leer.setAttribute('role', 'status');
    var alle = document.createElement('a');
    alle.className = 'alerts-all';
    alle.href = '/anstehend';
    fenster.append(titel, liste, leer, alle);

    function schliessen(zurueck) {
      fenster.hidden = true;
      knopf.setAttribute('aria-expanded', 'false');
      if (zurueck) knopf.focus();
    }
    knopf.addEventListener('click', function () {
      if (!fenster.hidden) { schliessen(false); return; }
      fenster.hidden = false;
      knopf.setAttribute('aria-expanded', 'true');
      glockeAktualisieren();
    });
    document.addEventListener('click', function (ereignis) {
      if (!fenster.hidden && !huelle.contains(ereignis.target)) schliessen(false);
    });
    // Tastatur: verlässt der Fokus das Fenster, schliesst es sich.
    huelle.addEventListener('focusout', function (ereignis) {
      if (!fenster.hidden && ereignis.relatedTarget && !huelle.contains(ereignis.relatedTarget)) schliessen(false);
    });
    huelle.addEventListener('keydown', function (ereignis) {
      if (ereignis.key === 'Escape' && !fenster.hidden) schliessen(true);
    });
    huelle.append(knopf, fenster);

    glocke = { knopf: knopf, zeichen: zeichen, titel: titel, liste: liste, leer: leer, alle: alle };
    glockeBeschriften();
    glockeAktualisieren();
    document.addEventListener('visibilitychange', function () { if (!document.hidden) glockeAktualisieren(); });
    return huelle;
  }

  function sucheBauen() {
    var haupt = document.querySelector('main');
    if (!haupt) return null;
    var huelle = document.createElement('div');
    huelle.className = 'topsearch';
    huelle.setAttribute('role', 'search');
    var label = document.createElement('label');
    label.className = 'visually-hidden';
    label.htmlFor = 'navSuche';
    var feld = document.createElement('input');
    feld.type = 'search';
    feld.id = 'navSuche';
    feld.autocomplete = 'off';
    feld.setAttribute('role', 'combobox');
    feld.setAttribute('aria-autocomplete', 'list');
    feld.setAttribute('aria-expanded', 'false');
    feld.setAttribute('aria-controls', 'navSucheListe');
    var liste = document.createElement('ul');
    liste.id = 'navSucheListe';
    liste.className = 'topsearch-list';
    liste.setAttribute('role', 'listbox');
    liste.hidden = true;
    var status = document.createElement('p');
    status.className = 'visually-hidden';
    status.setAttribute('role', 'status');
    var aktuell = -1;

    function optionen() { return liste.querySelectorAll('[role=option]'); }
    function markieren(nummer) {
      var alle = optionen();
      aktuell = alle.length ? (nummer + alle.length) % alle.length : -1;
      alle.forEach(function (o, i) { o.classList.toggle('is-active', i === aktuell); o.setAttribute('aria-selected', String(i === aktuell)); });
      if (aktuell >= 0) feld.setAttribute('aria-activedescendant', alle[aktuell].id);
      else feld.removeAttribute('aria-activedescendant');
    }
    function schliessen() {
      liste.hidden = true;
      feld.setAttribute('aria-expanded', 'false');
      markieren(-1);
    }
    function zeigen() {
      liste.replaceChildren();
      var frage = feld.value.trim();
      if (!frage) { status.textContent = ''; schliessen(); return; }
      var gefunden = treffer(frage);
      function option(href, titel, info) {
        var li = document.createElement('li');
        li.id = 'navSucheTreffer' + liste.children.length;
        li.setAttribute('role', 'option');
        var a = document.createElement('a');
        a.href = href;
        a.tabIndex = -1;
        var name = document.createElement('strong');
        name.textContent = titel;
        var zusatz = document.createElement('span');
        zusatz.textContent = info;
        a.append(name, zusatz);
        li.append(a);
        liste.append(li);
      }
      gefunden.forEach(function (x) {
        option(x.e.href, t(x.e.key), (x.gruppe ? t(x.gruppe) + ' · ' : '') + t(x.e.info));
      });
      // Alles-Finder (2026-10-01): jede Eingabe lässt sich auch als Artikel- oder
      // Belegsuche öffnen; die Seiten filtern selbst und prüfen die Rechte.
      var suchtext = encodeURIComponent(frage);
      var i18n = window.SportfabrikI18n;
      option('/articles?q=' + suchtext, i18n.t('nav.search_in_articles', { text: frage }), i18n.t('nav.search_in_articles_info'));
      option('/invoices?q=' + suchtext, i18n.t('nav.search_in_documents', { text: frage }), i18n.t('nav.search_in_documents_info'));
      status.textContent = i18n.t('nav.search_results', { anzahl: liste.children.length });
      liste.hidden = false;
      feld.setAttribute('aria-expanded', 'true');
      markieren(-1);
    }
    feld.addEventListener('input', zeigen);
    feld.addEventListener('focus', zeigen);
    feld.addEventListener('blur', schliessen);
    // Klick auf einen Treffer darf das Feld nicht vorher verlassen (Safari).
    liste.addEventListener('mousedown', function (ereignis) { ereignis.preventDefault(); });
    feld.addEventListener('keydown', function (ereignis) {
      if (ereignis.key === 'ArrowDown' || ereignis.key === 'ArrowUp') {
        if (liste.hidden) zeigen();
        markieren(aktuell + (ereignis.key === 'ArrowDown' ? 1 : -1));
        ereignis.preventDefault();
      } else if (ereignis.key === 'Enter') {
        var ziel = optionen()[aktuell >= 0 ? aktuell : 0];
        if (ziel) location.href = ziel.querySelector('a').href;
        ereignis.preventDefault();
      } else if (ereignis.key === 'Escape') {
        if (feld.value) feld.value = '';
        schliessen();
      }
    });
    huelle.append(label, feld, liste, status);
    // Zeile oben im Inhalt: Suche links, Glocke rechts (30.09.2026).
    var leiste = document.createElement('div');
    leiste.className = 'topbar';
    leiste.append(huelle, glockeBauen());
    haupt.prepend(leiste);
    return { label: label, feld: feld };
  }

  function sucheBeschriften() {
    if (!suche) suche = sucheBauen();
    if (!suche) return;
    suche.label.textContent = t('nav.search_label');
    suche.feld.placeholder = t('nav.search_placeholder');
    glockeBeschriften();
  }

  function zeichnen() {
    sucheBeschriften();
    nav.replaceChildren();
    var liste = document.createElement('div');
    liste.className = 'nav-links';
    liste.id = 'navLinks';
    EINTRAEGE.forEach(function (eintrag, nummer) {
      if (eintrag.gruppe) {
        var g = gruppe(eintrag, nummer);
        if (g) liste.append(g);
      } else if (sichtbar(eintrag)) {
        liste.append(link(eintrag));
      }
    });
    // Schmale Bildschirme: ein Knopf „Menü" klappt die ganze Navigation auf;
    // die Gruppen stehen dort immer offen (CSS).
    var menueKnopf = document.createElement('button');
    menueKnopf.type = 'button';
    menueKnopf.className = 'nav-burger secondary';
    menueKnopf.textContent = t('nav.menu');
    menueKnopf.setAttribute('aria-controls', 'navLinks');
    menueKnopf.setAttribute('aria-expanded', String(nav.classList.contains('is-open')));
    menueKnopf.addEventListener('click', function () {
      var auf = nav.classList.toggle('is-open');
      menueKnopf.setAttribute('aria-expanded', String(auf));
    });
    nav.append(menueKnopf, liste);
    seitenleisteKnopf();
  }

  // Seitenleiste ein-/ausklappen (30.09.2026, nur Desktop): Drei-Striche-Knopf
  // oben in der Leiste; die Wahl bleibt im Browser (theme-init.js setzt die
  // Klasse vor dem ersten Zeichnen, damit nichts aufblitzt).
  var leistenKnopf = null;

  function seitenleisteKnopf() {
    var kopf = nav.parentElement;
    if (!leistenKnopf) {
      leistenKnopf = document.createElement('button');
      leistenKnopf.type = 'button';
      leistenKnopf.className = 'sidebar-toggle secondary';
      leistenKnopf.setAttribute('aria-controls', 'navLinks');
      var svgNs = 'http://www.w3.org/2000/svg';
      var svg = document.createElementNS(svgNs, 'svg');
      svg.setAttribute('class', 'icon icon-16');
      svg.setAttribute('aria-hidden', 'true');
      var use = document.createElementNS(svgNs, 'use');
      use.setAttribute('href', '/static/img/icons.svg#icon-menu');
      svg.append(use);
      leistenKnopf.append(svg);
      leistenKnopf.addEventListener('click', function () {
        var wurzel = document.documentElement;
        wurzel.classList.add('sidebar-anim');
        setTimeout(function () { wurzel.classList.remove('sidebar-anim'); }, 300);
        var zu = wurzel.classList.toggle('sidebar-collapsed');
        try { localStorage.setItem('sportfabrikSidebar', zu ? 'collapsed' : 'open'); } catch (e) { }
        seitenleisteKnopf();
      });
      kopf.prepend(leistenKnopf);
    }
    var eingeklappt = document.documentElement.classList.contains('sidebar-collapsed');
    var text = t(eingeklappt ? 'nav.sidebar_expand' : 'nav.sidebar_collapse');
    leistenKnopf.setAttribute('aria-label', text);
    leistenKnopf.title = text;
    leistenKnopf.setAttribute('aria-expanded', String(!eingeklappt));
  }

  // session.js meldet die Rolle, sobald /api/me geantwortet hat.
  document.addEventListener('sportfabrik:me', function (ereignis) {
    rolle = ereignis.detail && ereignis.detail.role;
    if (bereit) zeichnen();
  });
  window.SportfabrikI18n.ready.then(function () {
    bereit = true;
    zeichnen();
    document.addEventListener('sportfabrik:i18n-ready', zeichnen);
  });
})();
