"""Esquemas públicos explícitos. Un borrador no puede incluir estados ni IDs administrativos."""
# FLUJO: admin-events.js -> api.js -> events.py; aquí se validan datos y cupos.
from datetime import date, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class TicketZone(BaseModel):
    name: str = Field(min_length=1, max_length=75)
    price: int = Field(ge=1, le=100_000_000)
    capacity: int = Field(default=0, ge=0, le=100_000)
    description: str = Field(default='', max_length=140)

    @field_validator('name', 'description')
    @classmethod
    def trim(cls, value: str, info) -> str:
        value = value.strip()
        if info.field_name == 'name' and not value:
            raise ValueError('La zona debe tener un nombre.')
        return value


class EventData(BaseModel):
    title: str = Field(min_length=3, max_length=90)
    category: Literal['Música', 'Teatro', 'Arte', 'Cultural', 'Deportes']
    short: str = Field(min_length=8, max_length=170)
    description: str = Field(min_length=15, max_length=1400)
    date: date
    time: time
    venue: str = Field(min_length=2, max_length=85)
    city: str = Field(min_length=2, max_length=75)
    address: str = Field(default='', max_length=150)
    seating: Literal['General por zonas', 'Asientos numerados'] = 'General por zonas'
    timezone: str = Field(default='America/Bogota', min_length=3, max_length=60)
    ticketTypes: list[TicketZone] = Field(min_length=1, max_length=12)

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError('Selecciona una zona horaria IANA válida.') from exc
        return value

    @field_validator('title', 'short', 'description', 'venue', 'city', 'address')
    @classmethod
    def clean(cls, value: str, info) -> str:
        value = value.strip()
        minimum = {'title': 3, 'short': 8, 'description': 15, 'venue': 2, 'city': 2}.get(info.field_name, 0)
        if len(value) < minimum:
            raise ValueError('El campo no tiene suficiente información.')
        return value


class EventDecision(BaseModel):
    reason: str = Field(default='', max_length=500)
