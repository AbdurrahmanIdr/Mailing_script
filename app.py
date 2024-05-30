import os
import shutil as sh
import time
from threading import Thread

from PyPDF2 import PdfReader, PdfWriter
from flask import Flask, render_template, url_for, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
base_dir = os.path.abspath('data')
db_path = os.path.join(base_dir, 'db.sqlite')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
db = SQLAlchemy(app)
migrate = Migrate(app, db)
progress = {}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ippis = db.Column(db.String(20), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=False)


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


def splitter(filename):
    if str(filename).endswith('.pdf'):
        file_folder = filename.split('.')[0]
        folder_path = os.path.join(base_dir, file_folder)
        print(file_folder, folder_path, end='\n')
        if os.path.exists(folder_path):
            sh.rmtree(folder_path)
            print(f'{file_folder} removed from {base_dir}')

        os.makedirs(folder_path)

        file_path = str(os.path.join(base_dir, filename))
        print(file_path)
        pdf_reader = PdfReader(file_path)
        pages = len(pdf_reader.pages)
        print(f'Length of pages {pages}')

        for i in range(pages):
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[i])
            name = detail_extract(pdf_reader.pages[i])

            if name[0] == '482427':
                name[0] = str(int(name[0]) + i)

            pswd = f'{name[0][-2:]}{name[1][-2:]}'
            pdf_writer.encrypt(pswd)
            print(f'Encrypted {name} with {pswd}')

            name = f'{name[0]}_{name[1]}_{name[2]}_{name[3]}.pdf'
            print(f'Extracted {name}')

            file_name = str(os.path.join(base_dir, filename.split('.')[0], name))
            print(f'Writing {file_name}')
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
    file = request.files['file']
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
    file = request.form['file']
    task_id = str(time.time())  # Generate a unique task ID
    progress[task_id] = 0  # Initialize progress
    print(file)
    file_path = os.path.join(base_dir, file.split('.')[0])
    print(file_path)

    # Run the splitter function in the background
    thread = Thread(target=splitter, args=(file, task_id))
    thread.start()

    return render_template('progress.html', task_id=task_id)


@app.route('/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    return jsonify(progress=progress.get(task_id, 0))


@app.route('/query_db/<task_id>', methods=['GET'])
def query_db(task_id):
    folder = request.args['folder']
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

    return render_template('results.html', active=len(active_found), inactive=len(inactive), unknown=len(unknown))


@app.route('/select_folder/')
def select_folder():
    return 'Hello World! Select Folder'


@app.route('/view_csv/')
def view_csv():
    return render_template(url_for('view'))


@app.route('/select_view/')
def select_view():
    return 'Hello World! Select View'


@app.route('/results/')
def results():
    return 'Hello World! Results'


@app.route('/send_mail/', methods=['GET', 'POST'])
def send_mail():
    return 'Hello World! send_mail'


if __name__ == '__main__':
    app.run()
