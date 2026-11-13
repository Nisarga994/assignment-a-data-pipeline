import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def normalize_header(value):
    """Normalize CSV headers for matching."""
    value = str(value or "").strip().lower()
    return re.sub(r"[_\s]+", " ", value)


def normalize_phone(value):
    """Convert a valid Indian phone number to +91XXXXXXXXXX."""
    digits = re.sub(r"\D", "", str(value or ""))

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 10 or digits[0] not in "6789":
        raise ValueError("invalid_phone")

    return "+91" + digits


def parse_date(value):
    """Parse supported date formats using day-first interpretation."""
    value = str(value or "").strip()

    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d-%b-%Y",
    )

    for date_format in formats:
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue

    raise ValueError("invalid_date")


def parse_decimal(value):
    """Parse an amount with optional Indian currency prefixes."""
    value = str(value or "").strip()

    value = re.sub(
        r"^(₹|rs\.?|inr)\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = value.replace(",", "")

    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid_decimal")

    if not amount.is_finite() or amount < 0:
        raise ValueError("invalid_decimal")

    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_enum(value, allowed_values):
    """Match enum values without case sensitivity."""
    value = str(value or "").strip().lower()
    allowed = [item.lower() for item in allowed_values]

    if value not in allowed:
        raise ValueError("invalid_enum")

    return value


def mask_phone(phone):
    """Mask a canonical Indian phone number for reports."""
    digits = re.sub(r"\D", "", str(phone))
    return "+91******" + digits[-4:]



import os
import base64
import hashlib
import hmac
from cryptography.fernet import Fernet


def get_secret_key():
    """Load the persistent encryption key from an environment variable."""
    key = os.environ.get("LEDGER_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError(
            "Set the LEDGER_ENCRYPTION_KEY environment variable first."
        )

    return key.encode("utf-8")


def get_fernet():
    """Create the encryption helper."""
    key = get_secret_key()
    return Fernet(key)


def encrypt_value(value):
    """Encrypt a PII value before storing it."""
    return get_fernet().encrypt(
        str(value).encode("utf-8")
    ).decode("utf-8")


def decrypt_value(value):
    """Decrypt a previously encrypted value."""
    return get_fernet().decrypt(
        value.encode("utf-8")
    ).decode("utf-8")


def hash_phone(phone):
    """Create a stable keyed hash for matching phone numbers."""
    key = get_secret_key()

    return hmac.new(
        key,
        phone.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_encryption_key():
    """Generate a Fernet-compatible encryption key."""
    return Fernet.generate_key().decode("utf-8")