"""Workflow-specific exceptions."""


class WorkflowError(RuntimeError):
    """Base workflow error."""


class WorkflowConfigurationError(WorkflowError):
    """Raised for an invalid run configuration."""
