from flask import Flask, render_template, url_for

app = Flask(__name__)


@app.route('/upload/')
def upload():
    return render_template(url_for('upload.html'))


@app.route('/select_folder/')
def select_folder():
    return 'Hello World! Select Folder'


@app.route('/query_db/')
def query_db():
    return 'Hello World! Query DB'


@app.route('/view_csv/')
def view_csv():
    return 'Hello World! View CSV'


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
