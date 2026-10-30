"""Real browser receiving-to-reconciliation flow over the isolated TestClient."""
import pytest
from sqlalchemy import select
from urllib.parse import urlsplit
from test_winter_reconciliation import setup_order,size_pdf
from app.core.models import WinterAbgleich,Lagerbewegung


def test_review_confirmation_and_history(welt):
    playwright=pytest.importorskip('playwright.sync_api')
    from playwright.sync_api import expect
    rid=setup_order(welt)
    with playwright.sync_playwright() as p:
        try:browser=p.chromium.launch()
        except playwright.Error:pytest.skip('Chromium unavailable')
        context=browser.new_context(reduced_motion='reduce')
        def serve(route):
            request=route.request;url=urlsplit(request.url)
            assert url.hostname=='testserver'
            response=welt.client.request(request.method,url.path+('?' + url.query if url.query else ''),
                content=request.post_data_buffer,headers={k:v for k,v in request.headers.items() if k not in ('host','cookie','content-length')})
            route.fulfill(status=response.status_code,body=response.content,headers={k:v for k,v in response.headers.items() if k not in ('content-length','content-encoding','transfer-encoding')})
        context.route('**/*',serve);page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://testserver/winter-abgleich?receipt={rid}')
        expect(page.locator('#winterOrder')).to_have_value(str(rid))
        page.locator('#winterFile').set_input_files({'name':'synthetic.pdf','mimeType':'application/pdf','buffer':size_pdf()})
        page.locator('#winterRead').click()
        expect(page.locator('#winterRows tr')).to_have_count(1)
        expect(page.locator('#winterRows')).to_contain_text('23/23.5: 8')
        expect(page.locator('#winterApply')).to_be_disabled()
        page.locator('#winterConfirmed').check()
        expect(page.locator('#winterApply')).to_be_enabled()
        page.once('dialog',lambda d:d.dismiss());page.locator('#winterApply').click()
        with welt.sessions() as s:assert not s.scalars(select(WinterAbgleich)).all()
        page.once('dialog',lambda d:d.accept());page.locator('#winterApply').click()
        expect(page.locator('#winterStatus')).to_contain_text('Abgleich gespeichert')
        with welt.sessions() as s:
            assert len(s.scalars(select(WinterAbgleich)).all())==1
            assert not s.scalars(select(Lagerbewegung)).all()
        page.locator('#winterRead').click()
        expect(page.locator('#winterRows input[type=checkbox]')).to_be_disabled()
        expect(page.locator('#winterHistory details')).to_have_count(1)
        page.goto('http://testserver/wareneingaenge')
        # The synthetic fixture holds one SF1 receipt; only the two active sized lines are listed.
        expect(page.locator('#list section')).to_have_count(1)
        expect(page.locator('#list section').first.locator('tbody tr')).to_have_count(2)
        assert not errors,errors
        browser.close()
