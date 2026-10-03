class VibeError(Exception):
    """Erreur lisible renvoyée telle quelle à l'agent."""


class MissingKey(VibeError):
    pass


class ProviderError(VibeError):
    pass


class BridgeUnavailable(VibeError):
    pass
