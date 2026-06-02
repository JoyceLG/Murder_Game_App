from src.domain.missions import MISSIONS


def test_missions_catalogue_is_non_empty():
    assert len(MISSIONS) >= 1


def test_missions_are_unique():
    assert len(set(MISSIONS)) == len(MISSIONS)


def test_missions_count_matches_ported_catalogue():
    # The JS source held 30 missions (the roadmap's "45" was inaccurate).
    assert len(MISSIONS) == 30
