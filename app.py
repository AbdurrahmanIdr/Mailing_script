#!/usr/bin/env python3

import csv
import datetime
import functools
import math
import os
import shutil as sh
import time
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from secrets import token_urlsafe
from threading import Thread
from urllib.parse import quote, unquote

from flask import (
    Flask,
    render_template,
    url_for,
    request,
    redirect,
    jsonify,
    session,
    flash,
    send_file,
)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from models.explorer import (
    get_sorted_files,
    get_file_info,
    format_file_size,
    datetimeformat,
    query_string,
)
from models.mail_mod import send_email_with_attachment, progress_data
from models.pdf_rel import splitter, base_dir, progress

app = Flask(__name__)
app.secret_key = token_urlsafe(32)
db_path = os.path.abspath("db.sqlite")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ippis = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    surname = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(100), nullable=True)
    active = db.Column(db.Boolean, default=False)

    def __init__(self, email, ippis, first_name, surname, phone, active=False):
        self.email = email
        self.ippis = ippis
        self.first_name = first_name
        self.surname = surname
        self.phone = phone
        self.active = active


class ActiveUser(db.Model):
    __tablename__ = "active"
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class InactiveUser(db.Model):
    __tablename__ = "inactive_users"
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class UnknownUser(db.Model):
    __tablename__ = "unknown_users"
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class Admins(db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(20), nullable=False)

    @property
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(str(password))

    def verify_password(self, password):
        return check_password_hash(self.password_hash, str(password))


app.jinja_env.filters["format_file_size"] = format_file_size
app.jinja_env.filters["datetimeformat"] = datetimeformat


def login_required(route):
    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("You need to be logged in to view this page.", 'error')
            return redirect(url_for("login"))
        user = Admins.query.filter_by(username=session["username"]).first()
        if not user:
            flash("User not found. Please log in again.", 'error')
            return redirect(url_for("login"))
        return route(*args, **kwargs)

    return wrapper


@app.route("/")
@app.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")
        user = Admins.query.filter_by(username=username).first()
        if user and user.verify_password(password):
            flash(f"{username} logged in successfully.", "success")
            session["username"] = username
            return redirect(url_for("directories", rel_directory='base_dir'))
        else:
            flash("Username or password is incorrect, try again.", "error")
    return render_template("login.html", title="Login-Form")


@app.route("/logout/", methods=['POST'])
def logout():
    session.pop('username', None)  # Remove username from session
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))


@app.route("/upload/", methods=["POST"])
@login_required
def upload():
    """
    Upload a file to the directory. If the file exists it will be overwritten.
    @return redirect to the directories page with the file uploaded.
    """
    file = request.files.get("file")
    filename = str(file.filename)

    # Create the base directory if it doesn t exist.
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    # Save the file to the file system.
    if file and filename != "":
        full_path = os.path.join(base_dir, filename)
        # Remove the full path if it exists.
        if os.path.exists(full_path):
            os.remove(full_path)
        file.save(full_path)
        flash(f"{file.filename} saved successfully.", "success")

    else:
        flash(f"{file.filename} failed to upload check the file type != PDF", "error")

    return redirect(url_for("directories", rel_directory='base_dir'))


@app.route("/directories/", methods=["GET", "POST"])
@login_required
def directories():
    if request.method == "POST":
        rel_directory = request.form.get('rel_directory')
        page = int(request.form.get('page', 1))
    else:
        rel_directory = request.args.get('rel_directory', 'base_dir')
        page = request.args.get('page', 1, type=int)
    
    if not rel_directory or rel_directory == "base_dir":
        rel_directory = base_dir
        
    per_page = 20
    files, current_directory = get_sorted_files(rel_directory)
    
    total_files = len(files)
    total_pages = math.ceil(total_files / per_page)
    files_on_page = files[(page - 1) * per_page: page * per_page]
    
    ActiveUser.query.delete()
    InactiveUser.query.delete()
    UnknownUser.query.delete()
    db.session.commit()
    
    return render_template('directories.html',
                           files=files_on_page,
                           current_directory=current_directory,
                           page=page,
                           total_pages=total_pages,
                           title="Directories")


@app.route("/view_file/<path:filepath>/", methods=["GET", "POST"])
@login_required
def view_file(filepath):
    """
    Render the page for viewing file metadata.

    Args:
        filepath (str): Path to the file.

    Returns:
        render_template: Rendered HTML template.
    """

    file_path = Path(filepath)

    if not file_path.exists():
        flash(f"The file '{file_path}' does not exist.", "error")
        return redirect(request.url)

    file_info = get_file_info(file_path)

    # Handle POST request to retrieve file path
    if request.method == "POST":
        # Logic to retrieve the file path goes here
        file_path_to_display = str(file_path)

        # Render the template with the file path to display
        return render_template(
            "view_file.html",
            file_path=file_path.resolve(),
            file_info=file_info,
            file_path_to_display=file_path_to_display,
        )

    # Render the template for a regular GET request
    return render_template(
        "view_file.html",
        title="View File",
        file_path=file_path.resolve(),
        file_info=file_info,
    )


@app.route("/delete_file_or_directory/", methods=["POST"])
@login_required
def delete_file_or_directory():
    """
    Delete a file or directory. This is a form to delete a file
    or directory.

    Returns:
        Redirect to the directories page if request method is POST
    """
    # This is a POST request.
    if request.method == "POST":
        path = request.form.get("path")
        # Retrieve current directory from form data
        current_directory = request.form.get("current_directory")
        current_directory = Path(current_directory)

        try:
            if os.path.exists(path):
                # Delete file or directory.                
                name = Path(path).name
                if os.path.isfile(path):
                    os.remove(path)
                    flash(f"{name} deleted successfully!", "success")
                elif os.path.isdir(path):
                    sh.rmtree(path)
                    flash(f"{name} deleted successfully!", "success")
            else:
                flash("File or directory does not exist.", "error")
        except Exception as e:
            flash(
                f"An error occurred while deleting the file/directory.\n{e}", "error")

        return redirect(url_for("directories", rel_directory=current_directory))


@app.route("/retrieve_selected_path/", methods=["GET", "POST"])
@login_required
def retrieve_selected_path():
    """
    Render the page with retrieved selected file paths.

    Returns:
        render_template: Rendered HTML template.
    """
    if request.method == "POST":
        selected_file = request.form.get("selected_file")
        if os.path.isdir(selected_file):
            files = os.listdir(selected_file)
            if "success_mail" in files and "failed_mail" in files:
                return redirect(url_for("retry_send_mail",
                                        folder=selected_file))

            return render_template("query_db.html",
                                   folder=selected_file,
                                   title="Query DB")

        elif os.path.isfile(selected_file):
            try:
                if selected_file.endswith('.pdf'):
                    return render_template("split_enc.html",
                                           selected_file=selected_file,
                                           title="Split Encrypt")
                    
                raise TypeError
            except TypeError:
                flash("Invalid file type. Only PDFs are supported.", "error")
                
    return redirect(url_for("directories", rel_directory='base_dir'))


@app.route("/split_encrypt/", methods=["POST"])
@login_required
def split_encrypt():
    try:
        task_id = str(time.time())  # Generate a unique task ID
        progress[task_id] = 0  # Initialize progress
        
        file = request.form.get("file")
        file = Path(file)
        filename = str(file.name).split(".", maxsplit=1)[0]
        file_path = os.path.join(base_dir, filename)        
        
        folder_encoded = quote(file_path)            

        # Run the splitter function in the background
        thread = Thread(target=splitter, 
                        args=(str(file), file_path, task_id))
        thread.start()

        return render_template("progress.html",
                               task_id=task_id,
                               folder=folder_encoded)
        
    except Exception as e:
        flash(f"An error occurred while splitting the file.\n{e}", "error")
        return redirect(url_for("directories", rel_directory='base_dir'))


@app.route("/progress/<task_id>")
def progress_status(task_id):
    return jsonify({"progress": progress.get(task_id, 0)})


@app.route("/query_db/", methods=["GET", "POST"])
@login_required
def query_db():
    folder = request.form.get("folder")
    if not folder:
        return redirect(url_for("directories", rel_directory='base_dir'))

    folder = unquote(folder)
    return render_template("query_db.html", folder=folder)


@app.route("/results/", methods=["GET", "POST"])
@login_required
def results():    
    folder_encoded = request.form.get("folder")
    if not folder_encoded:
        return redirect(url_for("directories", rel_directory='base_dir'))

    folder = unquote(folder_encoded)
    db_found = User.query.all()

    active_found, inactive, unknown = query_string(folder, db_found)

    ActiveUser.query.delete()
    InactiveUser.query.delete()
    UnknownUser.query.delete()

    db.session.bulk_insert_mappings(
        ActiveUser, [{"ippis": ippis} for ippis in active_found]
    )
    db.session.bulk_insert_mappings(
        InactiveUser, [{"ippis": ippis} for ippis in inactive]
    )
    db.session.bulk_insert_mappings(
        UnknownUser, [{"ippis": ippis} for ippis in unknown]
    )
    db.session.commit()

    session["folder"] = folder_encoded
    session["active_count"] = len(active_found)
    session["inactive_count"] = len(inactive)
    session["unknown_count"] = len(unknown)

    return render_template(
        "results.html",
        active=len(active_found),
        inactive=len(inactive),
        unknown=len(unknown),
        folder=folder,
    )


@app.route("/view_users/<category>/", methods=["GET", "POST"])
@login_required
def view_users(category):    
    page = request.args.get('page', 1, type=int)
    per_page = 100  # Number of users per page
    
    if category == "active":
        users = ActiveUser.query.paginate(page=page, per_page=per_page)
        total_users = ActiveUser.query.count()
        
    elif category == "inactive":
        users = InactiveUser.query.paginate(page=page, per_page=per_page)
        total_users = InactiveUser.query.count()
        
    elif category == "unknown":
        users = UnknownUser.query.paginate(page=page, per_page=per_page)
        total_users = UnknownUser.query.count()
    else:
        flash("Category does not exist.", "error")
        return redirect(url_for("directories", rel_directory='base_dir'))

    return render_template("view_users.html",
                           category=category,
                           users=users.items,
                           pagination=users,
                           total_users=total_users)


@app.route("/back_to_result/")
def back_to_result():
    folder = unquote(session["folder"])
    active = session["active_count"]
    inactive = session["inactive_count"]
    unknown = session["unknown_count"]

    return render_template(
        "results.html", active=active, inactive=inactive, unknown=unknown, folder=folder
    )


@app.route("/send_mail/", methods=["POST"])
@login_required
def send_mail():
    folder = request.form.get("folder")
    task_id = str(time.time())  # Generate a unique task ID
    progress_data[task_id] = {
        "logs": [],
        "errors": [],
        "status": "running",
        "total": 0,
        "sent": 0,
        "failed": 0,
        "completed": False,
        "cancelled": False,
    }

    file_name = Path(folder).name
    folder_encoded = quote(folder)

    # Run the email sending function in the background
    thread = Thread(target=send_emails, args=(folder, task_id))
    thread.start()

    return render_template(
        "results_visual.html",
        task_id=task_id,
        folder=folder_encoded,
        filename=file_name,
    )


def send_emails(folder, task_id):
    with app.app_context():
        success = os.path.join(folder, "success_mail")
        failed = os.path.join(folder, "failed_mail")

        if not os.path.exists(success):
            os.makedirs(success)
        if not os.path.exists(failed):
            os.makedirs(failed)

        active = [user.ippis for user in ActiveUser.query.all()]
        files_list = [file for file in os.listdir(
            folder) if file.endswith(".pdf")]
        files = [file for file in files_list if file.split("_")[0] in active]

        progress_data[task_id]["total"] = len(files)

        for file in files:
            if progress_data[task_id]["status"] == "canceled":
                break
            ippis = file.split("_")[0]
            user = User.query.filter_by(ippis=ippis).first()
            email = user.email
            matched_path = os.path.join(folder, file)

            mail_att, error_message = send_email_with_attachment(
                email, ippis, file, matched_path
            )

            full_path = os.path.join(folder, file)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            log_entry = {
                "timestamp": timestamp,
                "message": (
                    error_message
                    if mail_att
                    else f"Email notification failed to {email}."
                ),
                "file": file,
                "email": email,
            }
            progress_data[task_id]["logs"].append(log_entry)

            if mail_att:
                sh.move(full_path, success)
                progress_data[task_id]["sent"] += 1
            else:
                sh.move(full_path, failed)
                progress_data[task_id]["failed"] += 1
                progress_data[task_id]["errors"].append(
                    {
                        "file": file,
                        "email": email,
                        "error": error_message,
                        "timestamp": timestamp,
                    }
                )

        progress_data[task_id]["completed"] = True


@app.route("/progress_mail/<task_id>/")
def progress_mail(task_id):
    return jsonify(
        progress_data.get(
            task_id, {"total": 0, "sent": 0,
                      "failed": 0, "logs": [], "errors": []}
        )
    )


@app.route("/retry_page/", methods=["GET", "POST"])
def retry_page():
    folder = request.form.get("folder") or request.args.get("folder")
    task_id = request.form.get("task_id") or request.args.get("task_id")
    filename = request.form.get("filename") or request.args.get("filename")
    return render_template(
        "retry_page.html", task_id=task_id, folder=folder, filename=filename
    )


@app.route("/retry_logs/", methods=["GET"])
def retry_logs():
    task_id = request.args.get("task_id")
    page = int(request.args.get("page", 1))
    per_page = 20
    start = (page - 1) * per_page
    end = start + per_page
    logs_paginated = progress_data[task_id]["logs"][start:end]
    total = len(progress_data[task_id]["logs"])
    out_of = math.ceil(total / per_page)
    out_of = out_of if out_of != 0 else 1
    return jsonify(logs=logs_paginated, total=total, n_logs=out_of)


@app.route("/retry_errors/", methods=["GET"])
def retry_errors():
    task_id = request.args.get("task_id")
    page = int(request.args.get("page", 1))
    per_page = 15
    start = (page - 1) * per_page
    end = start + per_page
    errors_paginated = progress_data[task_id]["errors"][start:end]
    total = len(progress_data[task_id]["errors"])
    out_of = math.ceil(total / per_page)
    out_of = out_of if out_of != 0 else 1
    return jsonify(errors=errors_paginated, total=total, n_errors=out_of)


@app.route("/retry_send_mail/", methods=["GET", "POST"])
@login_required
def retry_send_mail():
    if request.method == "POST":
        folder = unquote(request.form["folder"])
    else:
        folder = request.args.get("folder")

    if not folder:
        flash("No folder provided for retry_send_mail", "error")
        return redirect(url_for("directories", rel_directory='base_dir'))

    task_id = str(time.time())  # Generate a unique task ID
    failed_folder = os.path.join(folder, "failed_mail")
    file_name = Path(folder).name

    progress_data[task_id] = {
        "logs": [],
        "errors": [],
        "status": "running",
        "total": 0,
        "sent": 0,
        "failed": 0,
        "completed": False,
        "cancelled": False,
    }

    # Run the email sending function in the background
    # Start a background thread to handle the email sending process
    thread = Thread(target=retry_send_emails, args=(
        folder, task_id, failed_folder))
    thread.start()

    return render_template(
        "results_visual.html", task_id=task_id, folder=quote(folder), filename=file_name
    )


def retry_send_emails(main_folder, task_id, failed_folder):
    with app.app_context():
        db_found = User.query.all()
        active_found, inactive, unknown = query_string(main_folder, db_found)

        files_list = [file for file in os.listdir(
            main_folder) if file.endswith(".pdf")]
        files_new = [file for file in files_list if file.split("_")[
            0] in active_found]

        files_failed = [
            file for file in os.listdir(failed_folder) if file.endswith(".pdf")
        ]

        files = files_failed + files_new

        progress_data[task_id]["total"] = len(files)

        for file in files:
            if progress_data[task_id]["status"] == "canceled":
                break
            user_id = file.split("_")[0]
            user = User.query.filter_by(ippis=user_id).first()
            email = user.email

            full_path = os.path.join(failed_folder, file)

            matched_path = (
                full_path
                if os.path.exists(full_path)
                else os.path.join(main_folder, file)
            )

            mail_att, error_message = send_email_with_attachment(
                email, user_id, file, matched_path
            )

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            log_entry = {
                "timestamp": timestamp,
                "message": (
                    error_message
                    if mail_att
                    else f"Email notification failed to {email}."
                ),
                "file": file,
                "email": email,
            }
            progress_data[task_id]["logs"].append(log_entry)

            if mail_att:
                sh.move(matched_path, os.path.join(
                    main_folder, "success_mail", file))
                progress_data[task_id]["sent"] += 1
            else:
                progress_data[task_id]["failed"] += 1
                progress_data[task_id]["errors"].append(
                    {
                        "file": file,
                        "email": email,
                        "error": error_message,
                        "timestamp": timestamp,
                    }
                )

        progress_data[task_id]["completed"] = True


@app.route("/cancel_task/", methods=["POST"])
def cancel_task():
    try:
        task_id = request.form["task_id"]
        folder = request.form["folder"]
        filename = request.form["filename"]

        if task_id in progress_data:
            progress_data[task_id]["cancelled"] = True
            progress_data[task_id]["status"] = "canceled"
            return jsonify(
                {
                    "status": "Task canceled",
                    "redirect": url_for(
                        "retry_page",
                        task_id=task_id,
                        folder=folder,
                        filename=filename
                    ),
                }
            )
    except KeyError:
        flash("No task ID provided", "error")
        return redirect(url_for("directories", rel_directory='base_dir'))


@app.route("/export_logs/", methods=["POST", "GET"])
def export_logs():
    task_id = request.form.get("task_id")

    def generate_csv(data, columns):
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    logs_csv = generate_csv(
        [
            {
                "timestamp": log["timestamp"],
                "message": log["message"],
                "file": log["file"],
                "email": log["email"],
            }
            for log in progress_data[task_id]["logs"]
        ],
        ["timestamp", "message", "file", "email"],
    )
    errors_csv = generate_csv(
        [
            {
                "timestamp": error["timestamp"],
                "file": error["file"],
                "email": error["email"],
                "error": error["error"],
            }
            for error in progress_data[task_id]["errors"]
        ],
        ["timestamp", "file", "email", "error"],
    )

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("logs.csv", logs_csv)
        zip_file.writestr("errors.csv", errors_csv)
    zip_buffer.seek(0)

    timedate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    flash(f"Saving to logs_and_errors_{timedate}.zip", 'success')

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"logs_and_errors_{timedate}.zip",
    )


@app.route("/add_user/", methods=["GET", "POST"])
@login_required
def add_user():
    if request.method != "POST":
        return render_template("add_user.html", title="Add User")
    
    try:
        email = request.form.get("email")
        ippis = request.form.get("ippis")
        first_name = request.form.get("first_name")
        surname = request.form.get("surname")
        phone = request.form.get("phone")
        active = "active" in request.form

        new_user = User(
            email=email,
            ippis=ippis,
            first_name=first_name,
            surname=surname,
            phone=phone,
            active=active,
        )
        db.session.add(new_user)
        db.session.commit()

        flash(f"User {email} added successfully.", "success")
        
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
        
    return redirect(url_for('manage_users'))


@app.route("/remove_user/", methods=["GET", "POST"])
@login_required
def remove_user():
    try:
        email = request.form.get("email")
        ippis = request.form.get("ippis")

        user = User.query.filter_by(email=email).first()
        if not user and user.ippis != ippis:
            raise AssertionError(f"User {email} not found.")

        db.session.delete(user)
        db.session.commit()

        flash(f"User {email} removed successfully.", "success")
        
    except Exception as e:
        flash(f"{str(e)}", "error")
        
    return redirect(url_for('manage_users'))


@app.route("/add_admin/", methods=["GET", "POST"])
@login_required
def add_admin():
    if request.method != "POST":
        return render_template("add_admin.html", title="Add Admin")
    
    try:
        user = request.form.get("name")
        password = request.form.get("passwd")
        confirm_password = request.form.get("confirm")

        if password != confirm_password:
            flash("Passwords do not match", "error")
            raise AssertionError("Passwords do not match")

        new_user = Admins()
        new_user.username = user.lower()
        new_user.password = password

        db.session.add(new_user)
        db.session.commit()

        flash(f"Admin {new_user.username} added successfully.", "success")
        
    except Exception as e:
        flash(f"{str(e)}", "error")
        
    return redirect(url_for('manage_admins'))


@app.route("/remove_admin/", methods=["GET", "POST"])
@login_required
def remove_admin():
    try:
        user = request.form.get("admin")

        user = Admins.query.filter_by(username=user).first()
        if not user:
            raise AssertionError("User not found")
        
        if user.username == session.get('username'):
            raise AssertionError("cannot delete logged in Administrator")

        db.session.delete(user)
        db.session.commit()

        flash(f"Admin {user.username} removed successfully.", "success")
        return redirect(url_for("manage_admins"))
    
    except Exception as e:
        flash(f"{str(e)}", "error")
        
    return redirect(url_for("manage_admins"))


@app.route('/admin_control/', methods=['GET'])
@login_required
def admin_control():
    return render_template('admin_control.html')


@app.route('/manage_users/', methods=['GET'])
@login_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    per_page = 100  # Number of users per page
    users = User.query.paginate(page=page, per_page=per_page)
    total_users = User.query.count()
    return render_template('manage_users.html',
                           users=users.items,
                           pagination=users,
                           total_users=total_users)


@app.route('/manage_admins/', methods=['GET', 'POST'])
@login_required
def manage_admins():    
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of admins per page
    total_admins = Admins.query.count()
    admins = Admins.query.paginate(page=page, per_page=per_page)
    
    if request.method == 'POST':
        admin_id = request.form.get('admin_id')
        new_password = request.form.get('new_password')
        admin = Admins.query.get(admin_id)
        if admin and new_password:
            admin.password = new_password
            db.session.commit()
            flash('Password changed successfully', 'success')
        else:
            flash('Failed to change password', 'error')
    return render_template('manage_admins.html',
                           admins=admins.items, 
                           pagination=admins, 
                           total_admins=total_admins
                           )


@app.route('/change_pswd/', methods=['POST', 'GET'])
@login_required
def change_pswd():
    if request.method == 'POST':
        try:
            user = request.form.get('admin_username') 
            old_pswd = request.form.get('old_password')
            pswd = request.form.get('new_password')
            
            admin_user = Admins.query.filter_by(username=user).first()
            if admin_user and admin_user.verify_password(old_pswd):
                admin_user.password = pswd
                flash(f'Successfully changed password for {user}', 'success')
                
                db.session.commit()
                
            else:
                flash(f'{user} not found')
        except Exception as e:
            flash(str(e), 'error')
            
    return redirect(url_for('manage_admins'))


if __name__ == "__main__":
    app.run()
