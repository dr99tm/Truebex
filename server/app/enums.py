"""Enum values a client may send in any case (PF14f).

The app writes many of the contracts' enum values from Unreal FNames
(`FName::ToString`), and a packaged (Shipping or Game) build does not keep an
FName's case (UE 5.7 NameTypes.h: WITH_CASE_PRESERVING_NAME is
WITH_EDITORONLY_DATA): `FName(TEXT("high")).ToString()` answers whichever
spelling the name table registered first, for example "High". The platform
reads such a value without case and stores and answers the contract's own
spelling; anything else is still refused by the caller, naming that spelling.
Telemetry (PF14d) and the analysis kinds (PF11c) follow the same rule.
"""

from collections.abc import Iterable


def canonical(value: object, allowed: Iterable[str]) -> str | None:
    """`value` spelled as in `allowed`, matched without case, or None.

    ASCII case only (the contracts' values are ASCII): `str.lower()` would
    also turn the Kelvin sign into "k". None for anything that is not one of
    the words: None, numbers, booleans, lists, objects, unknown words.
    """
    if not isinstance(value, str) or not value.isascii():
        return None
    low = value.lower()
    return next((word for word in allowed if word.lower() == low), None)
