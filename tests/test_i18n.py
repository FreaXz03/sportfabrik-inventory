"""i18n-Grundgerüst (Regel 7): Katalog/translate(), Spracherkennung pro
Request (Konto-Sprache bzw. Accept-Language für /login) und Sprachwahl."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.i18n import DEFAULT_LANGUAGE, LANGUAGES, normalize_language, translate
from app.main import app
from app.core.database import get_session
from app.core.lagerorte import seed_lagerorte
from app.core.models import Base, BenutzerLagerort, Lagerort, User
from app.core.security import hash_password


def test_languages_are_de_fr_en():
    assert LANGUAGES == ("de", "fr", "en")
    assert DEFAULT_LANGUAGE == "de"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_normalize_language_keeps_valid_languages(lang):
    assert normalize_language(lang) == lang


@pytest.mark.parametrize("bad", [None, "", "xx", "DE", "deutsch"])
def test_normalize_language_falls_back_to_default(bad):
    assert normalize_language(bad) == DEFAULT_LANGUAGE


def test_translate_returns_language_specific_text():
    assert translate("common.retry", "de") == "Erneut versuchen"
    assert translate("common.retry", "en") == "Try again"
    assert translate("common.retry", "fr") == "Réessayer"


def test_translate_substitutes_params():
    text = translate("preview.count_shown", "de", shown=3, total=10)
    assert text == "3 von 10 Positionen angezeigt"


def test_translate_falls_back_to_default_language_when_key_missing_elsewhere(monkeypatch):
    # Simuliert einen Katalog-Eintrag, der nur auf Deutsch existiert (z.B. kurz
    # nach dem Hinzufügen eines neuen Keys, bevor FR/EN nachgezogen sind).
    import app.core.i18n as i18n

    i18n._catalog.cache_clear()
    original = i18n._catalog

    def patched(language):
        data = dict(original(language))
        if language != "de":
            data.pop("common.retry", None)
        return data

    monkeypatch.setattr(i18n, "_catalog", patched)
    assert translate("common.retry", "fr") == "Erneut versuchen"


def test_translate_unknown_key_returns_key_itself():
    assert translate("does.not.exist", "de") == "does.not.exist"


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as s:
        seed_lagerorte(s)
        s.flush()
        sf1 = s.scalar(select(Lagerort).where(Lagerort.code == "SF1"))
        mitarbeiter = User(
            kassennummer="910141", name="Anna", role="mitarbeiter", password_hash=None
        )
        chef = User(
            kassennummer="910199",
            name="Chef",
            role="chef",
            password_hash=hash_password("geheim123"),
            language="fr",
        )
        s.add_all([mitarbeiter, chef])
        s.flush()
        s.add(BenutzerLagerort(user_id=mitarbeiter.id, lagerort_id=sf1.id, ist_primaer=True))
        s.add(BenutzerLagerort(user_id=chef.id, lagerort_id=sf1.id, ist_primaer=True))

    def override_get_session():
        with sessions() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def test_new_user_defaults_to_german(client):
    r = client.post("/login", data={"kassennummer": "910141"})
    assert r.status_code == 200
    me = client.get("/api/me").json()
    assert me["language"] == "de"


def test_login_error_honours_accept_language_header_for_anonymous_user(client):
    r = client.post(
        "/login",
        data={"kassennummer": "000000"},
        headers={"Accept-Language": "fr-CH,fr;q=0.9"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == translate("errors.auth.unknown_kassennummer", "fr")


def test_login_error_defaults_to_german_without_header(client):
    r = client.post("/login", data={"kassennummer": "000000"})
    assert r.status_code == 401
    assert r.json()["detail"] == translate("errors.auth.unknown_kassennummer", "de")


def test_login_error_falls_back_to_german_for_unsupported_language(client):
    r = client.post(
        "/login",
        data={"kassennummer": "000000"},
        headers={"Accept-Language": "it-CH,it;q=0.9"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == translate("errors.auth.unknown_kassennummer", "de")


def test_error_message_uses_account_language_once_logged_in(client):
    client.post("/login", data={"kassennummer": "910199", "password": "geheim123"})
    # Filialleiter-Konto mit language="fr": eine 403-Fehlermeldung (z.B. beim
    # Wechsel auf eine nicht zugewiesene Filiale) kommt jetzt auf Französisch.
    r = client.post("/api/active-lagerort", json={"lagerort_id": 999999})
    assert r.status_code == 403
    assert r.json()["detail"] == translate("errors.auth.no_lagerort_access", "fr")


def test_me_reports_account_language(client):
    client.post("/login", data={"kassennummer": "910199", "password": "geheim123"})
    me = client.get("/api/me").json()
    assert me["language"] == "fr"
    assert me["role_label"] == translate("role.chef", "fr")


def test_set_language_persists_and_affects_later_errors(client):
    client.post("/login", data={"kassennummer": "910141"})
    r = client.post("/api/language", json={"language": "en"})
    assert r.status_code == 200
    assert r.json() == {"language": "en"}
    assert client.get("/api/me").json()["language"] == "en"

    r = client.post("/api/active-lagerort", json={"lagerort_id": 999999})
    assert r.status_code == 403
    assert r.json()["detail"] == translate("errors.auth.no_lagerort_access", "en")


def test_set_language_rejects_unsupported_value(client):
    client.post("/login", data={"kassennummer": "910141"})
    r = client.post("/api/language", json={"language": "it"})
    assert r.status_code == 422


def test_set_language_requires_login(client):
    r = client.post("/api/language", json={"language": "en"})
    assert r.status_code == 401
