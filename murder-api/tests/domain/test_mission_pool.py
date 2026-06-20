from src.domain.missions import MISSIONS
from src.domain.models import Game, MissionMode, PooledMission
from src.domain.rules import effective_missions


def _game(mode: MissionMode = MissionMode.AUGMENT, pool: tuple[str, ...] = ()) -> Game:
    game = Game(code="ABCD", host_id="h", mission_mode=mode)
    game.mission_pool = [PooledMission(id=str(i), text=t, by="h") for i, t in enumerate(pool)]
    return game


def test_effective_missions_augment_appends_pool_to_catalogue():
    eff = effective_missions(_game(MissionMode.AUGMENT, ("Custom A", "Custom B")))
    assert eff[: len(MISSIONS)] == MISSIONS
    assert eff[-2:] == ("Custom A", "Custom B")


def test_effective_missions_replace_uses_pool_only():
    assert effective_missions(_game(MissionMode.REPLACE, ("Custom A", "Custom B"))) == (
        "Custom A",
        "Custom B",
    )


def test_effective_missions_replace_with_empty_pool_falls_back_to_catalogue():
    assert effective_missions(_game(MissionMode.REPLACE, ())) == MISSIONS


def test_effective_missions_dedups_preserving_order():
    eff = effective_missions(_game(MissionMode.AUGMENT, (MISSIONS[0], "Unique")))
    assert eff.count(MISSIONS[0]) == 1
    assert "Unique" in eff
