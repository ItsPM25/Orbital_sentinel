from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Datetimes go out as UTC ISO-8601 with a trailing Z.
UtcDatetime = Annotated[datetime, PlainSerializer(_iso_z, return_type=str)]


class CamelModel(BaseModel):
    """Base for API models: snake_case in Python, camelCase in JSON."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)
