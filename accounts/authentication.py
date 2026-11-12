from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Authenticate by email without case sensitivity."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get("email", username)
        if email is None or password is None:
            return None

        user_model = get_user_model()
        try:
            user = user_model._default_manager.get(email__iexact=email.strip())
        except user_model.DoesNotExist:
            # Run the password hasher even for an unknown email to reduce timing clues.
            user_model().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
