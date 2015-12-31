#!/usr/bin/python
#coding:utf-8

import os

from flask import Flask, render_template, flash, redirect, request, url_for
from flask.ext.script import Manager
from flask.ext.bootstrap import Bootstrap
from flask.ext.login import UserMixin, LoginManager, login_required, login_user, logout_user
from flask.ext.wtf import Form
from wtforms import PasswordField, SubmitField, BooleanField
from wtforms.validators import Required


app = Flask(__name__)
app.config['SESSION_TYPE'] = os.environ.get('FLASK_SESSION_TYPE') or 'memcached'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') or "123456" # for CSRF protection of WTF

manager = Manager(app)
bootstrap = Bootstrap(app)

login_manager = LoginManager(app)
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'

class User(UserMixin):
    # solely special admin user
    id = 1
    email = ''
    username = 'root'
    password = app.config['SECRET_KEY']
    role = 'admin'

@login_manager.user_loader
def load_user(user_id):
    return User()


# URL view map
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/articles')
def articles():
    return render_template('articles.html')

@app.route('/tools')
def tools():
    return render_template('tools.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/article')
def article():
    return render_template('article.html')

@app.route('/edit')
@login_required
def edit():
    return render_template('edit.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    password = None
    form = LoginForm()
    if form.validate_on_submit():
        user = User()
        password = form.password.data
        form.password.data = ''
        if password is not None and password == user.password:
            login_user(user, form.remember_me.data)
            flash('Logged in')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid password')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out')
    return redirect(request.args.get('next') or url_for('index'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html'), 500


# Forms
# login
class LoginForm(Form):
    #email = StringField(u'邮箱', validators=[Required(), Length(1, 64), Email()]
    password = PasswordField(u'密码', validators=[Required()])
    remember_me = BooleanField(u'记住我')
    submit = SubmitField(u'确定')


if __name__ == '__main__':
    manager.run()
