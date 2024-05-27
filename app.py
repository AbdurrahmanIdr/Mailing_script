import os
from PyPDF2 import PdfReader, PdfWriter

from flask import Flask, render_template, url_for, request

app = Flask(__name__)


def detail_extract(file_page):
    contents = file_page.extract_text().split('\n')

    content = contents[3:6]

    dates = content[0].strip().split('-')
    d_mon = dates[0]
    d_year = dates[-1]
    sur_name = content[1].split(':')[1].split(',')[0].strip()
    ippis = content[-1].split(':')[-1].strip()

    new_name = f'{ippis}_{sur_name}_{d_mon}_{d_year}.pdf'
    return new_name


def splitter(filename):
    if filename.endswith('.pdf'):
        pdf_reader = PdfReader(filename)
        pages = len(pdf_reader.pages)

        for i in range(pages):
            pdf_writer = PdfWriter()
            pdf_writer.addpage(pdf_reader.pages[i])
            name = detail_extract(pdf_reader.pages[i])
            pdf_writer.encrypt('12345')
            pdf_writer.write(name)



@app.route("/")
@app.route('/index/')
def index():
    return render_template(url_for('index.html'))


@app.route("/upload/")
def upload():
    base_dir = os.path.abspath('data/raw')
    file = request.files['file']
    if file and file.filename != '':
        file.save(os.path.join(base_dir, file.filename))
        print(f'{file.filename} saved successfully at {base_dir}')

    else:
        print(f'{file.filename} not saved at {base_dir}')

    return render_template(url_for('query_db.html'))


@app.route('/select_folder/')
def select_folder():
    return 'Hello World! Select Folder'


@app.route('/query_db/')
def query_db():
    return 'Hello World! Query DB'


@app.route('/view_csv/')
def view_csv():
    return render_template(url_for('view.html'))


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
