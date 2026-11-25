from functools import wraps
from flask import current_app, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.models import User


class AuthProvider:
    """Abstract directory provider (AD-06: LDAP/AD federated or local demo directory)."""

    def authenticate(self, identifier: str, password: str) -> User | None:
        raise NotImplementedError


class LocalDirectoryProvider(AuthProvider):
    def authenticate(self, identifier: str, password: str) -> User | None:
        user = (
            User.query.filter(
                (User.email == identifier) | (User.directory_uid == identifier)
            )
            .filter_by(is_active=True)
            .first()
        )
        if user and user.check_password(password):
            return user
        return None


class LDAPDirectoryProvider(AuthProvider):
    """Stub adapter for institutional OpenLDAP / Active Directory integration."""

    def authenticate(self, identifier: str, password: str) -> User | None:
        # In production hospital deployment, bind to institutional LDAP/AD here
        # and synchronize active user record into BioTrack's RBAC table.
        return LocalDirectoryProvider().authenticate(identifier, password)


def get_auth_provider() -> AuthProvider:
    provider_name = current_app.config.get("AUTH_PROVIDER", "local").lower()
    if provider_name == "ldap":
        return LDAPDirectoryProvider()
    return LocalDirectoryProvider()


def get_current_user() -> User | None:
    identity = get_jwt_identity()
    if not identity:
        return None
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return User.query.filter_by(id=user_id, is_active=True).first()


def verify_reauth(user: User, raw_password: str) -> bool:
    """Mandatory credential re-entry for digital signatures (AD-06, QA-06)."""
    if not user or not raw_password:
        return False
    return user.check_password(raw_password)


def roles_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = get_current_user()
            if not user:
                return jsonify({"error": "Usuario no autenticado o inactivo."}), 401
            if allowed_roles and user.role not in allowed_roles:
                return (
                    jsonify(
                        {
                            "error": f"Acceso denegado. Rol requerido: {', '.join(allowed_roles)}."
                        }
                    ),
                    403,
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator
