"""Domain (business-rule) errors. The API layer maps these to HTTP status codes."""


class DomainError(Exception):
    """Base class for all domain errors."""


class GameNotFound(DomainError):
    """No game exists for the given code."""


class GameAlreadyStarted(DomainError):
    """Action requires the lobby state but the game has already started."""


class GameNotRunning(DomainError):
    """Action requires a running game."""


class NotEnoughPlayers(DomainError):
    """A game needs at least two players to start."""


class TooManyPlayers(DomainError):
    """The lobby has reached its player cap; no more players may join."""


class InvalidGameConfig(DomainError):
    """The requested game configuration is not acceptable (e.g. cap below current players)."""


class InvalidMission(DomainError):
    """A custom mission is empty, too long, or the pool is full."""


class MissionNotFound(DomainError):
    """No pooled mission with the given id."""


class NotAllowedToRemoveMission(DomainError):
    """Only the mission's author or the host may remove a pooled mission."""


class PlayerNotFound(DomainError):
    """No such player in this game."""


class NotTheHost(DomainError):
    """Only the host may perform this action (e.g. start the game)."""


class NoTargetAssigned(DomainError):
    """The player has no target yet, so cannot claim an elimination."""


class ClaimNotFound(DomainError):
    """No pending claim for the given attacker."""


class NotTheClaimTarget(DomainError):
    """Only the claim's target may confirm or deny it (server-side authority check)."""
