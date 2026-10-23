"""Autorización común: grupos de Cognito permitidos por operación."""


def get_claims(event: dict) -> dict:
    return event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})


def require(event: dict, allowed_groups: set):
    """Devuelve (claims, None) si el usuario puede pasar, o ({}, respuesta 401/403)."""
    claims = get_claims(event)
    if not claims:
        return {}, {"statusCode": 401, "body": '{"error": "No autenticado"}'}
    groups = set(claims.get("cognito:groups", "").split(","))
    if not groups & allowed_groups:
        return {}, {"statusCode": 403, "body": '{"error": "No autorizado"}'}
    return claims, None
