const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const next = safeLoginRedirect(params.get('next'), location.origin);
let awaitingPassword = false;
$('login').addEventListener('submit', async event => {
  event.preventDefault();
  $('submit').disabled = true;
  $('status').className = '';
  $('status').textContent = window.SportfabrikI18n.t(awaitingPassword ? 'login.checking_password' : 'login.checking_kassennummer');
  try {
    const body = new URLSearchParams();
    body.set('kassennummer', $('kassennummer').value.trim());
    if (awaitingPassword) body.set('password', $('password').value);
    const response = await fetch('/login', { method: 'POST', body });
    const result = await response.json();
    if (!response.ok) {
      $('status').className = 'notice error';
      $('status').textContent = typeof result.detail === 'string' ? result.detail : window.SportfabrikI18n.t('login.failed');
      if (awaitingPassword) { $('password').value = ''; $('password').focus(); }
      return;
    }
    if (result.requires_password) {
      awaitingPassword = true;
      $('passwordField').hidden = false;
      $('password').focus();
      $('status').textContent = window.SportfabrikI18n.t('login.enter_password');
      return;
    }
    location.href = next;
  } catch (error) {
    $('status').className = 'notice error';
    $('status').textContent = window.SportfabrikI18n.t('login.connection_lost');
  } finally {
    $('submit').disabled = false;
  }
});
function highlightActiveLang() {
  document.querySelectorAll('#langSwitch .lang-option').forEach(function (button) {
    button.classList.toggle('active', button.dataset.lang === window.SportfabrikI18n.lang);
  });
}
document.querySelectorAll('#langSwitch .lang-option').forEach(function (button) {
  button.addEventListener('click', function () {
    window.SportfabrikI18n.setLanguage(button.dataset.lang).then(highlightActiveLang);
  });
});
document.addEventListener('sportfabrik:i18n-ready', highlightActiveLang);
highlightActiveLang();
