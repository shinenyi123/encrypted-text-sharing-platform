import os
from functools import wraps

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from database import fetch_login_user


LOGIN_ERROR = "Invalid email or password."


def _admin_names():
    names = set()
    for key in ("ADMIN_NAME", "admin_name", "ADMIN_EMAILS", "admin_emails"):
        value = os.environ.get(key, "")
        if not value:
            continue
        if key in {"ADMIN_EMAILS", "admin_emails"}:
            names.update(part.strip().lower() for part in value.split(",") if part.strip())
        else:
            names.add(value.strip().lower())
    username = os.environ.get("ADMIN_NAME") or os.environ.get("admin_name") or ""
    if username:
        names.add(username.strip().lower())
    for value in (os.environ.get("ADMIN_EMAILS") or "").split(","):
        part = value.strip().lower()
        if part:
            names.add(part)
            names.add(part.split("@", 1)[0])
    return names


def _admin_password():
    for key in ("ADMIN_PASSWORD", "admin_password", "ADMIN_PASS", "admin_pass"):
        value = os.environ.get(key)
        if value is not None and value != "":
            return value
    return ""


def is_valid_admin_login(username, password):
    if not username or not password:
        return False
    username = str(username).strip().lower()
    if username not in _admin_names():
        return False
    return password == _admin_password()


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
        allowed_names = _admin_names()
        username = session.get("username", "").strip().lower()
        if username not in allowed_names:
            return jsonify({"error": "Admin access required"}), 403
        return view(*args, **kwargs)

    return wrapped
