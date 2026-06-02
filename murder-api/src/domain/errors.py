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
