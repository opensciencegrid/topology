import hashlib
import sys


def email_to_id(email):
    email = email.strip().lower()

    email_bytes = email if isinstance(email, bytes) else email.encode()

    return hashlib.sha1(email_bytes).hexdigest()

