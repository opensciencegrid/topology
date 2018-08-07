import hashlib
import sys


def email_to_id(email):
    email = email.strip().lower()

    if sys.version_info[0] >= 3:
        if isinstance(email, str):
            email_bytes = email.encode()
        else:
            email_bytes = email
    else:
        if isinstance(email, unicode):
            email_bytes = email.encode()
        else:
            email_bytes = email

    return hashlib.sha1(email_bytes).hexdigest()

