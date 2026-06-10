from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field
from datetime import datetime


class Emision(BaseModel):
    type: Literal["emision"]
    from_: str = Field(alias="from")
    to: str
    tokens: int = Field(gt=0)
    motivo: str
    pelicula: str
    timestamp: datetime


class Transferencia(BaseModel):
    type: Literal["transferencia"]
    from_: str = Field(alias="from")
    to: str
    tokens: int = Field(gt=0)
    timestamp: datetime


class Canje(BaseModel):
    type: Literal["canje"]
    from_: str = Field(alias="from")
    to: str
    tokens: int = Field(gt=0)
    beneficio: str
    timestamp: datetime


class AutorizarEmisor(BaseModel):
    type: Literal["autorizar_emisor"]
    solicitante: str
    aprobado_por: list[str]
    timestamp: datetime


Transaccion = Annotated[
    Union[Emision, Transferencia, Canje, AutorizarEmisor],
    Field(discriminator="type"),
]
