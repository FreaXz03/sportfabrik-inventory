"""OCR fallback for scanned (image-only) invoice pages.

parser.py calls into this module only when a PDF page has no extractable
text at all - i.e. a paper invoice that arrived stapled inside a delivery
instead of by email and was scanned rather than exported digitally. The
result is shaped exactly like PyMuPDF's page.get_text("words") (a list of
(x0, y0, x1, y1, word, block_no, line_no, word_no) tuples, in PDF point
space), so the existing table-reconstruction logic in parser.py can be
reused unchanged for OCR-derived pages.

OCR is inherently less reliable than a native text layer, so callers are
expected to flag results derived this way for extra human review - see
parser.parse_invoice's ocr_used/ocr_pages fields.
"""
import re

try:
    import pytesseract
    from pytesseract import Output
except ImportError:  # pragma: no cover - exercised only without the dependency
    pytesseract = None
    Output = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - exercised only without the dependency
    Image = None

# Rendering DPI for scanned pages. 300 is the usual sweet spot for OCR
# accuracy on printed (non-handwritten) text without being unreasonably slow.
OCR_DPI = 300
_POINTS_PER_PIXEL = 72 / OCR_DPI

# Table borders and smudges are frequently misread by OCR as stray
# underscores, pipes or similar marks glued to the start/end of a real word.
_NOISE = re.compile(r"^[_|~¦†‡•·=]+|[_|~¦†‡•·=]+$")

_UNAVAILABLE_MESSAGE = (
    "Diese Datei enthält keinen lesbaren Text (vermutlich ein eingescanntes "
    "Blatt). Texterkennung (OCR) ist auf diesem Rechner nicht verfügbar - "
    "bitte Tesseract OCR installieren (siehe SERVER-SETUP.md) oder die "
    "Rechnung digital anfordern."
)


class OcrUnavailableError(Exception):
    """Raised when a page needs OCR but Tesseract/pytesseract/Pillow are missing."""


def _clean_word(text):
    return _NOISE.sub("", text).strip()


def render_upright_image(page, dpi=OCR_DPI):
    """Render a PDF page to an image, auto-correcting sideways/upside-down scans.

    PyMuPDF already applies a page's own /Rotate flag when rendering, which
    covers scans where the scanning software recorded the orientation
    correctly. As a safety net for scans where it didn't (a raw sideways
    image with no rotation flag), Tesseract's orientation detection (OSD) is
    used to correct any rotation that remains.
    """
    pix = page.get_pixmap(dpi=dpi)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    try:
        osd = pytesseract.image_to_osd(image, output_type=Output.DICT)
        rotate = int(osd.get("rotate", 0) or 0)
    except Exception:
        # OSD can fail outright on sparse/low-confidence pages; falling back
        # to whatever orientation PyMuPDF already produced is safer than
        # aborting the whole OCR attempt over an orientation guess.
        rotate = 0
    if rotate:
        image = image.rotate((360 - rotate) % 360, expand=True)
    return image


def _grouped_words(data):
    """Turn Tesseract's per-character-box word list into word tuples whose
    y-coordinates are normalised per detected text line.

    Tesseract's own bounding boxes jitter by a few points from word to word
    on the same visual line (ascenders, descenders, box padding). parser.py's
    row-grouping (lines() in parser.py) expects same-line words to share
    (almost) the same y0, as they do in a native PDF's text layer. Snapping
    every word in a Tesseract line/paragraph/block group to that group's
    shared top/bottom keeps parser.py's logic unchanged for OCR input.
    """
    groups = {}
    entries = []
    for i, raw in enumerate(data["text"]):
        word = _clean_word(raw)
        if not word or not any(c.isalnum() for c in word):
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        left, top = data["left"][i], data["top"][i]
        width, height = data["width"][i], data["height"][i]
        entries.append((key, left, top, width, data["word_num"][i], word))
        lo, hi = groups.get(key, (top, top + height))
        groups[key] = (min(lo, top), max(hi, top + height))

    words = []
    for key, left, top, width, word_num, word in entries:
        y0, y1 = groups[key]
        x0 = left * _POINTS_PER_PIXEL
        x1 = (left + width) * _POINTS_PER_PIXEL
        words.append((x0, y0 * _POINTS_PER_PIXEL, x1, y1 * _POINTS_PER_PIXEL,
                      word, key[0], key[1] * 1000 + key[2], word_num))
    return words


def ocr_page(page, dpi=OCR_DPI):
    """OCR a scanned page.

    Returns a dict with `words` (PyMuPDF word-tuple shape, in PDF points),
    `text` (the full page text, for the invoice-number/stop-marker regexes),
    and `height` (page height in points, for the same fallback bound
    page.rect.height provides for native pages).
    """
    if pytesseract is None or Image is None:
        raise OcrUnavailableError(_UNAVAILABLE_MESSAGE)
    try:
        image = render_upright_image(page, dpi=dpi)
        data = pytesseract.image_to_data(image, output_type=Output.DICT, config="--psm 6")
        text = pytesseract.image_to_string(image, config="--psm 6")
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailableError(_UNAVAILABLE_MESSAGE) from exc

    return dict(words=_grouped_words(data), text=text, height=image.height * _POINTS_PER_PIXEL)
