# flash_messages.py
# Standardised flash message helpers.
# Using these functions ensures consistent Bootstrap alert categories
# across all modules instead of passing raw category strings.

from flask import flash


def flash_success(message):
    """Flash a green success alert."""
    flash(message, 'success')


def flash_error(message):
    """Flash a red error/danger alert."""
    flash(message, 'danger')


def flash_warning(message):
    """Flash a yellow warning alert."""
    flash(message, 'warning')


def flash_info(message):
    """Flash a blue informational alert."""
    flash(message, 'info')