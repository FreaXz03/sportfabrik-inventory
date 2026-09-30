// Gewähltes Farbschema vor dem ersten Zeichnen setzen, damit die Seite nicht
// aufblitzt. Eigene Datei statt Inline-Skript wegen der CSP (S7).
(function () { try { var t = localStorage.getItem('sportfabrikTheme'); if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t); } catch (e) { } })();
// Eingeklappte Seitenleiste (nav.js) ebenfalls vor dem ersten Zeichnen setzen.
(function () { try { if (localStorage.getItem('sportfabrikSidebar') === 'collapsed') document.documentElement.classList.add('sidebar-collapsed'); } catch (e) { } })();
