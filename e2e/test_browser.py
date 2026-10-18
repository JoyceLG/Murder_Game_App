"""Two agents play a whole game through the real Angular UI (Chromium, French UI)."""

import re

import pytest
from playwright.sync_api import Browser, Page, expect

pytestmark = pytest.mark.browser


def _agent(browser: Browser, browser_context_args: dict, errors: list[str]) -> Page:
    page = browser.new_context(**browser_context_args).new_page()
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    return page


def _score(page: Page):
    return page.locator(".hud .stat").nth(1).locator(".val")


def test_two_agents_play_a_full_game(browser, browser_context_args, base_url):
    errors: list[str] = []
    host = _agent(browser, browser_context_args, errors)
    guest = _agent(browser, browser_context_args, errors)

    # Host creates the game
    host.goto(f"{base_url}/")
    host.get_by_placeholder("Ex. Corbeau").fill("Hôte")
    host.get_by_role("button", name="Créer une partie").click()
    host.wait_for_url(re.compile(r"/g/[A-Z0-9]{4}$"))
    code = host.url.rsplit("/", 1)[-1]

    # Guest joins with the code
    guest.goto(f"{base_url}/")
    guest.get_by_placeholder("Ex. Corbeau").fill("Invité")
    guest.get_by_placeholder("••••").fill(code.lower())
    guest.get_by_role("button", name="Rejoindre").click()
    guest.wait_for_url(f"**/g/{code}")
    expect(host.get_by_text("Agents recrutés — 2")).to_be_visible()

    # Host starts: both are dealt each other (two players)
    host.get_by_role("button", name="Lancer l'opération").click()
    host.wait_for_url(f"**/g/{code}/play")
    guest.wait_for_url(f"**/g/{code}/play")
    expect(host.locator(".dossier .target b")).to_have_text("Invité")
    expect(guest.locator(".dossier .target b")).to_have_text("Hôte")

    # A refresh keeps the guest in the game (stored session + secret)
    guest.reload()
    guest.wait_for_url(f"**/g/{code}/play")
    expect(guest.locator(".dossier .target b")).to_have_text("Hôte")

    # Host claims the kill, the guest confirms it, the host scores
    host.get_by_role("button", name="J'ai éliminé ma cible").click()
    expect(host.get_by_text("En attente de Invité…")).to_be_visible()
    expect(guest.get_by_text("Tentative d'élimination")).to_be_visible()
    guest.get_by_role("button", name="Confirmer").click()
    expect(_score(host)).to_have_text("1")

    # Swapping a mission asks first (it costs a point); cancelling costs nothing
    host.get_by_role("button", name=re.compile("Changer de mission")).click()
    expect(host.get_by_text("Changer de mission te coûte 1 point.")).to_be_visible()
    host.get_by_role("button", name="Annuler").click()
    expect(_score(host)).to_have_text("1")

    # Host ends the game for everyone
    host.get_by_role("button", name="Terminer la partie").click()
    host.get_by_role("button", name="Terminer maintenant").click()
    host.wait_for_url(f"**/g/{code}/end")
    guest.wait_for_url(f"**/g/{code}/end")
    expect(host.get_by_text("Tu remportes l'opération.")).to_be_visible()
    expect(guest.get_by_text("Hôte l'emporte.")).to_be_visible()

    # The guest heads home; the host's final ranking still lists both agents
    guest.get_by_role("button", name="Retour à l'accueil").click()
    guest.wait_for_url("**/home")
    host.reload()
    expect(host.locator(".roster li")).to_have_count(2)

    assert errors == [], errors


def test_unknown_code_is_explained(page: Page, base_url):
    page.goto(f"{base_url}/")
    page.get_by_placeholder("Ex. Corbeau").fill("Perdu")
    page.get_by_placeholder("••••").fill("ZZZZ")
    page.get_by_role("button", name="Rejoindre").click()
    expect(page.locator("#toast")).to_have_text("Aucune partie pour ce code")


def test_english_ui(browser, browser_context_args, base_url):
    page = browser.new_context(**{**browser_context_args, "locale": "en-US"}).new_page()
    page.goto(f"{base_url}/")
    expect(page.get_by_role("button", name="Create a game")).to_be_visible()
    expect(page.locator("html")).to_have_attribute("lang", "en")
