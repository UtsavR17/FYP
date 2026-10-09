# text.py
# Shared text helpers for searching and comparing values that may be None.


def norm(value):
    """
    Lower-cased, stripped text for searching and comparing.
    None gives '', numbers and other values are converted with str().
    """
    if value is None:
        return ''
    return str(value).strip().lower()
