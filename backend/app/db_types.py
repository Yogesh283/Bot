"""Column types that PostgreSQL and MySQL can both store."""

from sqlalchemy import JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB

UUID_TYPE = Uuid(as_uuid=True)
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
