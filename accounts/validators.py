# accounts/validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class NoCommonPinValidator:
    """
    Blocks highly insecure or sequential 6-digit PINs/passwords 
    while allowing custom numeric combinations.
    """
    def validate(self, password, user=None):
        # Only target numeric strings (or handle all, but specifically 6-digits)
        if password.isdigit():
            # 1. Check for repeating digits (e.g., 000000, 111111)
            if len(set(password)) == 1:
                raise ValidationError(
                    _("This password is too simple. Avoid repeating single digits."),
                    code="password_too_simple",
                )

            # 2. Check for ascending sequences (e.g., 123456, 012345)
            ascending = "01234567890123456789"
            if password in ascending:
                raise ValidationError(
                    _("This password is a sequential number pattern and is too easy to guess."),
                    code="password_sequential",
                )

            # 3. Check for descending sequences (e.g., 654321, 987654)
            descending = "98765432109876543210"
            if password in descending:
                raise ValidationError(
                    _("This password is a sequential number pattern and is too easy to guess."),
                    code="password_sequential",
                )

    def get_help_text(self):
        return _("Your 6-digit password cannot be entirely repeating digits or standard sequences like 123456.")