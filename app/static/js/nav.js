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
  // Filialleiter und Zentrale). Ohne `nur` sehen ihn alle. `bald: true` =
  // Seite gibt es noch nicht, der Eintrag bleibt unsichtbar. Jeder Eintrag
  // steht in einer Zeile - tests/test_navigation.py liest die Liste.
  var EINTRAEGE = [
    { href: '/', key: 'nav.overview', genau: true },
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
    { href: '/statistiken', key: 'nav.statistiken', nur: ['chef', 'admin'] },
    { href: '/anstehend', key: 'nav.anstehend' },
    {
      gruppe: 'nav.group_verwaltung', eintraege: [
        { href: '/konten', key: 'nav.konten', nur: ['admin'] },
        { href: '/empfehlungen', key: 'nav.empfehlungen', nur: ['admin'] }
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

  function zeichnen() {
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
