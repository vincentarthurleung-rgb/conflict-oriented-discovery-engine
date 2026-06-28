"""Base validator interface."""


class AbstractValidator:
    name: str = "AbstractValidator"

    def can_validate(self, hypothesis: dict) -> bool:
        raise NotImplementedError

    def validate(self, hypothesis: dict) -> dict:
        raise NotImplementedError
