from sqlalchemy.exc import IntegrityError

COMPANY_NAME_UNIQUE = "company_name_lower_uidx"
IDEMPOTENCY_KEY_PK = "idempotency_key_pkey"


def constraint_name(exc: IntegrityError) -> str | None:
    """Violated constraint/index name from the asyncpg error, if any."""
    for source in (exc.orig, getattr(exc.orig, "__cause__", None)):
        name = getattr(source, "constraint_name", None)
        if name:
            return str(name)
    text = str(exc.orig)
    for known in (COMPANY_NAME_UNIQUE, IDEMPOTENCY_KEY_PK):
        if known in text:
            return known
    return None
