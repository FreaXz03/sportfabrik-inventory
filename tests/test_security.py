from app.security import hash_password, verify_password


def test_round_trip():
    stored = hash_password("geheim123")
    assert verify_password("geheim123", stored)


def test_wrong_password_rejected():
    stored = hash_password("geheim123")
    assert not verify_password("falsch", stored)


def test_hashes_are_salted_differently():
    assert hash_password("geheim123") != hash_password("geheim123")


def test_malformed_stored_hash_rejected():
    assert not verify_password("geheim123", "das-ist-kein-hash")
    assert not verify_password("geheim123", "")


def test_unknown_algorithm_rejected():
    assert not verify_password("geheim123", "md5$1$aa$bb")
