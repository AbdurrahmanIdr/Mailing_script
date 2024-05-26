from flask import Flask

app = Flask(__name__)


@app.route('/index/')
def index():
    return 'Hello World! Index'


@app.route('/send_mail/', methods=['GET', 'POST'])
def send_mail():
    return 'Hello World! send_mail'


if __name__ == '__main__':
    app.run()
