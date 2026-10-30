"""Automatic match suggestions for branch size lists (pure function, synthetic names)."""
from decimal import Decimal

from app.services.winter_reconciliation import suggest


def old(*names, blocked=()):
    return {i: dict(id=i, name=n, quantity=Decimal(5), blocked=i in blocked) for i, n in enumerate(names, 1)}


def group(name, target=None):
    return dict(key=name, name=name, target_id=target)


def run(groups, olds):
    suggest(groups, olds)
    return {g['name']: g for g in groups}


def test_exact_name_is_confident():
    g = run([group('Head Edge 7 W', 1)], old('Head Edge 7 W'))['Head Edge 7 W']
    assert g['confidence'] == 'exact' and g['suggested_id'] == 1


def test_similar_name_with_same_numbers_is_high():
    g = run([group('Head Edge 7 W HV R102mm')], old('Head Edge 7 W HV R 102mm'))['Head Edge 7 W HV R102mm']
    assert g['confidence'] == 'high' and g['suggested_id'] == 1 and not g['reasons']


def test_different_model_number_is_only_medium_with_reason():
    g = run([group('McKinley Lomas 2 schwarz')], old('McKinley Lomas 3 schwarz'))['McKinley Lomas 2 schwarz']
    assert g['confidence'] == 'medium' and 'number' in g['reasons']


def test_unrelated_name_has_no_suggestion():
    g = run([group('Giro Moxie Flash')], old('Tecnica Mach 1'))['Giro Moxie Flash']
    assert g['confidence'] == 'none' and g['suggested_id'] is None


def test_each_old_article_is_suggested_only_once():
    result = run([group('Scarpa Rush Polar GTX'), group('Scarpa Rush Polar GTX X')], old('Scarpa Rush Polar GTX'))
    assert sorted(g['suggested_id'] is not None for g in result.values()) == [False, True]


def test_received_articles_are_never_suggested():
    g = run([group('Head Edge 7 W')], old('Head Edge 7 W', blocked=(1,)))['Head Edge 7 W']
    assert g['confidence'] == 'none'


def test_two_equally_similar_candidates_are_flagged_ambiguous():
    g = run([group('Columbia Bugaboot 3 Blac')], old('Columbia Bugaboot 3 Black', 'Columbia Bugaboot 3 Blac k'))['Columbia Bugaboot 3 Blac']
    assert g['confidence'] == 'medium' and 'ambiguous' in g['reasons'] and g['alternatives']
