// Shared helpers for the phone pages (/m): translation, icons, number formats
// for the UI language, and fetch with readable errors.
(function () {
  var LOCALES = { de: 'de-CH', fr: 'fr-CH', en: 'en-GB' };

  function t(key, vars) { return window.SportfabrikI18n ? window.SportfabrikI18n.t(key, vars) : key; }
  function locale() { return LOCALES[window.SportfabrikI18n ? window.SportfabrikI18n.lang : 'de'] || 'de-CH'; }

  function icon(name, cls) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'icon' + (cls ? ' ' + cls : ''));
    svg.setAttribute('aria-hidden', 'true');
    var use = document.createElementNS(ns, 'use');
    use.setAttribute('href', '/static/img/icons.svg#icon-' + name);
    svg.append(use);
    return svg;
  }

  function money(value) {
    if (value === null || value === undefined || value === '') return null;
    return new Intl.NumberFormat(locale(), { style: 'currency', currency: 'CHF' }).format(Number(value));
  }

  function qty(value) {
    var n = Number(value);
    return new Intl.NumberFormat(locale(), { maximumFractionDigits: 2 }).format(Math.abs(n)).replace(/^/, n < 0 ? '−' : '');
  }

  async function fetchJson(url, options) {
    var response;
    try {
      response = await fetch(url, options);
    } catch (e) {
      throw new Error(t('phone.error_offline'));
    }
    if (response.status === 401) {
      location.href = '/login?next=' + encodeURIComponent(location.pathname);
      throw new Error(t('errors.auth.not_logged_in'));
    }
    var data = null;
    try { data = await response.json(); } catch (e) { }
    if (!response.ok) {
      var detail = data && typeof data.detail === 'string' ? data.detail : t('phone.error_generic');
      var error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  window.SFPhone = { t: t, icon: icon, money: money, qty: qty, fetchJson: fetchJson, el: el, locale: locale };
})();
