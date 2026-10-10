"""Explicit legal namespaces; listing storage is never rewritten."""
import re
from sqlalchemy import text


def legal_schema(name: str) -> str:
    if not re.fullmatch(r'public|legal_[a-z0-9_]{1,48}', name):
        raise ValueError('Invalid legal corpus schema')
    return name


def legal_sql(statement: str, schema: str):
    namespace = legal_schema(schema)
    return text(re.sub(r'\blegal_(?:documents|chunks)\b', lambda m: namespace+'.'+m[0], statement))
