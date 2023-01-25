from flask import Response
from .common import to_csv, to_json_bytes
from typing import List

def create_accepted_response(data: List, headers, default=None) -> Response:
    """Provides CSV or JSON options for list of list(string)"""

    if not default:
        default = "application/json"

    accepted_response_builders = {
        "text/csv": lambda: Response(to_csv(data), mimetype="text/csv"),
        "application/json": lambda: Response(to_json_bytes(data), mimetype="application/json"),
    }

    requested_types = set(headers.get('Accept', 'default').replace(' ', '').split(","))
    accepted_and_requested = set(accepted_response_builders.keys()).intersection(requested_types)

    if accepted_and_requested:
        return accepted_response_builders[accepted_and_requested.pop()]()
    else:
        return accepted_response_builders[default]()
