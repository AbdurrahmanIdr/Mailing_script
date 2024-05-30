import os
import shutil as sh
import time
from threading import Thread
from urllib.parse import quote, unquote

from PyPDF2 import PdfReader, PdfWriter
from flask import Flask, render_template, url_for, request, redirect, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.secret_key = os.urandom(32)
base_dir = os.path.abspath('data')
db_path = os.path.join(base_dir, 'db.sqlite')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)
progress = {}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=False)

    def __init__(self, email, ippis, active=False):
        self.email = email
        self.ippis = ippis
        self.active = active


class ActiveUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class InactiveUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


class UnknownUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ippis = db.Column(db.String(20), nullable=False)


# db.create_all()


def detail_extract(file_page):
    contents = file_page.extract_text().split('\n')
    content = contents[3:6]

    dates = content[0].strip().split('-')
    d_mon = dates[0]
    d_year = dates[-1]
    sur_name = content[1].split(':')[1].split(',')[0].strip()
    if ':' in content[-1]:
        ippis = content[-1].split(':')[-1].strip()
    else:
        ippis = content[6].split(':')[-1].strip()
    new_name = [ippis, sur_name, d_mon, d_year]
    return new_name


# Splitter function to process PDF
def splitter(filename, task_id):
    if str(filename).endswith('.pdf'):
        file_folder = filename.split('.')[0]
        folder_path = os.path.join(base_dir, file_folder)

        if os.path.exists(folder_path):
            sh.rmtree(folder_path)

        os.makedirs(folder_path)

        file_path = str(os.path.join(base_dir, filename))
        pdf_reader = PdfReader(file_path)
        pages = len(pdf_reader.pages)

        for i in range(pages):
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[i])
            name = detail_extract(pdf_reader.pages[i])

            if name[0] == '482427':
                name[0] = str(int(name[0]) + i)

            pswd = f'{name[0][-2:]}{name[1][-2:]}'
            pdf_writer.encrypt(pswd)

            name = f'{name[0]}_{name[1]}_{name[2]}_{name[3]}.pdf'

            file_name = str(os.path.join(base_dir, filename.split('.')[0], name))
            with open(file_name, 'wb') as f:
                pdf_writer.write(f)

            # Update progress
            progress[task_id] = (i + 1) / pages * 100
            time.sleep(0.1)  # Simulate time taken for processing each page

        progress[task_id] = 100  # Ensure progress is marked complete
        return True
    return False


@app.route("/")
@app.route('/index/')
def index():
    return render_template('index.html')


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
        print(f'{file.filename} saved successfully at {base_dir}')
        return render_template('split_enc.html', file=filename)

    print(f'{file.filename} failed to upload check the file type != PDF')
    return redirect(url_for('index'))


@app.route('/split_enc/', methods=['POST'])
def split_enc():
    file = request.form.get('file')
    task_id = str(time.time())  # Generate a unique task ID
    progress[task_id] = 0  # Initialize progress
    file_path = os.path.join(base_dir, file.split('.')[0])
    folder_encoded = quote(file_path)

    # Run the splitter function in the background
    thread = Thread(target=splitter, args=(file, task_id))
    thread.start()

    return render_template('progress.html', task_id=task_id, folder=folder_encoded)


@app.route('/progress/<task_id>')
def progress_status(task_id):
    return jsonify({'progress': progress.get(task_id, 0)})


@app.route('/query_db/', methods=['GET', 'POST'])
def query_db():
    folder = request.form['folder']
    if not folder:
        return redirect(url_for('index'))

    folder = unquote(folder)
    return render_template('query_db.html', folder=folder)


@app.route('/results/', methods=['POST'])
def results():
    folder_encoded = request.form.get('folder')
    if not folder_encoded:
        return redirect(url_for('index'))

    folder = unquote(folder_encoded)

    split_files = [f.split('_')[0] for f in os.listdir(folder)]

    active_users = User.query.filter_by(active=True).all()
    active_ippis = [user.ippis for user in active_users]

    found_users = set(split_files)
    db_users = set(active_ippis)

    active_found = found_users & db_users
    inactive = db_users - found_users
    unknown = found_users - db_users

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

    return render_template('results.html', active=len(active_found), inactive=len(inactive), unknown=len(unknown),
                           folder=folder)


@app.route('/select_folder/')
def select_folder():
    return 'Hello World! Select Folder'


@app.route('/view_users/<category>/', methods=['GET', 'POST'])
def view_users(category):
    if category == 'active':
        users = ActiveUser.query.all()
    elif category == 'inactive':
        users = InactiveUser.query.all()
    elif category == 'unknown':
        users = UnknownUser.query.all()
    else:
        return redirect(url_for('index'))

    return render_template('view_users.html', category=category, users=users)


@app.route('/back_to_result/')
def back_to_result():
    folder = unquote(session['folder'])
    active = session.get('active', 0)
    inactive = session.get('inactive', 0)
    unknown = session.get('unknown', 0)

    return render_template('results.html', active=active, inactive=inactive, unknown=unknown,
                           folder=folder)


@app.route("/add_user/", methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        email = request.form['email']
        ippis = request.form['ippis']
        active = 'active' in request.form

        new_user = User(email=email, ippis=ippis, active=active)
        db.session.add(new_user)
        db.session.commit()

        print(f'User {email} added successfully.')
        return redirect(url_for('index'))

    return render_template('add_user.html')


@app.route('/send_mail/', methods=['GET', 'POST'])
def send_mail():
    return 'Hello World! send_mail'


if __name__ == '__main__':
    app.run()
