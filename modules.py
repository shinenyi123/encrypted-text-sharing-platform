from werkzeug.security import check_password_hash, generate_password_hash

from database import fetch_user, insert_user


def signup(email, password):
    if not email or not password:
        return False, "Email and password are required"

    if not email.endswith("@smail.com"):
        return False, "Email must end with @smail.com"

    if fetch_user(email):
        return False, "Email already registered"

    insert_user((email, generate_password_hash(password)))
    return True, "Account created successfully"


def login(email, password):
    user = fetch_user(email)
    if not user:
        return False, None, "Invalid email or password"

    if not check_password_hash(user["password_hash"], password):
        return False, None, "Invalid email or password"

    return True, user["id"], user["email"]