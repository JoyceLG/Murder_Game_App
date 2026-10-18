import pytest

from src.domain.missions import CATALOGUE_SIZE, MISSION_KEYS, is_catalogue_key


def test_catalogue_has_the_thirty_ported_missions():
    # The JS source held 30 missions (the roadmap's "45" was inaccurate).
    assert len(MISSION_KEYS) == CATALOGUE_SIZE == 30


def test_catalogue_keys_are_unique_and_numbered():
    assert len(set(MISSION_KEYS)) == len(MISSION_KEYS)
    assert MISSION_KEYS[0] == "core.01"
    assert MISSION_KEYS[-1] == "core.30"


def test_every_catalogue_key_is_recognized():
    assert all(is_catalogue_key(key) for key in MISSION_KEYS)


@pytest.mark.parametrize("value", ["core.7", "core.999", " core.12 "])
def test_anything_shaped_like_a_key_is_reserved(value):
    assert is_catalogue_key(value)


@pytest.mark.parametrize(
    "value",
    [
        "Fais rire ta cible",
        "core.",
        "core.1a",
        "Core.01",
        "score.01",
        "core.01 et un selfie",
        "mission.core.01",
    ],
)
def test_custom_texts_are_not_keys(value):
    assert not is_catalogue_key(value)
