import os

from flask import Flask, redirect, render_template, request, session, url_for

import module_wChange
import modules
from database import (
    delete_save_file,
    delete_transfer_file,
    fetch_file_by_id,
    fetch_received_file_by_id,
    fetch_user,
    get_user_files,
    insert_file,
    insert_received_file,
    get_received_files,
    init_db,
)

app = Flask(__name__, template_folder="templates")
app.secret_key = "my_secret_key_123"


@app.route("/", methods=["GET"])
@app.route("/login_page", methods=["GET"])
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

    return render_template("login_motify.html", error_msg="Invalid email or password")


@app.route("/signin", methods=["GET"])
@app.route("/signup_page", methods=["GET"])
@app.route("/sigin", methods=["GET"])
def signin_page():
    if session.get("user_id"):
        return redirect(url_for("main_web"))
    return render_template("signin_motify.html")


@app.route("/signin", methods=["POST"])
def signin_post():
    email = request.form.get("signup_email_html", "").strip()
    password = request.form.get("signup_password_html", "")
    action = request.form.get("action_html")

    error_msg = None
    if action == 'signup':
        success, message = modules.signup(email, password)
        if success:
            return redirect(url_for("login_page"))
        error_msg = message

    return render_template("signin_motify.html", error_msg=error_msg)


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
        action_file_list = request.form.get("action_file_list")

        password = request.form.get("password_html", "")
        address = request.form.get("address_html", "").strip()
        file_name = request.form.get("file_name_html", "untitled.txt").strip() or "untitled.txt"

        text_input = request.form.get("text_html", "")

        action_read_file_id = request.form.get("read_file_id")
        action_delete_save_file_id = request.form.get("delete_save_file_id")
        action_delete_transfer_file_id = request.form.get("delete_transfer_file_id")

        password_value = None
        if password and password.strip():
            try:
                password_value = int(password)
            except ValueError:
                password_value = None

        session["input_text"] = text_input

        if action == "w_to_p":
            if len(str(password_value)) == 5:
                if not text_input or text_input.strip() == "":
                    output_text = ""
                    session["encrypted_text"] = ""
                    status_msg = "Please enter some text to encrypt!"
                elif password_value is None:
                    output_text = ""
                    session["encrypted_text"] = ""
                    status_msg = "Password must be numeric for encryption!"
                else:
                    output_text = module_wChange.Encrypt(text_input, password_value)
                    session["encrypted_text"] = output_text
                    status_msg = "Encryption completed"
            else:
                status_msg = "Password must be a 5-digit number for encryption!"

        elif action == "p_to_w":
            if len(str(password_value)) == 5:
                if not text_input or text_input.strip() == "":
                    output_text = ""
                    session["encrypted_text"] = ""
                    status_msg = "Please enter some text to decrypt!"
                elif password_value is None:
                    output_text = ""
                    session["encrypted_text"] = ""
                    status_msg = "Password must be numeric for decryption!"
                else:
                    output_text = module_wChange.Decrypt(text_input, password_value)
                    session["encrypted_text"] = output_text
                    status_msg = "Decryption completed"
            else:
                status_msg = "Password must be a 5-digit number for encryption!"

        elif action == "save":
            encrypted_payload = session.get("encrypted_text") or output_text
            if not encrypted_payload:
                encrypted_payload = module_wChange.Encrypt(text_input, password_value) if password_value is not None else text_input
            insert_file((user_id, file_name, encrypted_payload))
            files = get_user_files(user_id)
            output_text = encrypted_payload
            status_msg = "Data block saved"

        elif action == "sent":
            encrypted_payload = session.get("encrypted_text") or output_text
            session['user_name'] = user_email
            if not encrypted_payload:
                encrypted_payload = module_wChange.Encrypt(text_input, password_value) if password_value is not None else text_input
            receiver = fetch_user(address)
            if receiver is None:
                status_msg = "Receiver email not found"
            else:
                insert_received_file((receiver["id"], user_id, file_name, encrypted_payload))
                status_msg = f"Shared to {address}"
            
            return render_template(
                "main.html",
                user_email=user_email,
                status_msg=status_msg,
            )

        if action_file_list == "receive":
            received_files = get_user_files(user_id)
            if received_files:
                file_row = received_files[0]
                input_text = file_row["encrypted_content"]
                output_text = file_row["encrypted_content"]
                session['user_name'] = user_email
                session["input_text"] = input_text
                session["encrypted_text"] = input_text
                status_msg = "Loaded received file"
                
                return render_template(
                        "main.html",
                        user_email=user_email,
                        show_files_receive_py=True,
                        received_files_list=received_files,
                        status_msg=status_msg,
                    )
            else:
                status_msg = "No received files found"
    
        elif action_file_list == "transfer":
            user_files = get_received_files(user_id)
            if user_files:
                file_row = user_files[0]
                input_text = file_row["encrypted_content"]
                output_text = file_row["encrypted_content"]
                session['user_name'] = user_email
                session["input_text"] = input_text
                session["encrypted_text"] = input_text
                status_msg = "Loaded saved file for transfer"

                return render_template(
                        "main.html",
                        user_email=user_email,
                        show_files_transfer_py=True,
                        transfer_file_list=user_files,
                        status_msg=status_msg,
                    )
            else:
                status_msg = "No saved files found for transfer"


        received_files = get_user_files(user_id)
        if action_read_file_id == received_files[0]["id"] if received_files else None:
            file_row = received_files[0]
            file_row = fetch_file_by_id(int(action_read_file_id), user_id)
            if file_row is None:
                file_row = fetch_received_file_by_id(int(action_read_file_id), user_id)
            if file_row:
                input_text = file_row["encrypted_content"]
                output_text = file_row["encrypted_content"]
                session['user_name'] = user_email
                session["input_text"] = input_text
                session["encrypted_text"] = input_text
                status_msg = "Loaded file content"

                return render_template(
                    "main.html",
                    user_email=user_email,
                    status_msg=status_msg,
                )
            
        if action_delete_save_file_id:
            delete_save_file(int(action_delete_save_file_id), user_id)
            session['user_name'] = user_email
            status_msg = "File deleted successfully"

            return render_template(
                    "main.html",
                    user_email=user_email,
                    status_msg=status_msg,
                )
        
        if action_delete_transfer_file_id:
            delete_transfer_file(int(action_delete_transfer_file_id), user_id)
            session['user_name'] = user_email
            status_msg = "File deleted successfully"

            return render_template(
                    "main.html",
                    user_email=user_email,
                    status_msg=status_msg,
                )

    return render_template(
        "main.html",
        user_email=user_email,
        files=files,
        output_text=output_text,
        input_text=input_text,
        status_msg=status_msg,
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
