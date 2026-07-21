import os
from flask import Flask, redirect, render_template, request, session, url_for , jsonify
import module_wChange
import modules
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

@app.route("/contacts", methods=["GET"])
def send():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"contacts": []}), 401
        
    contacts = get_contacts(user_id)
    return jsonify({
        "contacts": contacts
    })

@app.route("/main_web", methods=["GET", "POST"])
def main_web():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_id = session["user_id"]
    user_email = session.get("username")
    output_text = session.get("encrypted_text", "")
    input_text = session.get("input_text", "")
    selected_contact_id = session.get("selected_contact_id")
    get_received_files_list = get_received_files(user_id, selected_contact_id)
    get_sent_files_list = get_sent_files(user_id, selected_contact_id)
    session['status_msg'] = None

    if request.method == "POST":
        action = request.form.get("action_html")

        password_encrypt = request.form.get("password_encrypt_html", "")
        password_decrypt = request.form.get("password_decrypt_html", "")

        address = request.form.get("address_html", "").strip()
        file_name = request.form.get("filename_html").strip()

        text_input = request.form.get("text_html", "")

        action_read_file_id = request.form.get("read_file_id")
        action_delete_file_id = request.form.get("delete_file_id")

        logout_button = request.form.get('logout_button')
        contact_name = request.form.get('contact_name')

        if logout_button == 'logout':
            session.clear()
            return redirect(url_for("login_page"))

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
                            if received_file_exists(user_id, receiver["id"], file_name):
                                session['status_msg'] = "You have already sent this file to this user."
                            else:
                                if receiver is None:
                                    session['status_msg'] = "Receiver email not found"
                                elif file_name == '':
                                    session['status_msg'] = 'Please enter File name!'
                                else:
                                    insert_received_file((receiver["id"], user_id, file_name, encrypted_payload))
                                    session['status_msg'] = f"Shared to {address}"
                else:
                    session['status_msg'] = "Password must be a 5-digit number for encryption!"

            receiver_id = session.get('selected_contact_id')
            get_received_files_list = get_received_files(user_id, receiver_id)
            get_sent_files_list = get_sent_files(user_id, receiver_id)
            
            return render_template(
                "main 2.5.2.html",
                contact_name=session.get('selected_contact_email'),
                get_received_files=get_received_files_list if get_received_files_list is not None else [],
                get_sent_files=get_sent_files_list if get_sent_files_list is not None else [],
                user_email=user_email.rsplit('@', 1)[0],
                file_name=session.get("selected_file_name"),
                status_msg=session.get('status_msg'),
            )

        elif contact_name:
            receiver_id, email = contact_name.split("|")
            receiver_id = int(receiver_id)
            session['selected_contact_email'] = email
            session['selected_contact_id'] = receiver_id
            get_received_files_list = get_received_files(user_id, receiver_id)
            get_sent_files_list = get_sent_files(user_id, receiver_id)
            return render_template(
                "main 2.5.2.html",
                contact_name=session.get('selected_contact_email'),
                get_received_files=get_received_files_list if get_received_files_list is not None else [],
                get_sent_files=get_sent_files_list if get_sent_files_list is not None else [],
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
                get_received_files=get_received_files_list if get_received_files_list is not None else [],
                get_sent_files=get_sent_files_list if get_sent_files_list is not None else [],
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
                get_received_files=get_received_files_list if get_received_files_list is not None else [],
                get_sent_files=get_sent_files_list if get_sent_files_list is not None else [],
                user_email=user_email.rsplit('@', 1)[0],
                decrypted_text=session.get("decrypted_text", ""),
                file_name=session.get("selected_file_name"),
                status_msg=session.get('status_msg'),
            )

        elif action_delete_file_id:
            delete_file(action_delete_file_id)


    return render_template(
        "main 2.5.2.html",
        contact_name=session.get('selected_contact_email'),
        get_received_files=get_received_files_list if get_received_files_list is not None else [],
        get_sent_files=get_sent_files_list if get_sent_files_list is not None else [],
        user_email=user_email.rsplit('@', 1)[0],
        file_name=session.get("selected_file_name"),
        status_msg=session.get('status_msg'),
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
