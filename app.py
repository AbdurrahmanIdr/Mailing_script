import csv
import datetime
import functools
import math
import os
import shutil as sh
import time
import zipfile
from io import (BytesIO,
                StringIO)
from pathlib import Path
from secrets import token_urlsafe
from threading import Thread
from urllib.parse import (quote,
                          unquote)

from flask import (Flask,
                   render_template,
                   url_for,
                   request,
                   redirect,
                   jsonify,
                   session,
                   flash,
                   send_file)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import (generate_password_hash,
                               check_password_hash)

from models.explorer import (get_sorted_files,
                             get_file_info,
                             format_file_size,
                             datetimeformat,
                             query_string)
from models.mail_mod import (send_email_with_attachment,
                             progress_data)
from models.pdf_rel import (splitter,
                            base_dir,
                            progress)

app = Flask(__name__)
app.secret_key = token_urlsafe(32)
db_path = os.path.abspath('db.sqlite')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)
progress = progress


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ippis = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
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
    __tablename__ = 'active'
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class InactiveUser(db.Model):
    __tablename__ = 'inactive_users'
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class UnknownUser(db.Model):
    __tablename__ = 'unknown_users'
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class Admins(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(20), nullable=False)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(str(password))

    def verify_password(self, password):
        return check_password_hash(self.password_hash, str(password))


# def init_migration():
#     with app.app_context():
#         if not os.path.exists('migrations'):
#             os.system('flask db init')
#         os.system('flask db migrate -m "migrations"')
#         os.system('flask db upgrade')


# init_migration()
app.jinja_env.filters['format_file_size'] = format_file_size
app.jinja_env.filters['datetimeformat'] = datetimeformat


def login_required(route):
    with app.app_context():
        users = [user.username for user in User.query.all()]

    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        if 'username' not in session and session.get('username') not in users:
            flash('User not found in the session or db')
            redirect(url_for('login'))
        return route(*args, **kwargs)

    return wrapper


@app.route('/')
@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = Admins.query.filter_by(username=username).first()

        if user and user.verify_password(password):
            flash(f'{username} login successfully.', 'success')
            session['username'] = username
            return redirect(url_for('directories'))

        flash(f'username or password is incorrect, try again.', 'error')

    return render_template('login.html', title='Login-Form')


@app.route("/upload/", methods=['POST'])
def upload():
    file = request.files.get('file')
    filename = str(file.filename)

    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    if file and filename != '':
        full_path = os.path.join(base_dir, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
        file.save(full_path)
        flash(f'{file.filename} saved successfully.', 'success')

    else:
        flash(f'{file.filename} failed to upload check the file type != PDF', 'error')

    return redirect(url_for('directories'))


@login_required
@app.route('/directories/<rel_directory>/', methods=['GET', 'POST'])
def directories(rel_directory=base_dir):
    """
       Render the home page or directory listing page.

       Args:
           rel_directory (str): Relative path of the directory.

       Returns:
           render_template: Rendered HTML template.
       """
    if os.path.isdir(rel_directory):
        files, current_directory = get_sorted_files(rel_directory)
        return render_template('directories.html', title='Directories',
                               files=files, current_directory=current_directory)


@app.route('/view_file/<path:filepath>/', methods=['GET', 'POST'])
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
        flash(f"The file '{file_path}' does not exist.", 'error')
        return redirect(request.url)

    file_info = get_file_info(file_path)

    # Handle POST request to retrieve file path
    if request.method == 'POST':
        # Logic to retrieve the file path goes here
        file_path_to_display = str(file_path)

        # Render the template with the file path to display
        return render_template('view_file.html',
                               file_path=file_path.resolve(),
                               file_info=file_info,
                               file_path_to_display=file_path_to_display)

    # Render the template for a regular GET request
    return render_template('view_file.html',
                           title='View File',
                           file_path=file_path.resolve(),
                           file_info=file_info)


@app.route('/delete_file_or_directory/', methods=['POST'])
def delete_file_or_directory():
    if request.method == 'POST':
        path = request.form.get('path')
        current_directory = request.form.get('current_directory')  # Retrieve current directory from form data
        current_directory = Path(current_directory)

        try:
            if os.path.exists(path):
                if os.path.isfile(path):
                    os.remove(path)
                    flash('File deleted successfully!', 'success')
                elif os.path.isdir(path):
                    sh.rmtree(path)
                    flash('Directory deleted successfully!', 'success')
            else:
                flash('File or directory does not exist.', 'error')
        except Exception as e:
            flash(f'An error occurred while deleting the file/directory.\n{e}', 'error')

        return redirect(url_for('directories',
                                rel_directory=current_directory))


@app.route('/retrieve_selected_path/', methods=['POST'])
def retrieve_selected_path():
    """
        Render the page with retrieved selected file paths.

        Returns:
            render_template: Rendered HTML template.
        """
    selected_file = request.form.get('selected_file')
    if os.path.isdir(selected_file):
        files = os.listdir(selected_file)
        if 'success_mail' in files and 'failed_mail' in files:
            return redirect(url_for('retry_send_mail',
                                    folder=selected_file))

        return render_template('query_db.html',
                               folder=selected_file,
                               title='Query DB')

    elif os.path.isfile(selected_file):
        return render_template('split_enc.html',
                               selected_file=selected_file,
                               title='Split Encrypt')


@app.route('/split_encrypt/', methods=['POST'])
def split_encrypt():
    try:
        file = request.form.get('file')
        task_id = str(time.time())  # Generate a unique task ID
        progress[task_id] = 0  # Initialize progress
        file_path = os.path.join(base_dir, file.split('.')[0])
        folder_encoded = quote(file_path)

        # Run the splitter function in the background
        thread = Thread(target=splitter, args=(file, task_id))
        thread.start()

        return render_template('progress.html',
                               task_id=task_id,
                               folder=folder_encoded)
    except Exception as e:
        flash(f'An error occurred while splitting the file.\n{e}', 'error')
        return redirect(url_for('directories'))


@app.route('/progress/<task_id>')
def progress_status(task_id):
    return jsonify({'progress': progress.get(task_id, 0)})


@app.route('/query_db/', methods=['POST'])
def query_db():
    folder = request.form['folder']
    if not folder:
        return redirect(request.url)

    folder = unquote(folder)
    return render_template('query_db.html', folder=folder)


@app.route('/results/', methods=['POST'])
def results():
    folder_encoded = request.form.get('folder')
    if not folder_encoded:
        return redirect(url_for('index'))

    folder = unquote(folder_encoded)
    db_found = User.query.all()

    active_found, inactive, unknown = query_string(folder, db_found)

    ActiveUser.query.delete()
    InactiveUser.query.delete()
    UnknownUser.query.delete()

    db.session.bulk_insert_mappings(ActiveUser, [{'ippis': ippis} for ippis in active_found])
    db.session.bulk_insert_mappings(InactiveUser, [{'ippis': ippis} for ippis in inactive])
    db.session.bulk_insert_mappings(UnknownUser, [{'ippis': ippis} for ippis in unknown])
    db.session.commit()

    session['folder'] = folder_encoded
    session['active_count'] = len(active_found)
    session['inactive_count'] = len(inactive)
    session['unknown_count'] = len(unknown)

    return render_template('results.html',
                           active=len(active_found),
                           inactive=len(inactive),
                           unknown=len(unknown),
                           folder=folder)


@app.route('/view_users/<category>/', methods=['GET', 'POST'])
def view_users(category):
    if category == 'active':
        users = ActiveUser.query.all()
    elif category == 'inactive':
        users = InactiveUser.query.all()
    elif category == 'unknown':
        users = UnknownUser.query.all()
    else:
        flash('Category does not exist.', 'error')
        return redirect(url_for('directories'))

    return render_template('view_users.html',
                           category=category,
                           users=users)


@app.route('/back_to_result/')
def back_to_result():
    folder = unquote(session['folder'])
    active = session['active_count']
    inactive = session['inactive_count']
    unknown = session['unknown_count']

    return render_template('results.html',
                           active=active,
                           inactive=inactive,
                           unknown=unknown,
                           folder=folder)


@app.route('/send_mail/', methods=['POST'])
def send_mail():
    folder = request.form.get('folder')
    task_id = str(time.time())  # Generate a unique task ID
    progress_data[task_id] = {
        'logs': [],
        'errors': [],
        'status': 'running',
        'total': 0,
        'sent': 0,
        'failed': 0,
        'completed': False,
        'cancelled': False
    }

    file_name = Path(folder).name
    folder_encoded = quote(folder)

    # Run the email sending function in the background
    thread = Thread(target=send_emails, args=(folder, task_id))
    thread.start()

    return render_template('results_visual.html',
                           task_id=task_id,
                           folder=folder_encoded,
                           filename=file_name)


def send_emails(folder, task_id):
    with app.app_context():
        success = os.path.join(folder, 'success_mail')
        failed = os.path.join(folder, 'failed_mail')

        if not os.path.exists(success):
            os.makedirs(success)
        if not os.path.exists(failed):
            os.makedirs(failed)

        active = [user.ippis for user in ActiveUser.query.all()]
        files_list = [file for file in os.listdir(folder) if file.endswith('.pdf')]
        files = [file for file in files_list if file.split('_')[0] in active]

        progress_data[task_id]['total'] = len(files)

        for file in files:
            if progress_data[task_id]['status'] == 'canceled':
                break
            ippis = file.split('_')[0]
            user = User.query.filter_by(ippis=ippis).first()
            email = user.email
            matched_path = os.path.join(folder, file)

            mail_att, error_message = send_email_with_attachment(email, ippis, file, matched_path)

            full_path = os.path.join(folder, file)
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            log_entry = {
                'timestamp': timestamp,
                'message': error_message if mail_att
                else f"Email notification failed to {email} for user ID {ippis}.",
                'file': file,
                'email': email,
            }
            progress_data[task_id]['logs'].append(log_entry)

            if mail_att:
                sh.move(full_path, success)
                progress_data[task_id]['sent'] += 1
            else:
                sh.move(full_path, failed)
                progress_data[task_id]['failed'] += 1
                progress_data[task_id]['errors'].append({
                    'file': file,
                    'email': email,
                    'error': error_message,
                    'timestamp': timestamp,
                })

        progress_data[task_id]['completed'] = True


@app.route('/progress_mail/<task_id>/')
def progress_mail(task_id):
    return jsonify(progress_data.get(task_id,
                                     {'total': 0,
                                      'sent': 0,
                                      'failed': 0,
                                      'logs': [],
                                      'errors': []}))


@app.route('/retry_page/', methods=['GET', 'POST'])
def retry_page():
    folder = request.form.get('folder') or request.args.get('folder')
    task_id = request.form.get('task_id') or request.args.get('task_id')
    filename = request.form.get('filename') or request.args.get('filename')
    return render_template('retry_page.html',
                           task_id=task_id,
                           folder=folder,
                           filename=filename)


@app.route('/retry_logs/', methods=['GET'])
def retry_logs():
    task_id = request.args.get('task_id')
    page = int(request.args.get('page', 1))
    per_page = 5
    start = (page - 1) * per_page
    end = start + per_page
    logs_paginated = progress_data[task_id]['logs'][start:end]
    total = len(progress_data[task_id]['logs'])
    out_of = math.ceil(total / per_page)
    out_of = out_of if out_of != 0 else 1
    return jsonify(logs=logs_paginated,
                   total=total,
                   n_logs=out_of)


@app.route('/retry_errors/', methods=['GET'])
def retry_errors():
    task_id = request.args.get('task_id')
    page = int(request.args.get('page', 1))
    per_page = 4
    start = (page - 1) * per_page
    end = start + per_page
    errors_paginated = progress_data[task_id]['errors'][start:end]
    total = len(progress_data[task_id]['errors'])
    out_of = math.ceil(total / per_page)
    out_of = out_of if out_of != 0 else 1
    return jsonify(errors=errors_paginated,
                   total=total,
                   n_errors=out_of)


@app.route('/retry_send_mail/', methods=['GET', 'POST'])
def retry_send_mail():
    if request.method == 'POST':
        folder = unquote(request.form['folder'])
    else:
        folder = request.args.get('folder')

    if not folder:
        flash("No folder provided for retry_send_mail", 'error')
        return redirect(url_for('directories'))

    task_id = str(time.time())  # Generate a unique task ID
    failed_folder = os.path.join(folder,
                                 'failed_mail')
    file_name = Path(folder).name

    progress_data[task_id] = {
        'logs': [],
        'errors': [],
        'status': 'running',
        'total': 0,
        'sent': 0,
        'failed': 0,
        'completed': False,
        'cancelled': False
    }

    # Run the email sending function in the background
    # Start a background thread to handle the email sending process
    thread = Thread(target=retry_send_emails, args=(folder,
                                                    task_id,
                                                    failed_folder))
    thread.start()

    return render_template('results_visual.html',
                           task_id=task_id,
                           folder=quote(folder),
                           filename=file_name)


def retry_send_emails(main_folder, task_id, failed_folder):
    with app.app_context():
        db_found = User.query.all()
        active_found, inactive, unknown = query_string(main_folder, db_found)

        files_list = [file for file in os.listdir(main_folder) if file.endswith('.pdf')]
        files_new = [file for file in files_list if file.split('_')[0] in active_found]

        files_failed = [file for file in os.listdir(failed_folder) if file.endswith('.pdf')]

        files = files_failed + files_new

        progress_data[task_id]['total'] = len(files)

        for file in files:
            if progress_data[task_id]['status'] == 'canceled':
                break
            user_id = file.split('_')[0]
            user = User.query.filter_by(ippis=user_id).first()
            email = user.email

            full_path = os.path.join(failed_folder,
                                     file)

            matched_path = full_path if os.path.exists(full_path) else os.path.join(main_folder,
                                                                                    file)

            mail_att, error_message = send_email_with_attachment(email,
                                                                 user_id,
                                                                 file,
                                                                 matched_path)

            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            log_entry = {
                'timestamp': timestamp,
                'message': error_message if mail_att
                else f"Email notification failed to {email} for user ID {user_id}.",
                'file': file,
                'email': email,
            }
            progress_data[task_id]['logs'].append(log_entry)

            if mail_att:
                sh.move(matched_path, os.path.join(main_folder,
                                                   'success_mail',
                                                   file))
                progress_data[task_id]['sent'] += 1
            else:
                progress_data[task_id]['failed'] += 1
                progress_data[task_id]['errors'].append({
                    'file': file,
                    'email': email,
                    'error': error_message,
                    'timestamp': timestamp,
                })

        progress_data[task_id]['completed'] = True


@app.route('/cancel_task/', methods=['POST'])
def cancel_task():
    try:
        task_id = request.form['task_id']
        folder = request.form['folder']
        filename = request.form['filename']

        if task_id in progress_data:
            progress_data[task_id]['cancelled'] = True
            progress_data[task_id]['status'] = 'canceled'
            return jsonify({'status': 'Task canceled',
                            'redirect': url_for('retry_page',
                                                task_id=task_id,
                                                folder=folder,
                                                filename=filename)})
    except KeyError:
        flash("No task ID provided", 'error')
        return redirect(url_for('directories'))


@app.route('/export_logs/', methods=['POST', 'GET'])
def export_logs():
    task_id = request.form.get('task_id')

    def generate_csv(data, columns):
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    logs_csv = generate_csv(
        [{'timestamp': log['timestamp'],
          'message': log['message'],
          'file': log['file'],
          'email': log['email']}

         for log in progress_data[task_id]['logs']],

        ['timestamp',
         'message',
         'file',
         'email']
    )
    errors_csv = generate_csv(
        [{'timestamp': error['timestamp'], 'file': error['file'], 'email': error['email'], 'error': error['error']}
         for error in progress_data[task_id]['errors']],
        ['timestamp', 'file', 'email', 'error']
    )

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('logs.csv', logs_csv)
        zip_file.writestr('errors.csv', errors_csv)
    zip_buffer.seek(0)

    timedate = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    flash(f'Saving to logs_and_errors_{timedate}.zip')

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'logs_and_errors_{timedate}.zip'
    )


@app.route("/add_user/", methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            ippis = request.form.get('ippis')
            first_name = request.form.get('first_name')
            surname = request.form.get('surname')
            phone = request.form.get('phone')
            active = 'active' in request.form

            new_user = User(email=email, ippis=ippis, first_name=first_name,
                            surname=surname, phone=phone, active=active)
            db.session.add(new_user)
            db.session.commit()

            flash(f'User {email} added successfully.', 'success')
            return redirect(url_for('directories'))
        except Exception as e:
            flash(f'{str(e)}', 'error')

    return render_template('add_user.html', title='Add User')


@app.route("/remove_user/", methods=['GET', 'POST'])
def remove_user():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            ippis = request.form.get('ippis')

            user = User.query.filter_by(email=email).first()
            if not user and user.ippis != ippis:
                raise AssertionError(f'User {email} not found.')

            db.session.delete(user)
            db.session.commit()

            flash(f'User {email} removed successfully.', 'success')
            return redirect(url_for('directories'))
        except Exception as e:
            flash(f'{str(e)}', 'error')

    return render_template('remove_user.html', title='Remove User')


@app.route("/add_admin/", methods=['GET', 'POST'])
def add_admin():
    if request.method == 'POST':
        try:
            user = request.form.get('name')
            password = request.form.get('passwd')
            confirm_password = request.form.get('confirm')

            if password != confirm_password:
                flash('Passwords do not match', 'error')
                raise AssertionError('Passwords do not match')

            new_user = Admins()
            new_user.username = user
            new_user.password = password

            db.session.add(new_user)
            db.session.commit()

            flash(f'Admin {new_user} added successfully.', 'success')
            return redirect(url_for('directories'))
        except Exception as e:
            flash(f'{str(e)}', 'error')

    return render_template('add_admin.html', title='Add Admin')


@app.route("/remove_admin/", methods=['GET', 'POST'])
def remove_admin():
    if request.method == 'POST':
        try:
            user = request.form.get('admin')

            user = Admins.query.filter_by(username=user).first()
            if not user:
                raise AssertionError('User not found')

            db.session.delete(user)
            db.session.commit()

            flash(f'Admin {user} removed successfully.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'{str(e)}', 'error')

    return render_template('remove_admin.html', title='Remove Admin')


if __name__ == '__main__':
    app.run()
