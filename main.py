#!/usr/bin/python

from flask import Flask, render_template
from flask.ext.script import Manager
from flask.ext.bootstrap import Bootstrap

app = Flask(__name__)
manager = Manager(app)
bootstrap = Bootstrap(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/articles')
def articles():
    return render_template('articles.html')

@app.route('/tools')
def tootls():
    return render_template('tools.html')

@app.route('/me')
def me():
    return render_template('me.html')

@app.route('/article')
def article():
    return render_template('article.html')

@app.route('/edit')
def edit():
    return render_template('edit.html')

@app.route('/login')
def login():
    return render_template('login.html')

if __name__ == '__main__':
    manager.run()
