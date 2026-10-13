"""PF7b: `POST /market/basket`, the site's "Buy this look" basket page's
platform route (not in the contract, like `/market/checkout/{id}`). It names
the lines the app's room themes send and resolves their `default` variant;
the page then prices them through 5.5 and orders them through 5.7.

No credential (the page prices a basket before anyone signs in); rate-limited
per address like the catalogue reads; errors in the shared envelope.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.orm import Session

from ..contract_http import ContractError, enveloped
from ..database import get_db
from ..market.basket import MAX_LINES, describe
from ..market.prices import region_or_invalid
from ..market.schemas import Id32, RegionCode, Sku, VariantId, _Body
from .market import Reads

router = APIRouter(prefix="/market", tags=["market"], dependencies=[enveloped()])


class BasketItemIn(_Body):
    supplier_id: Id32
    sku: Sku
    variant_id: VariantId


class BasketIn(_Body):
    region: RegionCode
    # The 100-line cap answers 413 `too_large` (as 5.5's does), so the route checks it.
    items: Annotated[list[BasketItemIn], Field(max_length=10_000)]


@router.post("/basket", dependencies=[Reads])
def basket_lines(body: BasketIn, db: Session = Depends(get_db)) -> dict:
    if len(body.items) > MAX_LINES:
        raise ContractError("too_large", 413, f"A basket holds at most {MAX_LINES} lines.", {"max_items": MAX_LINES})
    region = region_or_invalid(db, body.region.upper(), where="body")
    return describe(db, region, [i.model_dump() for i in body.items])
