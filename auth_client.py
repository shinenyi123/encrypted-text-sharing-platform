import os
from functools import wraps

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from database import fetch_login_user


LOGIN_ERROR = "Invalid email or password."


def authenticate(email, password):
    user = fetch_login_user(email.strip().lower())
    if not user or not user.get("is_verified"):
        return None
    try:
        password_matches = check_password_hash(user["password_hash"], password)
    except (TypeError, ValueError):
        password_matches = False
    if not password_matches:
        return None
    return {"id": user["id"], "email": user["email"]}


def establish_session(user):
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["email"]


def logout_session():
    session.clear()


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.is_json or request.path in {"/contacts", "/receive_files"} or request.accept_mimetypes.best == "application/json":
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @auth_required
    def wrapped(*args, **kwargs):
        allowed_emails = {
            email.strip().lower()
            for email in os.environ.get("ADMIN_EMAILS", "").split(",")
            if email.strip()
        }
        if session.get("username", "").lower() not in allowed_emails:
            return jsonify({"error": "Admin access required"}), 403
        return view(*args, **kwargs)

    return wrapped
