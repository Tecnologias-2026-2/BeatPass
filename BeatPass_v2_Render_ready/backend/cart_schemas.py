"""El cliente envía identificadores y cantidades, jamás precios ni stock."""
# FLUJO: cart.py recibe cantidades del navegador y aquí Pydantic valida los rangos.
from pydantic import BaseModel, Field, ConfigDict

class AddCartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: int = Field(ge=1)
    zone_index: int = Field(ge=0, le=11)
    quantity: int = Field(ge=1, le=10)

class SetCartQuantity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(ge=1, le=10)
