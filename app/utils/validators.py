# validators.py
# Shared form validation helpers used across all CRUD modules.


def required_fields(data, fields):
    """
    Check that all required field names are present and non-empty in data.

    Args:
        data: dict of form data (e.g. request.form)
        fields: list of field name strings that are required

    Returns:
        List of field name strings that are missing or empty.
        Returns an empty list if all required fields are present.
    """
    errors = []
    for field in fields:
        value = data.get(field, '')
        if isinstance(value, str) and not value.strip():
            errors.append(field)
        elif value is None:
            errors.append(field)
    return errors


def is_positive_number(value):
    """
    Return True if value can be converted to a positive float, False otherwise.
    Used for validating price, rate, cost, and quantity fields.
    """
    try:
        return float(value) >= 0
    except (TypeError, ValueError):
        return False


def is_positive_integer(value):
    """
    Return True if value can be converted to a non-negative integer, False otherwise.
    Used for validating quantity and count fields.
    """
    try:
        return int(value) >= 0
    except (TypeError, ValueError):
        return False

def is_valid_email(value):
    """
    Basic email format check. 
    returns True if value contains exactly one '@' and has at least one character before @ and has at least one  '.' after @
    """
    if not isinstance(value, str):
        return False
    if value.count('@') != 1:
        return False
    local, domain = value.split('@')
    if not local:
        return False
    if '.' not in domain:
        return False
    return True
    

        


