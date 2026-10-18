import pytest

from src.application.acknowledge_resolution import AcknowledgeResolution
from src.application.claim_elimination import ClaimElimination
from src.application.confirm_claim import ConfirmClaim
from src.application.end_game import EndGame
from src.application.swap_mission import SwapMission
from src.domain.errors import (
    ClaimAlreadyResolved,
    ClaimAwaitingAck,
    ClaimNotFound,
    ClaimNotResolved,
    GameNotRunning,
    NoTargetAssigned,
    NotTheClaimAttacker,
    NotTheClaimTarget,
    PlayerNotFound,
)
from src.domain.models import ClaimStatus, GameStatus
from tests.application.conftest import make_running
from tests.builders import make_game

# --- ClaimElimination ------------------------------------------------------------------


async def test_claim_elimination_creates_pending_claim_and_publishes(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))  # FirstPicker => h targets p2
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)

    claim = await uc.execute("ABCD", "h")

    assert claim.atk == "h"
    assert claim.target == "p2"
    assert claim.status is ClaimStatus.PENDING
    assert "h" in (await repo.get("ABCD")).claims
    assert len(notifier.published) == 1


async def test_claim_without_target_raises_no_target_assigned(repo, clock, picker, notifier):
    game = make_running(clock, picker)
    game.players["h"].target_id = None
    await repo.save(game)
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)
    with pytest.raises(NoTargetAssigned):
        await uc.execute("ABCD", "h")


async def test_claim_on_non_running_game_raises_game_not_running(repo, clock, notifier):
    await repo.save(make_game(["h", "p2"], code="ABCD", host="h"))  # still in lobby
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)
    with pytest.raises(GameNotRunning):
        await uc.execute("ABCD", "h")


async def test_claim_by_unknown_player_raises_player_not_found(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)
    with pytest.raises(PlayerNotFound):
        await uc.execute("ABCD", "ghost")


async def test_claim_overwrites_previous_for_same_attacker(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    uc = ClaimElimination(repo=repo, clock=clock, notifier=notifier)
    await uc.execute("ABCD", "h")
    clock.advance(5000)
    await uc.execute("ABCD", "h")
    stored = await repo.get("ABCD")
    assert list(stored.claims) == ["h"]
    assert stored.claims["h"].ts == clock.now_ms()


# --- ConfirmClaim (the server-side authority) ------------------------------------------


def _confirm(repo, clock, notifier) -> ConfirmClaim:
    return ConfirmClaim(repo=repo, clock=clock, notifier=notifier)


def _ack(repo, clock, picker, notifier) -> AcknowledgeResolution:
    return AcknowledgeResolution(repo=repo, clock=clock, picker=picker, notifier=notifier)


async def _claimed(repo, clock, picker, notifier, **game_fields):
    """A running game (ring h -> p2 -> p3 -> h) where h has claimed p2."""
    game = make_running(clock, picker)
    for name, value in game_fields.items():
        setattr(game, name, value)
    await repo.save(game)
    await ClaimElimination(repo=repo, clock=clock, notifier=notifier).execute("ABCD", "h")
    return game


async def test_confirmation_scores_now_and_waits_for_the_attacker(repo, clock, picker, notifier):
    game = await _claimed(repo, clock, picker, notifier)

    result = await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)

    h = result.players["h"]
    assert h.score == 1
    assert (h.target_id, h.mission) == ("p2", game.players["h"].mission)  # nothing dealt yet
    assert result.claims["h"].status is ClaimStatus.OK
    stored = await repo.get("ABCD")
    assert stored.players["h"].score == 1
    assert stored.claims["h"].status is ClaimStatus.OK  # persisted through the repository


async def test_refusal_is_recorded_and_waits_for_the_attacker(repo, clock, picker, notifier):
    game = await _claimed(repo, clock, picker, notifier)

    result = await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=False)

    assert result.players["h"].score == 0
    assert result.players["h"].mission == game.players["h"].mission
    assert result.claims["h"].status is ClaimStatus.NO


async def test_a_claim_cannot_be_answered_twice(repo, clock, picker, notifier):
    await _claimed(repo, clock, picker, notifier)
    confirm = _confirm(repo, clock, notifier)
    await confirm.execute("ABCD", "h", "p2", confirmed=True)
    with pytest.raises(ClaimAlreadyResolved):
        await confirm.execute("ABCD", "h", "p2", confirmed=True)
    assert (await repo.get("ABCD")).players["h"].score == 1


async def test_confirm_claim_reaching_score_cap_ends_the_game(repo, clock, picker, notifier):
    await _claimed(repo, clock, picker, notifier, max_score=1)

    result = await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)

    assert result.players["h"].score == 1
    assert result.status is GameStatus.ENDED  # cap reached -> ended in the same response
    assert result.claims == {}  # the end acknowledges every claim by itself
    assert (await repo.get("ABCD")).status is GameStatus.ENDED


async def test_confirm_claim_by_non_target_raises_not_the_claim_target(
    repo, clock, picker, notifier
):
    await _claimed(repo, clock, picker, notifier)
    with pytest.raises(NotTheClaimTarget):
        await _confirm(repo, clock, notifier).execute("ABCD", "h", "p3", confirmed=True)


async def test_confirm_claim_missing_claim_raises_claim_not_found(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    with pytest.raises(ClaimNotFound):
        await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)


async def test_confirm_claim_after_time_up_raises_game_not_running(repo, clock, picker, notifier):
    game = await _claimed(repo, clock, picker, notifier)
    clock.advance(game.end_at - clock.now_ms() + 1)  # game has now expired
    with pytest.raises(GameNotRunning):
        await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)
    assert (await repo.get("ABCD")).players["h"].score == 0  # no scoring after the buzzer


# --- AcknowledgeResolution (the attacker moves on) -------------------------------------


async def test_acknowledging_a_confirmation_deals_next_target_and_mission(
    repo, clock, picker, notifier
):
    game = await _claimed(repo, clock, picker, notifier)
    await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)
    notifier.published.clear()

    result = await _ack(repo, clock, picker, notifier).execute("ABCD", "h", caller_id="h")

    h = result.players["h"]
    assert h.score == 1
    assert h.target_id != "p2"  # moved on from the eliminated target
    assert h.mission != game.players["h"].mission
    assert "h" not in result.claims
    assert len(notifier.published) == 1
    assert "h" not in (await repo.get("ABCD")).claims


async def test_acknowledging_a_refusal_deals_a_new_mission_only(repo, clock, picker, notifier):
    game = await _claimed(repo, clock, picker, notifier)
    await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=False)

    result = await _ack(repo, clock, picker, notifier).execute("ABCD", "h", caller_id="h")

    assert result.players["h"].target_id == "p2"
    assert result.players["h"].mission != game.players["h"].mission
    assert result.players["h"].score == 0
    assert "h" not in result.claims


async def test_only_the_attacker_can_acknowledge(repo, clock, picker, notifier):
    await _claimed(repo, clock, picker, notifier)
    await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)
    with pytest.raises(NotTheClaimAttacker):
        await _ack(repo, clock, picker, notifier).execute("ABCD", "h", caller_id="p2")
    assert (await repo.get("ABCD")).claims["h"].status is ClaimStatus.OK


async def test_a_pending_claim_cannot_be_acknowledged(repo, clock, picker, notifier):
    await _claimed(repo, clock, picker, notifier)
    with pytest.raises(ClaimNotResolved):
        await _ack(repo, clock, picker, notifier).execute("ABCD", "h", caller_id="h")


async def test_acknowledging_without_a_claim_raises_not_found(repo, clock, picker, notifier):
    await repo.save(make_running(clock, picker))
    with pytest.raises(ClaimNotFound):
        await _ack(repo, clock, picker, notifier).execute("ABCD", "h", caller_id="h")


async def test_acknowledging_after_time_up_settles_the_end(repo, clock, picker, notifier):
    game = await _claimed(repo, clock, picker, notifier)
    await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)
    clock.advance(game.end_at - clock.now_ms() + 1)
    notifier.published.clear()

    with pytest.raises(GameNotRunning):
        await _ack(repo, clock, picker, notifier).execute("ABCD", "h", caller_id="h")

    stored = await repo.get("ABCD")
    assert stored.status is GameStatus.ENDED
    assert stored.claims == {}
    assert [g.status for g in notifier.published] == [GameStatus.ENDED]


# --- nothing else until the result is acknowledged -------------------------------------


async def test_cannot_claim_again_before_acknowledging(repo, clock, picker, notifier):
    await _claimed(repo, clock, picker, notifier)
    await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)
    with pytest.raises(ClaimAwaitingAck):
        await ClaimElimination(repo=repo, clock=clock, notifier=notifier).execute("ABCD", "h")


async def test_cannot_swap_mission_before_acknowledging(repo, clock, picker, notifier):
    await _claimed(repo, clock, picker, notifier)
    await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=False)
    swap = SwapMission(repo=repo, clock=clock, picker=picker, notifier=notifier)
    with pytest.raises(ClaimAwaitingAck):
        await swap.execute("ABCD", "h")
    assert (await repo.get("ABCD")).players["h"].score == 0  # no penalty taken


async def test_host_ending_the_game_acknowledges_every_claim(repo, clock, picker, notifier):
    await _claimed(repo, clock, picker, notifier)
    await _confirm(repo, clock, notifier).execute("ABCD", "h", "p2", confirmed=True)

    result = await EndGame(repo=repo, clock=clock, notifier=notifier).execute("ABCD", "h")

    assert result.claims == {}
    assert result.players["h"].score == 1
