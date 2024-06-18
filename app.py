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
    """
    This class defines the User model with attributes for user information and activity status.

    Attributes:
        id (int): Primary key for the user, auto-increments.
        ippis (str): IPPIS number of the user (unique, not null).
        email (str): Email address of the user (unique, not null).
        first_name (str): User's first name (nullable).
        surname (str): User's surname (nullable).
        phone (str): User's phone number (nullable).
        active (bool): Flag indicating if the user is active (default: False).
    """
       
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ippis = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    surname = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(100), nullable=True)
    active = db.Column(db.Boolean, default=False)

    def __init__(self, email, ippis, first_name, surname, phone, active=False):
        """
        Initializes a new User object with the provided data.

        Args:
            email (str): The user's email address.
            ippis (str): The user's IPPIS number.
            first_name (str, optional): User's first name (defaults to None).
            surname (str, optional): User's surname (defaults to None).
            phone (str, optional): User's phone number (defaults to None).
            active (bool, optional): Flag indicating if the user is active (defaults to False).
        """
        
        self.email = email
        self.ippis = ippis
        self.first_name = first_name
        self.surname = surname
        self.phone = phone
        self.active = active


class ActiveUser(db.Model):
    """
    Represents a user categorized as active based on processing results.

    Attributes:
        id (int): Primary key for the record.
        ippis (str): IPPIS number of the active user (not null).
    """
    
    __tablename__ = "active"
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class InactiveUser(db.Model):
    """
    Represents a user categorized as inactive based on processing results.

    Attributes:
        id (int): Primary key for the record.
        ippis (str): IPPIS number of the inactive user (not null).
    """
    
    __tablename__ = "inactive_users"
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class UnknownUser(db.Model):
    """
    Represents a user whose status is unknown based on processing results.

    Attributes:
        id (int): Primary key for the record.
        ippis (str): IPPIS number of the unknown user (not null).
    """
    __tablename__ = "unknown_users"
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class Admins(db.Model):
    """
    Represents an administrator user with login credentials.

    Attributes:
        id (int): Primary key for the admin record, auto-increments.
        username (str): Username for admin login (unique, not null).
        password_hash (str): Hashed password for secure storage (not null).
    """
    
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(20), nullable=False)

    @property
    def password(self):
        """
        Password attribute is read-only for security purposes, attempting to access it raises an error.
        """
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        """
         Sets the password to be used for authenticating. This is a string of length 256 and should be used in conjunction with the : meth : ` password_hash ` method
        """
        self.password_hash = generate_password_hash(str(password))

    def verify_password(self, password):
        """
         Verify a password against the hash. This is used to verify the user's password before logging in to the system
         
         Args:
         	 password: The password to verify.
         
         Returns: 
         	 True if the password matches the hash False otherwise. Note that a return value of False does not mean that the password was not correct
        """
        return check_password_hash(self.password_hash, str(password))


app.jinja_env.filters["format_file_size"] = format_file_size
app.jinja_env.filters["datetimeformat"] = datetimeformat


def login_required(route):
    """
    Decorator that restricts access to a route for logged-in users only.

    This decorator checks if a username is present in the session data. If not, it flashes an error message indicating the user needs to log in and redirects them to the login page. If a username is found, it retrieves the corresponding Admin user object from the database using SQLAlchemy. If the user is not found, it also flashes an error message and redirects to the login page. Otherwise, the original route function is called, allowing access to the protected route.

    Args:
        route (function): The route function to be decorated.

    Returns:
        function: The decorated route function.
    """
    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        """
        Wrapper function that performs the login check and redirection.

        This function checks the session for a username and retrieves the corresponding Admin user if found. If not logged in or user not found, it displays an error message and redirects to login. Otherwise, it calls the original route function with the provided arguments.

        Args:
            *args: Arguments passed to the decorated route function.
            **kwargs: Keyword arguments passed to the decorated route function.

        Returns:
            The return value of the decorated route function.
        """
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
    """
    Login route for admins.

    This route handles both GET and POST requests for the login functionality.

    GET requests:
        - Renders the "login.html" template with the title "Login-Form".

    POST requests (form submission):
        - Retrieves username (converted to lowercase) and password from the form data.
        - Queries the database for an Admin user with the provided username using `Admins.query.filter_by`.
        - If a user is found and the password matches (verified using `user.verify_password(password)`):
            - Flashes a success message indicating successful login.
            - Stores the username in the session for future reference.
            - Redirects the user to the `/directories` route, passing a default directory (`base_dir`) as an argument.
        - If the username or password is incorrect, it flashes an error message and re-renders the login template.
    
    """
        
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
    """
    Logout route for admins.

    This route handles POST requests for logging out a user.

    - Removes the username key from the session using `session.pop('username', None)`.
    - Flashes a success message indicating successful logout.
    - Redirects the user back to the login page (`/login`).
    """
    session.pop('username', None)  # Remove username from session
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))


@app.route("/upload/", methods=["POST"])
@login_required
def upload():
    """
    Uploads a file submitted through a POST request.

    This route handles file uploads. It expects a file named "file" to be included in the request data.

    Args:
        request (flask.Request): The incoming request object.

    Returns:
        flask.Response: A redirect response to the directories route
            with a success or error message depending on the upload outcome.

    Raises:
        KeyError: If the request doesn't contain a file named "file".
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
    """
    Displays a paginated list of files in the specified directory.

    This route handles both GET and POST requests for browsing directories.

    GET requests:
        - Retrieves the relative directory path from the query string parameter "rel_directory".
        - Defaults to "base_dir" if no directory is specified.

    POST requests:
        - Retrieves the relative directory path and page number from the request form.

    Args:
        request (flask.Request): The incoming request object.

    Returns:
        flask.Response: The rendered directories.html template with file listing
            and pagination information.
    """
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
    """
    Initiates the process of splitting and encrypting a file uploaded through a POST request.

    This route handles file splitting and encryption requests. It expects a file path
    to be submitted in the request form under the key "file".

    Args:
        request (flask.Request): The incoming request object.

    Returns:
        flask.Response: The rendered progress.html template with a unique task ID
            and encoded folder path for progress tracking.

    Raises:
        Exception: If an error occurs during file processing.
    """
    try:
        task_id = str(time.time())  # Generate a unique task ID
        progress[task_id] = 0  # Initialize progress
        
        file = request.form.get("file")
        file = Path(file)
        filename = str(file.name).split(".", maxsplit=1)[0]
        file_path = os.path.join(base_dir, filename)        
        
        folder_encoded = quote(file_path)            

        # Run the splitter function in a separate thread for asynchronous processing.
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
    """
    Provides the progress status for a split and encrypt task identified by its task ID.

    This route retrieves the progress information associated with a specific task ID
    from the `progress` dictionary.

    Args:
        task_id (str): The unique identifier for the split and encrypt task.

    Returns:
        flask.json. jsonify: A JSON response containing the progress value (integer).
    """
    return jsonify({"progress": progress.get(task_id, 0)})


@app.route("/query_db/", methods=["GET", "POST"])
@login_required
def query_db():
    """
    Handles form submissions for database queries related to a specific folder.

    This route expects a folder path to be submitted in the request form under the key "folder".

    Args:
        request (flask.Request): The incoming request object.

    Returns:
        flask.Response:
            - A redirect to the directories route with an error message if no folder path is provided.
            - The rendered query_db.html template with the decoded folder path
              for further database interaction if a folder path is provided.
    """
    folder = request.form.get("folder")
    if not folder:
        return redirect(url_for("directories", rel_directory='base_dir'))

    folder = unquote(folder)
    return render_template("query_db.html", folder=folder)


@app.route("/results/", methods=["GET", "POST"])
@login_required
def results():
    """
    Processes user data for a specified folder and displays categorization results.

    This route handles form submissions from the query_db.html page. It expects a folder path
    encoded as "folder" in the request form.

    Args:
        request (flask.Request): The incoming request object.

    Returns:
        flask.Response: The rendered results.html template with user categorization
            counts and the folder path.

    Raises:
        KeyError: If the request doesn't contain the "folder" key.
    """    
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
    """
    Displays a paginated list of users for a specified category.

    This route handles GET and POST requests for viewing users categorized as active,
    inactive, or unknown. It retrieves users based on the provided category and
    supports pagination for large datasets.

    Args:
        request (flask.Request): The incoming request object.
        category (str): The user category ("active", "inactive", or "unknown").

    Returns:
        flask.Response: The rendered view_users.html template with user list and pagination.

    Raises:
        ValueError: If an invalid category is provided.
    """
 
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
    """
    Renders the results.html template with previously stored user category counts and folder path.

    This route serves as a "back" button functionality, retrieving user category counts
    (active, inactive, unknown) and folder path from session variables set in the `results`
    route. It then renders the `results.html` template with this information.

    Returns:
        flask.Response: The rendered results.html template with previously stored user
            category counts and folder path.
    """
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
    """
    Initiates the process of sending emails for users in a specified folder asynchronously.

    This route handles POST requests to send email notifications to users
    with attached PDFs. It retrieves the folder path from the request form,
    generates a unique task ID for progress tracking, and initializes a dictionary
    `progress_data` to store task information (logs, errors, status, counts).

    Args:
        request (flask.Request): The incoming request object.

    Returns:
        flask.Response: The rendered results_visual.html template with task ID,
            encoded folder path, and filename for progress visualization.
    """
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
    """
    Sends emails with attachments to users listed in the specified folder.

    This function runs in a separate thread and performs the following steps:
        1. Defines paths for success and failed email folders within the given folder.
        2. Creates the folders if they don't exist.
        3. Retrieves a list of active users' IPPIS from the database.
        4. Filters files within the folder based on active users' IPPIS.
        5. Iterates through each file, sending an email with the attachment to the
           corresponding user. Updates progress data and logs based on success/failure.
        6. Marks the task as completed in `progress_data`.

    Args:
        folder (str): The path to the folder containing email attachments.
        task_id (str): The unique identifier for the email sending task.

    Raises:
        Exception: If an error occurs during email sending or file operations.
    """
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
    """
    Provides progress information for an email sending task identified by its task ID.

    This route retrieves the progress data associated with a specific task ID
    from the `progress_data` dictionary. It returns a JSON response containing
    information like total emails, sent emails, failed emails, logs, and errors.

    Args:
        task_id (str): The unique identifier for the email sending task.

    Returns:
        flask.json. jsonify: A JSON response containing the progress data for the task.

    Raises:
        KeyError: If the `task_id` is not found in the `progress_data` dictionary.
    """

    return jsonify(
        progress_data.get(
            task_id, {"total": 0, "sent": 0,
                      "failed": 0, "logs": [], "errors": []}
        )
    )


@app.route("/retry_page/", methods=["GET", "POST"])
def retry_page():
    """
    Renders the retry_page.html template for retrying a failed email notification.

    This route handles both GET and POST requests to display a retry page.
    It retrieves the folder path, task ID, and filename from the request form or arguments.
    These values are then used to populate the retry_page.html template.

    Returns:
        flask.Response: The rendered retry_page.html template with task ID, folder path,
            and filename for retrying a failed email notification.
    """
    folder = request.form.get("folder") or request.args.get("folder")
    task_id = request.form.get("task_id") or request.args.get("task_id")
    filename = request.form.get("filename") or request.args.get("filename")
    return render_template(
        "retry_page.html", task_id=task_id, folder=folder, filename=filename
    )


@app.route("/retry_logs/", methods=["GET"])
def retry_logs():
    """
    Provides paginated access to email sending task logs for a specified task ID.

    This route retrieves logs associated with an email sending task from the
    `progress_data` dictionary. It supports pagination by accepting a page number
    as a query argument. The route returns a JSON response containing the requested
    page of logs, total number of logs, and total number of log pages.

    Args:
        task_id (str): The unique identifier for the email sending task.

    Returns:
        flask.json. jsonify: A JSON response containing paginated email sending task logs,
            total log count, and total number of log pages.
    """
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
    """
    Provides paginated access to email sending task errors for a specified task ID.

    This route retrieves errors associated with an email sending task from the
    `progress_data` dictionary. It supports pagination by accepting a page number
    as a query argument. The route returns a JSON response containing the requested
    page of errors, total number of errors, and total number of error pages.

    Args:
        task_id (str): The unique identifier for the email sending task.

    Returns:
        flask.json. jsonify: A JSON response containing paginated email sending task errors,
            total error count, and total number of error pages.
    """
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
    """
    Retries sending emails that previously failed for a specified task.

    This function reattempts sending emails associated with a task identified by
    `task_id`. It retrieves active users and failed email filenames. It then
    processes both new and failed email files:

    1. Combines new email files (from the main folder) with failed email files.
    2. Iterates through each file, prioritizing new files.
        - Checks for cancellation status in `progress_data`.
        - Retrieves user information and email address based on filename.
        - Attempts to send the email with an attachment.
        - Updates progress data (logs, errors, counts) based on success/failure.
        - Moves successful files to the "success_mail" folder within the main folder.

    3. Marks the task as completed in `progress_data`.

    Args:
        main_folder (str): The path to the main folder containing email attachments.
        task_id (str): The unique identifier for the email sending task.
        failed_folder (str): The path to the folder containing failed email attachments.

    Raises:
        Exception: If an error occurs during email sending or file operations.
    """
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
    """Cancels an email sending task by task ID.

    - Retrieves task ID, folder, and filename from request form.
    - Cancels task if ID exists in `progress_data`.
    - Returns JSON with cancellation status and retry page redirect URL.

    Raises:
        KeyError: If task ID is not found.
    """
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
    """
    Exports email sending task logs and errors as a ZIP archive.

    - Retrieves task ID from the request form.
    - Generates CSV data for logs and errors from `progress_data`.
    - Creates a ZIP archive containing logs.csv and errors.csv.
    - Flashes a success message with the filename.
    - Returns the ZIP archive for download.

    Raises:
        KeyError: If the task ID is not found in `progress_data`.
    """
    task_id = request.form.get("task_id")

    def generate_csv(data, columns):
        """
        Generates CSV data for logs and errors from task data.

        - Takes task data dictionary as input.
        - Returns separate lists of dictionaries for logs and errors
        formatted for CSV generation.
    """
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
    """
    Adds a new user to the database.

    - Handles GET and POST requests.
    - Renders the "add_user.html" template for GET requests.
    - Validates and adds user data to the database on POST requests.
    - Flashes success or error messages based on the outcome.
    - Redirects to the "manage_users" page after processing.
    """
    if request.method != "POST":
        return render_template("add_user.html", title="Add User")
    
    try:
        # ... user data retrieval and processing ...

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
    """Removes a user from the database.

    - Handles GET and POST requests.
    - Retrieves user email or IPPIS from the request form.
    - Queries the database for the user.
    - Deletes the user if found, otherwise raises an exception.
    - Flashes success or error messages based on the outcome.
    - Redirects to the "manage_users" page after processing.
    """
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
    """Creates a new administrator account.

    - Renders "add_admin.html" template on GET requests.
    - Validates and creates a new `Admins` object on POST requests.
    - Hashes and stores the password securely.
    - Flashes success or error messages based on the outcome.
    - Redirects to "manage_admins" page after processing.
    """
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
    """Removes an administrator from the system.

    - Handles GET and POST requests.
    - Retrieves admin username from the request form.
    - Queries the database for the admin.
    - Prevents deleting the currently logged-in admin.
    - Deletes the admin and flashes success message if found.
    - Flashes error message and redirects if admin not found.
    """
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
    """Renders the admin control panel template."""
    return render_template('admin_control.html')


@app.route('/manage_users/', methods=['GET'])
@login_required
def manage_users():
    """Presents a paginated list of all users."""
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
    """Manages administrator accounts.

    - Lists admins with pagination.
    - Allows changing admin password on POST requests.
    - Flashes success or error messages based on outcome.
    """   
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
    """Allows admins to change their password.

    - Handles password change requests on POST.
    - Validates current password and updates new password securely.
    - Flashes success or error messages based on outcome.
    - Redirects to admin management page after processing.
    """
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
