"""Contract between the API and the front: every mission key the server can deal has a
translation in every UI language, and the front carries no stale catalogue entry."""

import json
from pathlib import Path

import pytest

from src.domain.missions import MISSION_KEYS

I18N = Path(__file__).resolve().parents[2] / "murder-front" / "public" / "i18n"


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_every_catalogue_key_is_translated(lang):
    catalogue = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))["missions"]["core"]
    assert sorted(f"core.{n}" for n in catalogue) == sorted(MISSION_KEYS)
    assert all(text.strip() for text in catalogue.values())


def test_languages_do_not_share_untranslated_texts():
    fr = json.loads((I18N / "fr.json").read_text(encoding="utf-8"))["missions"]["core"]
    en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))["missions"]["core"]
    assert not [n for n in fr if fr[n] == en[n]]
