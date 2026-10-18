"""Default mission catalogue, as translation keys.

The server deals *keys* for catalogue missions (`core.01` … `core.30`) and each client renders
them in its own language (front: `public/i18n/<lang>.json`, section `missions.core`). Custom
missions from the per-game pool are dealt as the literal text their author typed.

The 30 missions were ported from legacy-js/src/game.js (MISSIONS); their French wording now
lives in fr.json under the same numbers.
"""

from __future__ import annotations

import re

CATALOGUE_SIZE = 30

MISSION_KEYS: tuple[str, ...] = tuple(f"core.{n:02d}" for n in range(1, CATALOGUE_SIZE + 1))

# Anything shaped like a catalogue key is reserved: a custom mission must not look like one,
# or clients would translate it (or show a missing key) instead of displaying it as typed.
# Exact match with ASCII digits only ([0-9], not \d which also matches other scripts' digits):
# the front applies the very same rule (murder-front/src/app/core/missions.ts), character for
# character, so both sides always agree on what is a key.
_CATALOGUE_KEY = re.compile(r"core\.[0-9]+")


def is_catalogue_key(mission: str) -> bool:
    """True for a value clients must translate, False for a literal custom mission text."""
    return _CATALOGUE_KEY.fullmatch(mission) is not None
