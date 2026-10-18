from src.domain.models import ClaimStatus, Game, GameStatus, Player


def test_new_game_defaults_to_empty_lobby():
    game = Game(code="ABCD", host_id="h")
    assert game.status is GameStatus.LOBBY
    assert game.players == {}
    assert game.claims == {}


def test_enum_values_match_js_strings():
    assert GameStatus.LOBBY.value == "lobby"
    assert GameStatus.RUNNING.value == "running"
    assert GameStatus.ENDED.value == "ended"
    assert ClaimStatus.PENDING.value == "pending"
    assert ClaimStatus.OK.value == "ok"
    assert ClaimStatus.NO.value == "no"


def test_is_time_up_false_when_no_end_at():
    assert Game(code="ABCD", host_id="h").is_time_up(10_000) is False


def test_is_time_up_true_when_now_at_or_after_end_at():
    game = Game(code="ABCD", host_id="h", end_at=5_000)
    assert game.is_time_up(4_999) is False
    assert game.is_time_up(5_000) is True
    assert game.is_time_up(6_000) is True


def test_ranking_orders_by_score_descending():
    game = Game(code="ABCD", host_id="a")
    game.players["a"] = Player(id="a", name="A", score=1)
    game.players["b"] = Player(id="b", name="B", score=3)
    game.players["c"] = Player(id="c", name="C", score=2)
    assert [p.id for p in game.ranking()] == ["b", "c", "a"]


def test_ranking_preserves_insertion_order_on_ties():
    game = Game(code="ABCD", host_id="a")
    game.players["a"] = Player(id="a", name="A", score=5)
    game.players["b"] = Player(id="b", name="B", score=5)
    assert [p.id for p in game.ranking()] == ["a", "b"]
