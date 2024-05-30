import os

from PyPDF2 import PdfReader, PdfWriter
from flask import Flask, render_template, url_for, request, redirect

app = Flask(__name__)
base_dir = os.path.abspath('data')


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
        folder_path = os.path.join(base_dir, filename.split('.')[0])
        if os.path.exists(folder_path):
            os.remove(folder_path)
            print(f'{folder_path} removed')

        os.makedirs(folder_path)

        full_path = str(os.path.join(base_dir, filename))
        print(full_path)
        pdf_reader = PdfReader(full_path)
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
            pdf_writer.write(file_name)

        return True
    return False


@app.route("/")
@app.route('/index/')
def index():
    return render_template('index.html')


@app.route("/upload/", methods=['GET', 'POST'])
def upload():
    file = request.files['file']
    filename = str(file.filename)

    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    if file and filename != '':
        full_path = os.path.join(base_dir, file.filename)
        if os.path.exists(full_path):
            os.remove(full_path)
        file.save(full_path)
        print(f'{file.filename} saved successfully at {base_dir}')
    else:
        print(f'{file.filename} not saved at {base_dir}')

    return redirect(url_for('split_enc', file=filename))


@app.route('/split_enc/<file>')
def split_enc(file):
    file_path = os.path.join(base_dir, file.split('.')[0])
    split = splitter(file)
    if split:
        print(f'{file} successfully split and encrypted at {file_path}')
    else:
        print(f'{file} failed to split')

    return redirect(url_for('query_db', folder=file_path))


@app.route('/select_folder/')
def select_folder():
    return 'Hello World! Select Folder'


@app.route('/query_db/<folder>/')
def query_db(folder):
    return render_template('query_db.html', folder=folder)


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
