"""Utility functions for using authentication"""
from functools import wraps
import json
from werkzeug.exceptions import HTTPException

from flask import Blueprint, jsonify, redirect, render_template, session, url_for, _request_ctx_stack, request
from jose import jwt
from app.serve import CLIENT_ID, SECRET_KEY, app, API_AUDIENCE, AUTH0_DOMAIN
from authlib.flask.client import OAuth
from six.moves.urllib.request import urlopen

ALGORITHMS = ["RS256"]
auth = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=CLIENT_ID,
    client_secret=SECRET_KEY,
    api_base_url='https://durian-inc.auth0.com',
    access_token_url='https://durian-inc.auth0.com/oauth/token',
    authorize_url='https://durian-inc.auth0.com/authorize',
    client_kwargs={
        'scope': 'openid profile',
    },
)

# TODO: Make above urls environment variables


def requires_auth(func):
    """Decorator to specify that function needs to be authenticated"""

    @wraps(func)
    def decorated(*args, **kwargs):
        """Check authentication, or get failure"""
        if 'profile' not in session:
            # Redirect to Login page here
            return jsonify(success=False, error="Authentication failure")
        else:
            # Check if the sub form the session matches the sub from the decodded token
            pass
        return func(*args, **kwargs)

    return decorated


# Error handler
class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


def get_token_auth_header():
    """Obtains the Access Token from the Authorization Header
    """
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise AuthError({
            "code": "authorization_header_missing",
            "description": "Authorization header is expected"
        }, 401)

    parts = auth.split()

    if parts[0].lower() != "bearer":
        raise AuthError(
            {
                "code": "invalid_header",
                "description": "Authorization header must start with"
                " Bearer"
            }, 401)
    elif len(parts) == 1:
        raise AuthError({
            "code": "invalid_header",
            "description": "Token not found"
        }, 401)
    elif len(parts) > 2:
        raise AuthError(
            {
                "code": "invalid_header",
                "description": "Authorization header must be"
                " Bearer token"
            }, 401)

    token = parts[1]
    return token


def requires_auth_token(f):
    """Determines if the Access Token is valid"""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_auth_header()
        jsonurl = urlopen("https://" + AUTH0_DOMAIN + "/.well-known/jwks.json")
        jwks = json.loads(jsonurl.read())
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        if rsa_key:
            try:
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=ALGORITHMS,
                    audience=API_AUDIENCE,
                    issuer=AUTH0_DOMAIN + "/")
            except jwt.ExpiredSignatureError:
                raise AuthError({
                    "code": "token_expired",
                    "description": "token is expired"
                }, 401)
            except jwt.JWTClaimsError:
                raise AuthError({
                    "code":
                    "invalid_claims",
                    "description":
                    "incorrect claims,"
                    "please check the audience and issuer"
                }, 401)
            except Exception:
                raise AuthError(
                    {
                        "code": "invalid_header",
                        "description": "Unable to parse authentication"
                        " token."
                    }, 401)
            _request_ctx_stack.top.current_user = payload
            return f(*args, **kwargs)
        raise AuthError({
            "code": "invalid_header",
            "description": "Unable to find appropriate key"
        }, 401)

    return decorated


def requires_scope(required_scope):
    """Determines if the required scope is present in the Access Token
    Args:
        required_scope (str): The scope required to access the resource
    """
    token = get_token_auth_header()
    unverified_claims = jwt.get_unverified_claims(token)
    if unverified_claims.get("scope"):
        token_scopes = unverified_claims["scope"].split()
        for token_scope in token_scopes:
            if token_scope == required_scope:
                return True
    return False
