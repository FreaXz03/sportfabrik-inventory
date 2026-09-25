// Hauptnavigation - an einer Stelle statt in jeder Seite (23.09.2026).
// Gruppiert, markiert die aktive Seite und klappt auf schmalen Bildschirmen
// in ein Menü zusammen. Alle Texte über window.SportfabrikI18n.t() (Regel 7).
(function () {
  var nav = document.querySelector('header nav');
  if (!nav || !window.SportfabrikI18n) return;
  var t = function (key) { return window.SportfabrikI18n.t(key); };

  // `nur` = Rollen, die den Eintrag sehen (Regel 9: Belege hochladen nur
  // Filialleiter und Zentrale). Ohne `nur` sehen ihn alle.
  var EINTRAEGE = [
    { href: '/', key: 'nav.overview', genau: true },
    { href: '/bestand', key: 'nav.bestand' },
    {
      gruppe: 'nav.group_ware', eintraege: [
        { href: '/erfassen', key: 'nav.erfassen', info: 'nav.info.erfassen' },
        { href: '/wareneingaenge', key: 'nav.wareneingaenge', info: 'nav.info.wareneingaenge' },
        { href: '/umlagern', key: 'nav.umlagern', info: 'nav.info.umlagern', nur: ['chef', 'admin'] },
        { href: '/ausbuchen', key: 'nav.ausbuchen', info: 'nav.info.ausbuchen', nur: ['chef', 'admin'] },
        { href: '/runterschreiben', key: 'nav.runterschreiben', info: 'nav.info.runterschreiben' }
      ]
    },
    { href: '/articles', key: 'nav.articles' },
    { href: '/statistiken', key: 'nav.statistiken', nur: ['chef', 'admin'] },
    { href: '/konten', key: 'nav.konten', nur: ['admin'] },
    {
      gruppe: 'nav.group_belege', eintraege: [
        { href: '/invoices', key: 'nav.invoices', info: 'nav.info.invoices' },
        { href: '/preview', key: 'nav.upload', info: 'nav.info.upload', nur: ['chef', 'admin'] }
      ]
    }
  ];

  var rolle = null;
  var offen = null;
  var bereit = false;

  function aktiv(eintrag) {
    var pfad = location.pathname.replace(/\/$/, '') || '/';
    if (eintrag.genau) return pfad === eintrag.href;
    return pfad === eintrag.href || pfad.indexOf(eintrag.href + '/') === 0;
  }

  function sichtbar(eintrag) {
    return !eintrag.nur || (rolle !== null && eintrag.nur.indexOf(rolle) !== -1);
  }

  function link(eintrag, mitInfo) {
    var a = document.createElement('a');
    a.href = eintrag.href;
    if (aktiv(eintrag)) a.setAttribute('aria-current', 'page');
    if (mitInfo && eintrag.info) {
      a.className = 'nav-item';
      var titel = document.createElement('span');
      titel.className = 'nav-item-title';
      titel.textContent = t(eintrag.key);
      var info = document.createElement('span');
      info.className = 'nav-item-info';
      info.textContent = t(eintrag.info);
      a.append(titel, info);
    } else {
      a.textContent = t(eintrag.key);
    }
    return a;
  }

  function schliessen() {
    if (!offen) return;
    offen.knopf.setAttribute('aria-expanded', 'false');
    offen.huelle.classList.remove('is-open');
    offen = null;
  }

  function gruppe(eintrag) {
    var eintraege = eintrag.eintraege.filter(sichtbar);
    if (!eintraege.length) return null;
    var huelle = document.createElement('div');
    huelle.className = 'nav-group';
    var knopf = document.createElement('button');
    knopf.type = 'button';
    knopf.className = 'nav-group-toggle';
    knopf.textContent = t(eintrag.gruppe);
    knopf.setAttribute('aria-expanded', 'false');
    if (eintraege.some(aktiv)) knopf.classList.add('is-active');
    var menue = document.createElement('div');
    menue.className = 'nav-menu';
    eintraege.forEach(function (e) { menue.append(link(e, true)); });
    knopf.addEventListener('click', function (ereignis) {
      ereignis.stopPropagation();
      var warOffen = offen && offen.knopf === knopf;
      schliessen();
      if (warOffen) return;
      knopf.setAttribute('aria-expanded', 'true');
      huelle.classList.add('is-open');
      offen = { knopf: knopf, menue: menue, huelle: huelle };
    });
    huelle.append(knopf, menue);
    return huelle;
  }

  function zeichnen() {
    schliessen();
    nav.replaceChildren();
    var liste = document.createElement('div');
    liste.className = 'nav-links';
    liste.id = 'navLinks';
    EINTRAEGE.forEach(function (eintrag) {
      if (eintrag.gruppe) {
        var g = gruppe(eintrag);
        if (g) liste.append(g);
      } else if (sichtbar(eintrag)) {
        liste.append(link(eintrag, false));
      }
    });
    // Auf schmalen Bildschirmen stehen die Gruppen immer offen (CSS) - nur
  // der Knopf „Menü" klappt die ganze Navigation auf.
  // Schmale Bildschirme: ein Knopf klappt die ganze Navigation auf.
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

  document.addEventListener('click', function (ereignis) {
    if (offen && !offen.menue.contains(ereignis.target)) schliessen();
  });
  document.addEventListener('keydown', function (ereignis) {
    if (ereignis.key !== 'Escape' || !offen) return;
    var knopf = offen.knopf;
    schliessen();
    knopf.focus();
  });

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
