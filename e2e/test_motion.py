"""Game-moment animations (#15) in a real browser, and their prefers-reduced-motion switch."""

import re

import pytest
from playwright.sync_api import Browser, Page, expect

pytestmark = pytest.mark.browser

ANIMATION = "e => getComputedStyle(e).animationName"
FLASH = "e => getComputedStyle(e, '::after').animationName"


def _attacked_guest(
    browser: Browser, browser_context_args: dict, base_url: str, motion: str
) -> tuple[Page, Page]:
    """Host + guest in a started 2-player game; the host has claimed, so the guest is attacked."""
    host = browser.new_context(**browser_context_args).new_page()
    guest = browser.new_context(**{**browser_context_args, "reduced_motion": motion}).new_page()

    host.goto(f"{base_url}/")
    host.get_by_placeholder("Ex. Corbeau").fill("Hôte")
    host.get_by_role("button", name="Créer une partie").click()
    host.wait_for_url(re.compile(r"/g/[A-Z0-9]{4}$"))
    code = host.url.rsplit("/", 1)[-1]
    guest.goto(f"{base_url}/")
    guest.get_by_placeholder("Ex. Corbeau").fill("Invité")
    guest.get_by_placeholder("••••").fill(code)
    guest.get_by_role("button", name="Rejoindre").click()
    guest.wait_for_url(f"**/g/{code}")
    host.get_by_role("button", name="Lancer l'opération").click()
    guest.wait_for_url(f"**/g/{code}/play")
    host.wait_for_url(f"**/g/{code}/play")
    host.get_by_role("button", name="J'ai éliminé ma cible").click()
    expect(guest.locator(".card.confirm")).to_be_visible()
    return host, guest


def test_key_moments_are_animated(browser, browser_context_args, base_url):
    host, guest = _attacked_guest(browser, browser_context_args, base_url, "no-preference")

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


def test_reduced_motion_switches_animations_off(browser, browser_context_args, base_url):
    _, guest = _attacked_guest(browser, browser_context_args, base_url, "reduce")
    attacked = guest.locator(".card.confirm")
    expect(attacked).to_have_class(re.compile(r"\banim-attacked\b"))  # same markup...
    assert attacked.evaluate(ANIMATION) == "none"  # ...but nothing moves
    assert attacked.evaluate(FLASH) == "none"  # not even the ::after flash
