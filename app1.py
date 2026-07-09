import os

from flask import Flask, redirect, render_template, request, session, url_for

import module_wChange
import modules
from database import (
    fetch_file_by_id,
    fetch_user,
    get_user_files,
    insert_file,
    insert_received_file,
)

app = Flask(__name__, template_folder="templates")
app.secret_key = "my_secret_key_123"


@app.route("/", methods=["GET"])
@app.route("/login", methods=["GET"])
def login_page():
    if session.get("user_id"):
        return redirect(url_for("main_web"))
    return render_template("login_motify.html", error_msg=None)


@app.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("login_email_html", "").strip()
    password = request.form.get("login_password_html", "")
    action = request.form.get("action_html")

    if action == 'login':
        authorized, user_id, user_email = modules.login(email, password)
        if authorized:
            session["username"] = user_email
            session["user_id"] = user_id
            session["encrypted_text"] = ""
            session["input_text"] = ""
            return redirect(url_for("main_web"))
    elif action == 'signup':
        return redirect(url_for("signin_page"))

    return render_template("login_motify.html", error_msg="Invalid email or password")


@app.route("/signin", methods=["GET"])
@app.route("/signup_page", methods=["GET"])
@app.route("/sigin", methods=["GET"])
def signin_page():
    if session.get("user_id"):
        return redirect(url_for("main_web"))
    return render_template("sigin_motify.html", error_msg=None)


@app.route("/signin", methods=["POST"])
def signin_post():
    email = request.form.get("signup_email_html", "").strip()
    password = request.form.get("signup_password_html", "")

    success, message = modules.signup(email, password)
    if success:
        return redirect(url_for("login_page"))

    return render_template("sigin_motify.html", error_msg=message)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/main_web", methods=["GET", "POST"])
def main_web():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_id = session["user_id"]
    user_email = session.get("username")
    files = get_user_files(user_id)
    output_text = session.get("encrypted_text", "")
    input_text = session.get("input_text", "")
    status_msg = None

    if request.method == "POST":
        action = request.form.get("action_html")
        read_file_id = request.form.get("read_file_id")
        text_input = request.form.get("text_html", "")
        password = request.form.get("password_html", "")
        file_name = request.form.get("file_name_html", "untitled.txt").strip() or "untitled.txt"
        address = request.form.get("address_html", "").strip()

        session["input_text"] = text_input

        if action == "w_to_p":
            if not text_input or text_input.strip() == "":
                output_text = ""
                session["encrypted_text"] = ""
                status_msg = "Please enter some text to encrypt!"
            else:
                output_text = module_wChange.Encrypt(text_input, password)
                session["encrypted_text"] = output_text
                status_msg = "Encryption completed"
        elif action == "p_to_w":
            if not text_input or text_input.strip() == "":
                output_text = ""
                session["encrypted_text"] = ""
                status_msg = "Please enter some text to decrypt!"
            else:
                output_text = module_wChange.Decrypt(text_input, password)
                session["encrypted_text"] = output_text
                status_msg = "Decryption completed"
        elif action == "save":
            encrypted_payload = session.get("encrypted_text") or output_text
            if not encrypted_payload:
                encrypted_payload = module_wChange.Encrypt(text_input, password) if password else text_input
            insert_file((user_id, file_name, encrypted_payload))
            files = get_user_files(user_id)
            output_text = encrypted_payload
            status_msg = "Data block saved"
        elif action == "sent":
            encrypted_payload = session.get("encrypted_text") or output_text
            if not encrypted_payload:
                encrypted_payload = module_wChange.Encrypt(text_input, password) if password else text_input
            receiver = fetch_user(address)
            if receiver is None:
                status_msg = "Receiver email not found"
            else:
                insert_received_file((receiver["id"], user_id, file_name, encrypted_payload))
                status_msg = f"Shared to {address}"

        if read_file_id:
            file_row = fetch_file_by_id(int(read_file_id), user_id)
            if file_row:
                input_text = file_row["encrypted_content"]
                output_text = file_row["encrypted_content"]
                session["input_text"] = input_text
                session["encrypted_text"] = input_text
                status_msg = "Loaded saved file"

    return render_template(
        "main.html",
        user_email=user_email,
        files=files,
        output_text=output_text,
        input_text=input_text,
        status_msg=status_msg,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
