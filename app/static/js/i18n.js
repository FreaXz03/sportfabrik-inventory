(function () {
  var STORAGE_KEY = 'sportfabrikLanguage';
  var LANGUAGES = ['de', 'fr', 'en'];
  var catalog = {};
  var currentLang = 'de';

  function storedLanguage() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }
  function storeLanguage(lang) {
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) { }
  }

  function t(key, vars) {
    var text = catalog[key] || key;
    if (vars) {
      Object.keys(vars).forEach(function (k) {
        text = text.split('{' + k + '}').join(vars[k]);
      });
    }
    return text;
  }

  function applyTranslations(root) {
    var scope = root || document;
    scope.querySelectorAll('[data-i18n]').forEach(function (el) {
      var text = t(el.getAttribute('data-i18n'));
      if (el.children.length) {
        var replaced = false;
        for (var i = 0; i < el.childNodes.length; i++) {
          if (el.childNodes[i].nodeType === Node.TEXT_NODE && el.childNodes[i].textContent.trim()) {
            el.childNodes[i].textContent = text;
            replaced = true;
            break;
          }
        }
        if (!replaced) el.insertBefore(document.createTextNode(text), el.firstChild);
      } else {
        el.textContent = text;
      }
    });
    scope.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder')));
    });
    scope.querySelectorAll('[data-i18n-aria-label]').forEach(function (el) {
      el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria-label')));
    });
    scope.querySelectorAll('[data-i18n-title]').forEach(function (el) {
      el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
    });
    if (scope === document) document.documentElement.setAttribute('lang', currentLang);
  }

  function loadCatalog(lang) {
    return fetch('/static/i18n/' + lang + '.json').then(function (r) {
      return r.ok ? r.json() : {};
    }).catch(function () { return {}; });
  }

  function persistToAccount(lang) {
    fetch('/api/language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: lang })
    }).catch(function () { });
  }

  var loading = null;

  function setLanguage(lang, opts) {
    opts = opts || {};
    if (LANGUAGES.indexOf(lang) === -1) lang = 'de';
    var changed = lang !== currentLang;
    // Gleiche Sprache: Katalog nicht erneut holen und kein zweites
    // i18n-ready senden. session.js meldet direkt nach dem Laden die
    // Kontosprache - meist dieselbe, die hier schon aktiv ist. Ohne diese
    // Abkuerzung holte jede Seite ihren Katalog doppelt und ihre Daten
    // (z.B. /api/articles) ein drittes Mal, im Ladennetz spuerbar.
    if (!changed) {
      if (loading) return loading;
      if (Object.keys(catalog).length) return Promise.resolve();
    }
    currentLang = lang;
    storeLanguage(lang);
    loading = loadCatalog(lang).then(function (data) {
      // Ein zwischenzeitlicher Wechsel gewinnt - eine spaet eintreffende
      // Antwort darf den neueren Katalog nicht ueberschreiben.
      if (lang !== currentLang) return;
      loading = null;
      catalog = data;
      applyTranslations();
      if (opts.persist && changed) persistToAccount(lang);
      document.dispatchEvent(new CustomEvent('sportfabrik:i18n-ready', { detail: { lang: lang } }));
    });
    return loading;
  }

  var ready = setLanguage(storedLanguage() || 'de', { persist: false });

  window.SportfabrikI18n = {
    t: t,
    applyTranslations: applyTranslations,
    setLanguage: function (lang) { return setLanguage(lang, { persist: true }); },
    syncFromAccount: function (lang) { return setLanguage(lang, { persist: false }); },
    languages: LANGUAGES,
    get lang() { return currentLang; },
    ready: ready
  };
})();
