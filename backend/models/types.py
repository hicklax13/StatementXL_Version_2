"""
Database type utilities for cross-database compatibility.

Provides SQLite-compatible versions of PostgreSQL types.
"""
import uuid as uuid_module
from sqlalchemy import TypeDecorator, String, Text


class UUID(TypeDecorator):
    """
    Platform-independent UUID type.
    
    Uses PostgreSQL's UUID type when available, otherwise
    stores as a 36-character string (with dashes).
    """
    
    impl = String(36)
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        if isinstance(value, uuid_module.UUID):
            return str(value)
        return str(uuid_module.UUID(value))
    
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid_module.UUID):
            return value
        return uuid_module.UUID(value)
