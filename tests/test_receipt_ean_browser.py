"""Optional real Chromium checks, served only through the isolated TestClient.

Install playwright and its Chromium runtime to run; no listening server or real data.
"""
import pytest
from conftest import ANNA
from sqlalchemy import select
from app.core.models import Bestand, Lagerbewegung


@pytest.mark.parametrize('path,mobile', [('/erfassen', False), ('/m/erfassen', True)])
def test_pending_receipt_ui_and_manual_ean_confirmation(welt, path, mobile):
    playwright = pytest.importorskip('playwright.sync_api')
    from playwright.sync_api import expect
    if mobile:
        welt.client.headers['user-agent'] = 'Synthetic Mobile Test Mobi'
    welt.anmelden(ANNA)
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except playwright.Error as exc:
            pytest.skip(f'Chromium unavailable: {type(exc).__name__}')
        device = p.devices['Pixel 7'] if mobile else {'viewport': {'width': 1280, 'height': 900}}
        # Exercise the responsive phone page and real phone session limits.
        # Desktop layout viewport avoids Chromium touch-emulation scroll offsets.
        device = {**device, 'is_mobile': False}
        context = browser.new_context(**device, reduced_motion='reduce')
        errors = []
        def serve(route):
            request = route.request
            from urllib.parse import urlsplit
            url = urlsplit(request.url)
            assert url.hostname == 'testserver'
            response = welt.client.request(request.method, url.path + ('?' + url.query if url.query else ''),
                                           content=request.post_data_buffer,
                                           headers={k: v for k, v in request.headers.items()
                                                    if k not in ('host', 'cookie', 'content-length')})
            headers = {k: v for k, v in response.headers.items()
                       if k not in ('content-length', 'content-encoding', 'transfer-encoding')}
            route.fulfill(status=response.status_code, headers=headers, body=response.content)
        context.route('**/*', serve)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://testserver' + path)
        expect(page.locator('#lagerort option')).not_to_have_count(0)
        for name, ean in [('Known', '5901234123457'), ('Missing', '')]:
            for field, value in {'marke': 'Synthetic', 'bezeichnung': name, 'menge': '1', 'uvp': '10', 'ean': ean}.items():
                page.locator('#' + field).fill(value)
            try:
                page.locator('#add').click(timeout=5000)
            except Exception:
                page.screenshot(path='/tmp/sf-receipt-browser-failure.png', full_page=True)
                raise
        page.locator('#book').click()
        message = page.locator('#notice' if mobile else '#bookStatus')
        expect(message).to_contain_text('Kein Bestand gebucht')
        with welt.sessions() as session:
            assert not session.scalars(select(Lagerbewegung)).all()
        destination = '/m/lieferungen' if mobile else '/wareneingaenge'
        page.locator('a[href="' + destination + '"]').last.click()
        if mobile:
            expect(page.locator('#deliveryList button')).to_have_count(1)
            page.locator('#deliveryList button').click()
            panel = page.locator('#detailView')
            page.locator('#confirm').click()
            expect(page.locator('#detailError')).to_contain_text('Es wurde nichts gebucht')
            expect(panel.locator('input[data-position]').first).to_have_value('1.00')
            # EAN assignment stays a computer feature; simulate a second operator
            # using the same domain service without expanding phone permissions.
            from app.services.ean import setze_ean
            from app.core.models import Variante
            with welt.sessions() as session:
                vid = session.scalar(select(Variante.id).where(Variante.ean.is_(None)))
            assert welt.client.post(f'/api/varianten/{vid}/ean', json={'generieren': True}).status_code == 403
            setze_ean(vid, welt.sessions, generieren=True)
            page.locator('#confirm').click()
            expect(page.locator('#deliveryList button')).to_have_count(0)
            with welt.sessions() as session:
                assert sum(session.scalars(select(Bestand.menge))) == 2
            assert not errors, errors
            browser.close()
            return
        expect(page.locator('#list section')).to_have_count(1)
        panel = page.locator('#list section')
        panel.locator('button').first.click()
        expect(panel).to_contain_text('Es wurde nichts gebucht')
        # Inputs survive rejection, including the chosen partial quantities.
        expect(panel.locator('input[data-position]').first).to_have_value('1')
        link = panel.get_by_role('link', name='EAN ergänzen')
        with context.expect_page() as popup:
            link.click()
        details = popup.value
        details.on('pageerror', lambda error: errors.append(str(error)))
        # The existing EAN tools are in a collapsed disclosure.
        details.locator('#toggleEan').click()
        expect(details.locator('#generateEan')).to_be_enabled()
        details.once('dialog', lambda dialog: dialog.dismiss())
        details.locator('#generateEan').click()
        expect(details.locator('#generateEan')).to_be_enabled()
        details.once('dialog', lambda dialog: dialog.accept())
        details.locator('#generateEan').click()
        expect(details.locator('#eanValue')).to_contain_text('2000')
        page.bring_to_front()
        panel.locator('button').first.click()
        expect(page.locator('#list section')).to_have_count(0)
        with welt.sessions() as session:
            assert sum(session.scalars(select(Bestand.menge))) == 2
        assert not errors, errors
        browser.close()


def test_bulk_eans_confirmation_preserves_receipt_inputs(welt):
    from test_receipt_ean import _manual
    from app.core.models import Variante
    from urllib.parse import urlsplit
    playwright = pytest.importorskip('playwright.sync_api')
    from playwright.sync_api import expect
    _manual(welt)
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except playwright.Error as exc:
            pytest.skip(f'Chromium unavailable: {type(exc).__name__}')
        context = browser.new_context(reduced_motion='reduce')
        def serve(route):
            request = route.request
            url = urlsplit(request.url)
            assert url.hostname == 'testserver'
            response = welt.client.request(request.method, url.path + ('?' + url.query if url.query else ''),
                content=request.post_data_buffer, headers={k: v for k, v in request.headers.items()
                if k not in ('host', 'cookie', 'content-length')})
            route.fulfill(status=response.status_code, body=response.content, headers={k: v for k, v in response.headers.items()
                if k not in ('content-length', 'content-encoding', 'transfer-encoding')})
        context.route('**/*', serve)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://testserver/wareneingaenge')
        panel = page.locator('#list section')
        quantities = panel.locator('input[data-position]')
        expect(quantities).to_have_count(2)
        quantities.last.fill('1')
        panel.locator('input[type=date]').fill('2026-10-20')
        generate = panel.get_by_role('button', name='Alle nötigen EANs generieren')
        page.once('dialog', lambda dialog: dialog.dismiss())
        generate.click()
        with welt.sessions() as session:
            assert session.scalar(select(Variante.ean).where(Variante.groesse == 'L')) is None
        page.once('dialog', lambda dialog: dialog.accept())
        generate.click()
        expect(panel.get_by_role('status').first).to_contain_text('1 interne EANs erzeugt')
        expect(generate).to_be_hidden()
        expect(quantities.last).to_have_value('1')
        expect(panel.locator('input[type=date]')).to_have_value('2026-10-20')
        with welt.sessions() as session:
            assert not session.scalars(select(Lagerbewegung)).all()
        panel.get_by_role('button', name='Ankunft bestätigen', exact=True).click()
        expect(page.locator('#status')).to_contain_text('Teillieferung gebucht')
        with welt.sessions() as session:
            assert sum(session.scalars(select(Bestand.menge))) == 3
        assert not errors, errors
        browser.close()
