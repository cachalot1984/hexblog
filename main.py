#!/usr/bin/python
#coding:utf-8

import os, MySQLdb
from datetime import datetime

from flask import Flask, render_template, flash, redirect, request, url_for
from flask.ext.script import Manager, Shell
from flask.ext.bootstrap import Bootstrap
from flask.ext.login import UserMixin, LoginManager, login_required, login_user, logout_user
from flask.ext.wtf import Form
from wtforms import PasswordField, SubmitField, BooleanField, TextAreaField, HiddenField
from wtforms.validators import Required
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.moment import Moment
from flask_bootstrap import WebCDN


basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SESSION_TYPE'] = os.environ.get('FLASK_SESSION_TYPE') or 'memcached'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') or '123456' # for CSRF protection of WTF
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('FLASK_DATABASE_URI') or 'sqlite:///' + os.path.join(basedir, 'db.sqlite')
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:foobar@localhost/teablog'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True

manager = Manager(app)
bootstrap = Bootstrap(app)
db = SQLAlchemy(app)
moment = Moment(app)

# use better css and js CDN resource
app.extensions['bootstrap']['cdns']['jquery']= WebCDN('//apps.bdimg.com/libs/jquery/2.1.4/')
app.extensions['bootstrap']['cdns']['bootstrap'] = WebCDN('//apps.bdimg.com/libs/bootstrap/3.3.4/')

login_manager = LoginManager(app)
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'

# callback implemention required by flask-login
@login_manager.user_loader
def load_user(user_id):
    return User()

# make script shell convenient: need not import these stuffs each time
def make_shell_context():
    return dict(app=app, db=db, bootstrap=bootstrap, Article=Article)

manager.add_command('shell', Shell(make_context=make_shell_context))



# Models
#----------------------------------------------------------
class User(UserMixin):
    # solely special admin user
    id = 1
    email = ''
    username = 'root'
    password = app.config['SECRET_KEY']
    role = 'admin'

class LoginForm(Form):
    #email = StringField(u'邮箱', validators=[Required(), Length(1, 64), Email()]
    password = PasswordField(u'密码', validators=[Required()])
    remember_me = BooleanField(u'记住我')
    submit = SubmitField(u'确定')

class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Unicode(128), unique=True, index=True, nullable=True)
    content = db.Column(db.UnicodeText)
    content_size = db.Column(db.Integer)
    time_created = db.Column(db.DateTime, index=True, default=datetime.now())
    time_modified = db.Column(db.DateTime, index=True, default=datetime.now())
    read_count = db.Column(db.Integer)
    #tags = db.Column(db.Enum)

    def __repr__(self):
        return '<Article "{0}">'.format(self.title)

    @staticmethod
    def generate_fake(count=100):
        from sqlalchemy.exc import IntegrityError
        from random import randint, seed
        import forgery_py

        seed()
        for i in range(count):
            title = forgery_py.lorem_ipsum.title()
            content = forgery_py.lorem_ipsum.paragraphs()
            article = Article(title=title, content=content, content_size=len(content),
                            time_created=forgery_py.date.date(True),
                            time_modified=forgery_py.date.date(True),
                            read_count=randint(1, 10000))
            db.session.add(article)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()


class EditForm(Form):
    text = TextAreaField(u'注：第一行为标题', validators=[Required()])
    id = HiddenField('new')
    submit = SubmitField(u'完成')



# URL view map
#----------------------------------------------------------
@app.route('/')
def index():
    articles = Article.query.order_by(Article.time_modified.desc()).all()
    return render_template('index.html', articles=articles)


@app.route('/articles')
def articles():
    return render_template('articles.html')


@app.route('/tools')
def tools():
    return render_template('tools.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/article/<int:id>')
@login_required
def article(id):
    article = Article.query.filter_by(id=id).first()
    article.read_count += 1
    return render_template('article.html', article=article)


# <opid>: 
#   'new' - create article; 
#   <num> - edit article
@app.route('/edit/<opid>', methods=['GET', 'POST'])
@login_required
def edit(opid):
    form = EditForm()
    if form.validate_on_submit():
        now = datetime.now()
        if form.id.data == 'new':
            article = Article(title='', content='', content_size=0, 
                            time_created=now, time_modified=now, read_count=0)
        else:
            article = Article.query.filter_by(id=int(form.id.data)).first()
            article.time_modified = now
        text = form.text.data
        article.title = text.split('\r')[0]
        article.content = '\r'.join(text.split('\r')[1:])
        db.session.add(article)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Failed to commit to DB')
            return internal_server_error(e)
        return redirect(url_for('article', id=article.id))
    else:
        if opid == 'new':
            new = True
            form.id.data = 'new'
            return render_template('edit.html', form=form, new=True)
        else:
            id = int(opid)
            article = Article.query.filter_by(id=id).first()
            form.text.data = article.title + '\r' + article.content
            form.id.data = id
            return render_template('edit.html', form=form, new=False)


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    article = Article.query.filter_by(id=id).first()
    if article != None:
        db.session.delete(article)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Failed to delete the article')
            return internal_server_error(e)
        flash('Article deleted')
    return redirect(url_for('index'))


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
    return render_template('error.html', code=404, e=e), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', code=500, e=e), 500



# main entry
#----------------------------------------------------------
if __name__ == '__main__':
    db.create_all()
    manager.run()
