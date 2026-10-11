"""422 `validation_failed` in the shape PF6's submit answers it."""

from ..contract_http import ContractError


def invalid(field: str, message: str, **data) -> ContractError:
    return ContractError(
        "validation_failed", 422, f"{field}: {message}",
        {"fields": [{"field": field, "in": "body", "message": message}], **data},
    )
