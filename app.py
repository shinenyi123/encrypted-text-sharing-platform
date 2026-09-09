import os
from flask import Flask, abort, redirect, render_template, request, session, url_for, jsonify
from dotenv import load_dotenv
from flask_session import Session

load_dotenv()

import module_wChange
import auth_client
from database import (
    fetch_user,
    insert_received_file,
    get_received_files,
    init_db,
    get_contacts,
    get_sent_files,
    all_files,
    delete_file,
    received_file_exists,
    get_received_files_list,
    get_admin_users,
    get_admin_user,
    get_admin_user_files,
    count_admin_user_files,
)

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is required")
app.config.update(
    SESSION_TYPE="filesystem",
    SESSION_FILE_DIR=os.environ.get("SESSION_FILE_DIR", os.path.join(app.instance_path, "flask_session")),
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
)
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
Session(app)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    return redirect(url_for("login_page"))


@app.post("/api/admin/login")
def admin_api_login():
    return admin_login()


@app.post("/api/admin/logout")
@auth_client.admin_required
def admin_api_logout():
    session.clear()
    return jsonify({"authenticated": False})


@app.get("/api/admin/me")
@auth_client.admin_required
def admin_api_me():
    return jsonify({"authenticated": True})


@app.get("/admin")
@auth_client.admin_required
def admin_users():
    return render_template("admin_users.html", users=get_admin_users())


@app.get("/admin/user/<int:user_id>")
@auth_client.admin_required
def admin_user_detail(user_id):
    user = get_admin_user(user_id)
    if user is None:
        abort(404)
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    per_page = 50
    total = count_admin_user_files(user_id)
    return render_template(
        "admin_user_detail.html",
        user=user,
        files=get_admin_user_files(user_id, page, per_page),
        page=page,
        total_pages=max(1, (total + per_page - 1) // per_page),
    )


@app.route("/", methods=["GET"])
@app.route("/login_page", methods=["GET"])
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("user_id"):
        return redirect(url_for("main_web"))

    error_msg = None
    if request.method == "POST":
        user = auth_client.authenticate(
            request.form.get("email", ""),
            request.form.get("password", ""),
        )
        if user:
            auth_client.establish_session(user)
            return redirect(url_for("main_web"))
        error_msg = auth_client.LOGIN_ERROR
    return render_template(
        "login_motify.html",
        error_msg=error_msg,
        auth_signup_url=os.environ.get(
            "AUTH_SIGNUP_URL", "https://auth-service-kaef.onrender.com/signup"
        ),
        auth_reset_url=os.environ.get(
            "AUTH_RESET_URL", "https://auth-service-kaef.onrender.com/forgot-password"
        ),
    )


@app.get("/logout")
def logout():
    auth_client.logout_session()
    return redirect(url_for("login_page"))


@app.route("/signin", methods=["GET"])
@app.route("/signup_page", methods=["GET"])
@app.route("/sigin", methods=["GET"])
def signin_page():
    return redirect(os.environ.get(
        "AUTH_SIGNUP_URL", "https://auth-service-kaef.onrender.com/signup"
    ))


@app.route("/contacts", methods=["GET"])
@auth_client.auth_required
def send():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"contacts": []}), 401
        
    contacts = get_contacts(user_id)
    return jsonify({
        "contacts": contacts
    })


@app.route("/receive_files", methods=["GET"])
@auth_client.auth_required
def receive_files():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"received_files": [], "all_received_files": []}), 401

    all_received_files = []
    for file in get_received_files_list(user_id):
        normalized_file = dict(file) if isinstance(file, dict) else {"id": file[0], "file_name": file[1], "encrypted_content": file[2], "created_at": file[3], "sender_email": file[4], "sender_id": file[5]}
        if normalized_file.get("created_at"):
            normalized_file["created_at"] = str(normalized_file["created_at"])
        all_received_files.append(normalized_file)

    selected_contact_id = session.get("selected_contact_id")
    selected_contact_email = session.get("selected_contact_email")

    filtered_files = all_received_files
    if selected_contact_id is not None and str(selected_contact_id).strip() != "":
        filtered_files = [
            file for file in all_received_files
            if str(file.get("sender_id")) == str(selected_contact_id)
        ]
    elif selected_contact_email:
        filtered_files = [
            file for file in all_received_files
            if str(file.get("sender_email", "")).lower() == str(selected_contact_email).lower()
        ]

    return jsonify({
        "received_files": filtered_files,
        "all_received_files": all_received_files,
        "selected_contact_id": selected_contact_id,
        "selected_contact_email": selected_contact_email,
    })


@app.route("/main_web", methods=["GET", "POST"])
@auth_client.auth_required
def main_web():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_id = session["user_id"]
    user_email = session.get("username")
    output_text = session.get("encrypted_text", "")
    input_text = session.get("input_text", "")
    selected_contact_id = session.get("selected_contact_id")
    selected_contact_email = session.get("selected_contact_email")
    received_files_for_contact = get_received_files(user_id, selected_contact_id)
    sent_files_for_contact = get_sent_files(user_id, selected_contact_id)
    session['status_msg'] = None

    if request.method == "POST":
        action = request.form.get("action_html")

        password_encrypt = request.form.get("password_encrypt_html", "")
        password_decrypt = request.form.get("password_decrypt_html", "")

        address = request.form.get("address_html", "").strip()
        file_name = request.form.get("filename_html", "").strip()

        text_input = request.form.get("text_html", "")

        action_read_file_id = request.form.get("read_file_id")
        action_delete_file_id = request.form.get("delete_file_id")

        logout_button = request.form.get('logout_button')
        contact_name = request.form.get('contact_name')

        if logout_button == 'logout':
            return redirect(url_for("logout"))

        password_encrypt_value = None
        if password_encrypt.strip():
            try:
                password_encrypt_value = int(password_encrypt)
            except ValueError:
                password_encrypt_value = None

        password_decrypt_value = None
        if password_decrypt.strip():
            try:
                password_decrypt_value = int(password_decrypt)
            except ValueError:
                password_decrypt_value = None

        session["input_text"] = text_input

        if action == "sent":
            if user_email == address:
                session['status_msg'] = "You cannot send a file to yourself!"
            else:
                if len(str(password_encrypt_value)) == 5:
                    if not text_input or text_input.strip() == "":
                        output_text = ""
                        session["encrypted_text"] = ""
                        session['status_msg'] = "Please enter some text to encrypt!"
                    else:
                        if all(char.isalpha() or char.isspace() for char in text_input):
                            output_text = module_wChange.Encrypt(text_input, password_encrypt_value)
                            session["encrypted_text"] = output_text
                            encrypted_payload = session.get("encrypted_text")
                            sent = True
                        else:
                            session['status_msg'] = 'Write text only!'
                            sent = False
                        session['user_name'] = user_email
                        receiver = fetch_user(address)
                        if sent:
                            if receiver is None:
                                session['status_msg'] = "Receiver email not found"
                            elif received_file_exists(user_id, receiver["id"], file_name):
                                session['status_msg'] = "You have already sent this file to this user."
                            elif file_name == '':
                                session['status_msg'] = 'Please enter File name!'
                            else:
                                insert_received_file((receiver["id"], user_id, file_name, encrypted_payload))
                                session['status_msg'] = f"Shared to {address}"
                else:
                    session['status_msg'] = "Password must be a 5-digit number for encryption!"

            selected_contact_id = session.get('selected_contact_id')
            received_files_for_contact = get_received_files(user_id, selected_contact_id)
            sent_files_for_contact = get_sent_files(user_id, selected_contact_id)

            return render_template(
                "main 2.5.2.html",
                contact_name=session.get('selected_contact_email'),
                get_received_files=received_files_for_contact if received_files_for_contact is not None else [],
                get_sent_files=sent_files_for_contact if sent_files_for_contact is not None else [],
                user_email=user_email.rsplit('@', 1)[0],
                file_name=session.get("selected_file_name"),
                status_msg=session.get('status_msg'),
            )

        elif contact_name:
            try:
                receiver_id_str, email = contact_name.split("|", 1)
                receiver_id = int(receiver_id_str)
            except (ValueError, TypeError):
                receiver_id = None
                email = contact_name

            session['selected_contact_email'] = email
            session['selected_contact_id'] = receiver_id
            received_files_for_contact = get_received_files(user_id, receiver_id)
            sent_files_for_contact = get_sent_files(user_id, receiver_id)
            return render_template(
                "main 2.5.2.html",
                contact_name=session.get('selected_contact_email'),
                get_received_files=received_files_for_contact if received_files_for_contact is not None else [],
                get_sent_files=sent_files_for_contact if sent_files_for_contact is not None else [],
                user_email=user_email.rsplit('@', 1)[0],
                file_name=session.get("selected_file_name"),
            )

        elif action_read_file_id:
            all_files_list = all_files(user_id)
            for file_list in all_files_list:
                if str(file_list['id']) == str(action_read_file_id):
                    fileName = file_list['file_name']
                    session["selected_file_name"] = fileName
                    session["output_file"] = file_list['encrypted_content']
                    break
            return render_template(
                "main 2.5.2.html",
                contact_name=session.get('selected_contact_email'),
                get_received_files=received_files_for_contact if received_files_for_contact is not None else [],
                get_sent_files=sent_files_for_contact if sent_files_for_contact is not None else [],
                user_email=user_email.rsplit('@', 1)[0],
                file_name=session.get("selected_file_name"),
            )

        elif action == 'decrypt':
            if len(str(password_decrypt_value)) == 5:
                output_decrypted_text = module_wChange.Decrypt(session.get('output_file'), password_decrypt_value)
                session["decrypted_text"] = output_decrypted_text
            else:
                session['decrypted_text'] = f'.....'
                session['status_msg'] = f'Password must be a 5-digit number for encryption!'
            return render_template(
                "main 2.5.2.html",
                contact_name=session.get('selected_contact_email'),
                get_received_files=received_files_for_contact if received_files_for_contact is not None else [],
                get_sent_files=sent_files_for_contact if sent_files_for_contact is not None else [],
                user_email=user_email.rsplit('@', 1)[0],
                decrypted_text=session.get("decrypted_text", ""),
                file_name=session.get("selected_file_name"),
                status_msg=session.get('status_msg'),
            )

        elif action_delete_file_id:
            delete_file(action_delete_file_id)
            selected_contact_id = session.get('selected_contact_id')
            received_files_for_contact = get_received_files(user_id, selected_contact_id)
            sent_files_for_contact = get_sent_files(user_id, selected_contact_id)

    return render_template(
        "main 2.5.2.html",
        contact_name=session.get('selected_contact_email'),
        get_received_files=received_files_for_contact if received_files_for_contact is not None else [],
        get_sent_files=sent_files_for_contact if sent_files_for_contact is not None else [],
        user_email=user_email.rsplit('@', 1)[0],
        file_name=session.get("selected_file_name"),
        status_msg=session.get('status_msg'),
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
