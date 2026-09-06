// Only known application pages can be destinations after signing in.
function safeLoginRedirect(value, origin) {
  if (typeof value !== 'string' || !value.startsWith('/') ||
      value.startsWith('//') || /[\\\x00-\x20\x7f]/.test(value)) return '/';
  try {
    const url = new URL(value, origin);
    if (url.origin !== origin ||
        !/^(?:\/|\/articles|\/invoices|\/preview|\/invoices\/\d+|\/articles\/\d+\/history)$/.test(url.pathname)) return '/';
    return url.pathname + url.search + url.hash;
  } catch (_) {
    return '/';
  }
}
