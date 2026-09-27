"""Custom exception hierarchy for LegalPilot-VN."""


class LegalPilotException(Exception):
    """Base exception for all LegalPilot-VN errors."""

    pass


class ConfigurationError(LegalPilotException):
    """Raised when configuration files or environment variables are invalid."""

    pass


class SecurityViolationError(LegalPilotException):
    """Raised when a security guardrail or threat model check fails."""

    def __init__(self, message: str, vector_id: int | None = None):
        super().__init__(message)
        self.vector_id = vector_id


class RetrievalError(LegalPilotException):
    """Raised when knowledge retrieval (Neo4j, Qdrant, or Web) fails."""

    pass


class KnowledgeBaseError(RetrievalError):
    """Raised when a graph or vector database operation fails."""

    pass


class AuditorRejectionError(LegalPilotException):
    """Raised when the Claim Auditor rejects a draft after max retry loops."""

    pass


class GateAuthorizationError(LegalPilotException):
    """Raised when an irreversible action is attempted without valid human approval token."""

    pass


class DisambiguationRequired(LegalPilotException):
    """Raised when legal reasoning halts due to missing case facts/parameters."""

    def __init__(self, missing_fields: list[str], prompt: str):
        super().__init__(prompt)
        self.missing_fields = missing_fields
        self.prompt = prompt
