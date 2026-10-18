"""Game-moment animations (#15) in a real browser, and their prefers-reduced-motion switch."""

import re

import pytest
from conftest import Agents
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.browser

ANIMATION = "e => getComputedStyle(e).animationName"
FLASH = "e => getComputedStyle(e, '::after').animationName"


def _attacked_guest(agents: Agents, motion: str) -> tuple[Page, Page]:
    """Host + guest in a started 2-player game; the host has claimed, so the guest is attacked."""
    host = agents.new()
    guest = agents.new(reduced_motion=motion)
    agents.start_two_player_game(host, guest)
    host.get_by_role("button", name="J'ai éliminé ma cible").click()
    expect(guest.locator(".card.confirm")).to_be_visible()
    return host, guest


def test_key_moments_are_animated(agents):
    host, guest = _attacked_guest(agents, "no-preference")

    attacked = guest.locator(".card.confirm")
    assert attacked.evaluate(ANIMATION) == "attacked"
    assert attacked.evaluate(FLASH) == "flash"

    guest.get_by_role("button", name="Confirmer").click()
    success = host.locator(".card.result")
    expect(success).to_have_class(re.compile(r"\banim-success\b"))
    assert success.evaluate(ANIMATION) == "success"
    score = host.locator(".hud .stat").nth(1).locator(".val span")
    expect(score).to_have_class(re.compile(r"\banim-bump\b"))
    assert score.evaluate(ANIMATION) == "bump"

    host.get_by_role("button", name="Lancer la prochaine mission").click()
    dossier = host.locator(".dossier")
    expect(dossier).to_have_class(re.compile(r"\banim-deal\b"))
    assert dossier.evaluate(ANIMATION) == "deal"
    assert agents.errors == [], agents.errors


# Freeze the end headline's stamp animation at a given time (ms) and measure how far the page
# then overflows sideways (> 0 = horizontal scroll on a phone).
OVERFLOW_AT = """t => {
  const animation = document.querySelector('h1.anim-stamp').getAnimations()[0];
  animation.pause();
  animation.currentTime = t;
  return document.documentElement.scrollWidth - innerWidth;
}"""


def test_end_headline_stays_within_a_phone_screen(agents):
    host, _ = _attacked_guest(agents, "no-preference")  # 390 px wide, like a phone
    host.get_by_role("button", name="Terminer la partie").click()
    host.get_by_role("button", name="Terminer maintenant").click()
    host.wait_for_url("**/end")
    for t in (0, 364, 520):  # start, overshoot peak (70 %), end
        assert host.evaluate(OVERFLOW_AT, t) <= 0, f"horizontal overflow at {t} ms"


def test_reduced_motion_switches_animations_off(agents):
    _, guest = _attacked_guest(agents, "reduce")
    attacked = guest.locator(".card.confirm")
    expect(attacked).to_have_class(re.compile(r"\banim-attacked\b"))  # same markup...
    assert attacked.evaluate(ANIMATION) == "none"  # ...but nothing moves
    assert attacked.evaluate(FLASH) == "none"  # not even the ::after flash
