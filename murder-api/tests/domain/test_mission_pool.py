from src.domain.missions import MISSION_KEYS
from src.domain.models import Game, MissionMode, PooledMission
from src.domain.rules import effective_missions


def _game(mode: MissionMode = MissionMode.AUGMENT, pool: tuple[str, ...] = ()) -> Game:
    game = Game(code="ABCD", host_id="h", mission_mode=mode)
    game.mission_pool = [PooledMission(id=str(i), text=t, by="h") for i, t in enumerate(pool)]
    return game


def test_effective_missions_augment_appends_pool_to_catalogue():
    eff = effective_missions(_game(MissionMode.AUGMENT, ("Custom A", "Custom B")))
    assert eff[: len(MISSION_KEYS)] == MISSION_KEYS
    assert eff[-2:] == ("Custom A", "Custom B")


def test_effective_missions_replace_uses_pool_only():
    assert effective_missions(_game(MissionMode.REPLACE, ("Custom A", "Custom B"))) == (
        "Custom A",
        "Custom B",
    )


def test_effective_missions_replace_with_empty_pool_falls_back_to_catalogue():
    assert effective_missions(_game(MissionMode.REPLACE, ())) == MISSION_KEYS


def test_effective_missions_dedups_preserving_order():
    eff = effective_missions(_game(MissionMode.AUGMENT, (MISSION_KEYS[0], "Unique")))
    assert eff.count(MISSION_KEYS[0]) == 1
    assert "Unique" in eff


def test_pool_entries_shaped_like_catalogue_keys_are_never_dealt():
    # Refused at input nowadays; a pool stored before that rule must not leak them either.
    eff = effective_missions(_game(MissionMode.REPLACE, ("core.99", "Chante")))
    assert eff == ("Chante",)
