// Phone camera scanner. Uses the browser's own barcode reader where there is
// one (Android Chrome), otherwise the bundled ZXing library (iPhone). A code
// counts only after two identical reads with a valid check digit; the camera
// stops at the first accepted code, so one scan can never become two.
(function () {
  var P = window.SFPhone;
  var t = P.t;
  var ZXING_SRC = '/static/vendor/zxing/zxing-library-0.21.3.min.js';
  var NATIVE_FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'];
  var zxingLoading = null;

  function loadZxing() {
    if (window.ZXing) return Promise.resolve(window.ZXing);
    if (!zxingLoading) {
      zxingLoading = new Promise(function (resolve, reject) {
        var script = document.createElement('script');
        script.src = ZXING_SRC;
        script.onload = function () { resolve(window.ZXing); };
        script.onerror = function () { zxingLoading = null; reject(new Error(t('phone.scan_error_generic'))); };
        document.head.append(script);
      });
    }
    return zxingLoading;
  }

  // EAN-8, UPC-A (12) and EAN-13 carry a check digit; other codes are taken as read.
  function normalize(raw) {
    var code = String(raw || '').trim();
    if (!/^\d+$/.test(code)) return code || null;
    if (code.length === 12) code = '0' + code;
    if (code.length !== 8 && code.length !== 13) return code;
    var digits = code.split('').map(Number);
    var check = digits.pop();
    var sum = 0;
    digits.reverse().forEach(function (d, i) { sum += d * (i % 2 === 0 ? 3 : 1); });
    return (10 - (sum % 10)) % 10 === check ? code : null;
  }

  async function nativeDetector() {
    if (!('BarcodeDetector' in window)) return null;
    try {
      var supported = await window.BarcodeDetector.getSupportedFormats();
      var formats = NATIVE_FORMATS.filter(function (f) { return supported.indexOf(f) !== -1; });
      if (formats.indexOf('ean_13') === -1) return null;
      var detector = new window.BarcodeDetector({ formats: formats });
      return async function (video) {
        var found = await detector.detect(video);
        return found.length ? found[0].rawValue : null;
      };
    } catch (e) {
      return null;
    }
  }

  async function zxingDetector() {
    var Z = await loadZxing();
    var reader = new Z.MultiFormatReader();
    var hints = new Map();
    hints.set(Z.DecodeHintType.POSSIBLE_FORMATS, [
      Z.BarcodeFormat.EAN_13, Z.BarcodeFormat.EAN_8, Z.BarcodeFormat.UPC_A,
      Z.BarcodeFormat.UPC_E, Z.BarcodeFormat.CODE_128
    ]);
    hints.set(Z.DecodeHintType.TRY_HARDER, true);
    reader.setHints(hints);
    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d', { willReadFrequently: true });
    return async function (video) {
      var w = video.videoWidth, h = video.videoHeight;
      if (!w || !h) return null;
      // Only the band behind the frame, scaled down: faster and fewer misreads.
      var cropW = Math.round(w * 0.9), cropH = Math.round(h * 0.45);
      var scale = Math.min(1, 960 / cropW);
      canvas.width = Math.round(cropW * scale);
      canvas.height = Math.round(cropH * scale);
      ctx.drawImage(video, (w - cropW) / 2, (h - cropH) / 2, cropW, cropH, 0, 0, canvas.width, canvas.height);
      try {
        var bitmap = new Z.BinaryBitmap(new Z.HybridBinarizer(new Z.HTMLCanvasElementLuminanceSource(canvas)));
        return reader.decodeWithState(bitmap).getText();
      } catch (e) {
        return null;
      }
    };
  }

  function cameraError(error) {
    if (!window.isSecureContext) return t('phone.scan_error_https');
    var name = error && error.name;
    if (name === 'NotAllowedError' || name === 'SecurityError') return t('phone.scan_error_denied');
    if (name === 'NotFoundError' || name === 'OverconstrainedError') return t('phone.scan_error_no_camera');
    if (name === 'NotReadableError') return t('phone.scan_error_busy');
    return t('phone.scan_error_generic');
  }

  function buildOverlay() {
    var overlay = P.el('div', 'm-scanner');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', t('phone.scan_title'));
    var video = P.el('video');
    video.setAttribute('playsinline', '');
    video.setAttribute('autoplay', '');
    video.muted = true;
    var frame = P.el('div', 'm-scanner-frame');
    var hint = P.el('p', 'm-scanner-hint', t('phone.scan_hint'));
    hint.setAttribute('role', 'status');
    hint.setAttribute('aria-live', 'polite');
    var cancel = P.el('button', 'secondary large m-scanner-cancel', t('phone.scan_cancel'));
    cancel.type = 'button';
    overlay.append(video, frame, hint, cancel);
    return { overlay: overlay, video: video, hint: hint, cancel: cancel };
  }

  // Opens the camera; resolves with the code, or null when cancelled.
  function scan() {
    return new Promise(function (resolve) {
      var ui = buildOverlay();
      var stream = null;
      var done = false;
      var last = null;
      var timer = null;
      document.body.append(ui.overlay);
      document.body.classList.add('m-scanning');

      function finish(code) {
        if (done) return;
        done = true;
        clearTimeout(timer);
        if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
        document.removeEventListener('visibilitychange', onHidden);
        document.removeEventListener('keydown', onKey);
        ui.overlay.remove();
        document.body.classList.remove('m-scanning');
        if (code && navigator.vibrate) navigator.vibrate(60);
        resolve(code || null);
      }
      function onHidden() { if (document.hidden) finish(null); }
      function onKey(event) { if (event.key === 'Escape') finish(null); }
      ui.cancel.addEventListener('click', function () { finish(null); });
      document.addEventListener('visibilitychange', onHidden);
      document.addEventListener('keydown', onKey);
      ui.cancel.focus();

      (async function () {
        try {
          if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error('no-media');
          stream = await navigator.mediaDevices.getUserMedia({
            audio: false,
            video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }
          });
          if (done) { stream.getTracks().forEach(function (track) { track.stop(); }); return; }
          ui.video.srcObject = stream;
          await ui.video.play();
          var detect = (await nativeDetector()) || (await zxingDetector());
          (async function loop() {
            if (done) return;
            var raw = null;
            try { raw = await detect(ui.video); } catch (e) { raw = null; }
            var code = raw ? normalize(raw) : null;
            if (code && code === last) { finish(code); return; }
            last = code;
            timer = setTimeout(loop, 120);
          })();
        } catch (error) {
          ui.hint.textContent = cameraError(error);
          ui.overlay.classList.add('has-error');
        }
      })();
    });
  }

  window.SFPhone.scan = scan;
  window.SFPhone.normalizeCode = normalize;
})();
