#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, collections, MySQLdb, bleach, imghdr
from datetime import datetime

from flask import Flask, render_template, flash, redirect, request, url_for, session
from flask.ext.script import Manager, Shell
from flask.ext.bootstrap import Bootstrap
from flask.ext.login import UserMixin, LoginManager, login_required, login_user, logout_user, current_user
from flask.ext.wtf import Form
from wtforms import PasswordField, SubmitField, BooleanField, TextAreaField, HiddenField, TextField, SelectField, StringField
from wtforms.validators import Required, ValidationError
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask.ext.migrate import Migrate, MigrateCommand
from flask.ext.moment import Moment
from flask_bootstrap import WebCDN
from flask.ext.pagedown import PageDown
from flask.ext.pagedown.fields import PageDownField
from markdown import markdown
from flask_admin import Admin, form
from flask_admin.base import AdminIndexView
from flask_admin.contrib import sqla
from flask_admin.contrib.fileadmin import FileAdmin
from jinja2 import Markup
from sqlalchemy.event import listens_for



app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

# for CSRF protection of WTF
app.config['SECRET_KEY'] = os.environ.get('HEXBLOG_SECRET_KEY') or '1hexblog9'
app.config['SESSION_TYPE'] = os.environ.get('HEXBLOG_SESSION_TYPE') or 'memcached'

app.config['SQLALCHEMY_DATABASE_URI'] = \
    os.environ.get('HEXBLOG_DATABASE_URI') or 'sqlite:///' + os.path.join(basedir, 'db.sqlite')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['HEXBLOG_ARTICLES_PER_PAGE'] = 10
# use the first article as the content of the 'about' page
app.config['HEXBLOG_ABOUT_ARTICLE_NUM'] = 1
# use the second article as the content of the 'markdown help' page, used in editing page
app.config['HEXBLOG_MARKDOWN_ARTICLE_NUM'] = 2

db = SQLAlchemy(app)
migrate = Migrate(app, db)

bootstrap = Bootstrap(app)
# use better css and js CDN resource
app.extensions['bootstrap']['cdns']['jquery'] = WebCDN('//apps.bdimg.com/libs/jquery/2.1.4/')
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
    return dict(app=app, db=db, bootstrap=bootstrap, Article=Article, 
                Category=Category, Series=Series)

manager = Manager(app)
manager.add_command('shell', Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

moment = Moment(app)

pagedown = PageDown(app)

admin = Admin(app, name='Hexblog', template_mode='bootstrap3')

# Create directory for file fields to use
file_path = os.path.join(basedir, 'static/files')
try:
    os.mkdir(file_path)
except OSError:
    pass


# Models
#----------------------------------------------------------
class User(UserMixin):
    # solely special admin user, hard-coded
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
    title = db.Column(db.Unicode(128), unique=True, index=True, nullable=False)
    content = db.Column(db.UnicodeText) # plain-text or markdown 
    content_html = db.Column(db.UnicodeText) # html
    content_pre = db.Column(db.UnicodeText) # several top lines for preview in 'index' page
    content_size = db.Column(db.Integer)
    time_created = db.Column(db.DateTime, index=True, default=datetime.now())
    time_modified = db.Column(db.DateTime, index=True, default=datetime.now())
    read_count = db.Column(db.Integer)
    private = db.Column(db.Boolean) # non-public, or hidden
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=True) # could be null
    tags = db.Column(db.Unicode(256), index=True, nullable=True) # space separated tag worlds

    def __repr__(self):
        return u'<Article "{0}">'.format(self.title)

    @staticmethod
    def on_changed_content(target, value, oldvalue, initiator):
        markdown_exts = ['markdown.extensions.extra', 'markdown.extensions.codehilite', 
                    ]
        markdown_exts_configs = {
                        'markdown.extensions.codehilite':
                                {
                                    'css_class': 'highlight',   # default class is 'codehilite'
                                },
                    }
        allowed_tags = [
                        'a', 'abbr', 'acronym', 'b', 'br', 'blockquote', 'code', 'del', 'em', 
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'i', 'img', 'li', 'ol', 'p', 'pre', 
                        'span', 'small', 'strong', 'sub', 'sup', 'table', 'thead', 'tbody', 
                        'td', 'th', 'tr', 'ul', '*'
                    ]
        allowed_attrs = {
                        '*': ['class', 'style'],
                        'a': ['href', 'rel', 'title'],
                        'img': ['alt', 'src', 'title'], 
                    }
        allowed_styles = ['*']
        html = markdown(value, output_format='html5', 
                    extensions=markdown_exts, extension_configs=markdown_exts_configs)
        '''
        cleaned_html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs, 
                                   styles=allowed_styles, strip=True)
        target.content_html = bleach.linkify(cleaned_html)
        '''
        target.content_html = html
        lines = target.content_html.split("\n")
        target.content_pre = "\n".join(lines[:20])

    @staticmethod
    def generate_fake(count=100):
        from random import randint, seed
        import forgery_py

        categories = Category.query.all()
        seed()
        for i in range(count):
            title = forgery_py.lorem_ipsum.title()
            content = forgery_py.lorem_ipsum.paragraphs()
            article = Article(title=title, content=content, content_size=len(content),
                            time_created=forgery_py.date.date(True, max_delta=1000),
                            time_modified=forgery_py.date.date(True, max_delta=1000),
                            read_count=randint(1, 10000),
                            private=False, category=categories[randint(0, len(categories)-1)])
            db.session.add(article)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(32), unique=True, index=True, nullable=False)
    articles = db.relationship('Article', backref='category', lazy='dynamic')

    def __repr__(self):
        return u'<Category "{0}">'.format(self.name)

    @staticmethod
    def generate_fake(count=10):
        from random import randint, seed
        import forgery_py

        seed()
        for i in range(count):
            name = forgery_py.personal.language()
            category = Category(name=name)
            db.session.add(category)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()


class Series(db.Model):
    __tablename__ = 'series'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(128), unique=True, index=True, nullable=False)
    articles = db.relationship('Article', backref='series', lazy='dynamic')

    def __repr__(self):
        return u'<Series "{0}">'.format(self.name)

    @staticmethod
    def generate_fake(count=10):
        from random import randint, seed
        import forgery_py

        seed()
        for i in range(count):
            name = forgery_py.lorem_ipsum.title()
            series = Series(name=name)
            db.session.add(series)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()


class Image(db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(64), unique=True, index=True, nullable=False)
    description = db.Column(db.UnicodeText)
    #content = db.Column(db.LargeBinary, nullable=False)
    path = db.Column(db.Unicode(256), nullable=False) # stored in local directory instead

    def __repr__(self):
        return u'<File "{0}">'.format(self.name)


@listens_for(Image, 'after_delete')
def del_image(mapper, connection, target):
    if target.path:
        # Delete image
        try:
            os.remove(os.path.join(file_path, target.path))
        except OSError:
            pass

        # Delete thumbnail
        try:
            os.remove(os.path.join(file_path, form.thumbgen_filename(target.path)))
        except OSError:
            pass


# Flask-Admin view for the 'images' model
class ImageModelView(sqla.ModelView):
    column_searchable_list = ['name', 'description']
    edit_modal = True
    form_excluded_columns = ['path']

    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if un-authenticated user access the 'files' admin page
        return redirect(url_for('login', next=request.url))

    def list_thumbnail(view, context, model, name):
        if not model.name:
            return ''
        url = url_for('static', filename='files/' + model.path)
        url_thumb = url_for('static', filename='files/' + form.thumbgen_filename(model.path))
        return Markup('<a href="%s" target="_blank"><img src="%s" width="100" height="100"></a>' % (url, url_thumb))

    column_formatters = {
        'path': list_thumbnail
    }

    # Alternative way to contribute field is to override it completely.
    # In this case, Flask-Admin won't attempt to merge various parameters for the field.
    form_extra_fields = {
        'path': form.ImageUploadField('Image', base_path=file_path, thumbnail_size=(100, 100, True))
    }


# Flask-Admin view to custimize the original FileAdmin view
class FileAdminView(FileAdmin):
    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if un-authenticated user access the 'files' admin page
        return redirect(url_for('login', next=request.url))


class EditForm(Form):
    id = HiddenField('new')
    title = TextField(u'标题', validators=[Required()])
    content = PageDownField(u'内容', validators=[Required()])

    def new_category_validator(form, field):
        if form.category.data == 'new':
            if not len(field.data):
                raise ValidationError(u'在此输入新分类名')
            elif field.data in [c[1] for c in form.category.choices]:
                raise ValidationError(u'分类名已存在')

    def new_series_validator(form, field):
        if form.series.data == 'new':
            if not len(field.data):
                raise ValidationError(u'在此输入新系列名')
            elif field.data in [s[1] for s in form.series.choices]:
                raise ValidationError(u'系列名已存在')

    # startup needs to create all necessary tables before the following query operation
    db.create_all()

    categories = Category.query.order_by(Category.name).all()
    choices = [(str(c.id), c.name) for c in categories]
    choices.append(('new', u'--新建分类--'))    # special category hint
    category = SelectField(u'分类', choices=choices, validators=[Required()])
    # the category name when create new category
    category_new = StringField('', validators=[new_category_validator])

    all_series = Series.query.order_by(Series.name).all()
    choices = [(str(s.id), s.name) for s in all_series]
    choices.insert(0, ('none', u'--无--'))  # default choice, not belongs to any series
    choices.append(('new', u'--新建系列--'))    # special serial hint
    series = SelectField(u'系列', choices=choices, validators=[Required()])
    # the series name when create new series
    series_new = StringField('', validators=[new_series_validator])

    tags = StringField(u'标签')

    private = BooleanField(u'不公开')
    submit = SubmitField(u'完成')


def update_tags_cache(articles=None, reverse=False):
    tags = {}
    if not articles:
        articles = Article.query.order_by(Article.title).all()
    for article in articles:
        if not article.tags:
            continue
        for tag in article.tags.split():
            tags.setdefault(tag, set())
            tags[tag].add(article)
    #print(tags)
    return sorted(tags.items(), reverse=reverse) # _list_ of item: ('tag', {art1, art2, ...})



# URL view map
#----------------------------------------------------------
@app.route('/')
def index():
    #articles = Article.query.order_by(Article.time_modified.desc()).all()
    page = request.args.get('page', 1, type=int)
    pagination = Article.query.order_by(Article.time_created.desc()).paginate(
                    page, per_page=app.config['HEXBLOG_ARTICLES_PER_PAGE'], error_out=True)
    articles = pagination.items
    return render_template('index.html', articles=articles, pagination=pagination)


@app.route('/articles')
def articles():
    if session.get('articles_orders') is None:
        # used for article sorting in page '/articles'
        session['articles_orders'] = {
                'time_modified': 0, 
                'time_created': 0, 
                'read_count': 0, 
                'content_size': 0,
                'category': 0,
                'series': 0,
                'tag': 0, 
                'search': 0
            }
    if session.get('searched_words') is None:
        session['searched_words'] = ''
    articles = empty_metas = tags_cache = None

    by = request.args.get('by') or 'time_modified'   # make 'time_modified' default
    if by == 'time_modified':
        articles = Article.query.order_by(Article.time_modified.desc()).all()
    elif by == 'time_created':
        articles = Article.query.order_by(Article.time_created.desc()).all()
    elif by == 'read_count':
        articles = Article.query.order_by(Article.read_count).all()
        articles.reverse()
    elif by == 'content_size':
        articles = Article.query.order_by(Article.content_size).all()
    elif by == 'category':
        articles = Article.query.order_by(Article.category_id).all()
        articles.sort(key=(lambda c: c.category.name))
        if current_user.is_authenticated:
            categories = Category.query.all()
            empty_metas = [c for c in categories if not c.articles.all()]
            empty_metas.sort(key=(lambda c: c.name))
    elif by == 'series':
        articles = Article.query.order_by(Article.series_id).all()
        articles = [a for a in articles if a.series ]
        articles.sort(key=(lambda c: c.series.name))
        if current_user.is_authenticated:
            all_series = Series.query.all()
            empty_metas = [s for s in all_series if not s.articles.all()]
            empty_metas.sort(key=(lambda s: s.name))
    elif by == 'tag':
        tags_cache = update_tags_cache(reverse=session['articles_orders'][by])
    elif by == 'search':
        words = request.args.get('searched_words')
        if not words or len(words) == 0:
            words = session['searched_words']
        articles = []
        if words and len(words) > 0:
            all_articles = Article.query.order_by(Article.time_created.desc()).all()
            for a in all_articles:
                if a.content and a.content.find(words) >= 0:
                    articles.append(a)
        session['searched_words'] = words
    else:
        return page_not_found(Exception("Invalid list condition"))

    if by != 'tag' and session['articles_orders'][by]:
            articles.reverse()
    session['articles_orders'][by] = 1 - session['articles_orders'][by]

    return render_template('articles.html', articles=articles, by=by, 
                            empty_metas=empty_metas, tags_cache=tags_cache)


@app.route('/tools')
def tools():
    return render_template('tools.html')


@app.route('/about')
def about():
    article = Article.query.filter_by(id=app.config['HEXBLOG_ABOUT_ARTICLE_NUM']).first()
    return render_template('about.html', article=article)


@app.route('/article/<int:id>')
def article(id):
    article = Article.query.filter_by(id=id).first_or_404()
    if article.private and not current_user.is_authenticated:
        flash("Private article")
        return page_not_found(Exception("Not allowed to read"))
    article.read_count += 1

    if article.tags:
        tags = article.tags.split()
    else:
        tags = None

    articles = Article.query.order_by(Article.time_created.desc()).all()
    index = articles.index(article)
    next = articles[index - 1] if index >= 1 else None
    prev = articles[index + 1] if index < len(articles) - 1 else None
    return render_template('article.html', article=article, tags=tags, prev=prev, next=next)


# <opid>: 
#   'new' - create article; 
#   <num> - edit article
@app.route('/edit/<opid>', methods=['GET', 'POST'])
@login_required
def edit(opid):
    form = EditForm()
    if form.validate_on_submit():
        # new or edit post received
        now = datetime.now()
        if form.id.data == 'new':
            article = Article(title='', content='', content_size=0, 
                            time_created=now, time_modified=now, read_count=0)
        else:
            article = Article.query.filter_by(id=int(form.id.data)).first_or_404()
            article.time_modified = now

        article.title = form.title.data
        article.content = form.content.data
        article.content_size = len(form.content.data)
        article.private = form.private.data

        if form.category.data == 'new':
            category = Category(name=form.category_new.data)
            db.session.add(category)
        else:
            category = Category.query.filter_by(id=int(form.category.data)).first_or_404()
        article.category = category

        if form.series.data == 'new':
            series = Series(name=form.series_new.data)
            db.session.add(series)
        elif form.series.data == 'none':
            series = None
        else:
            series = Series.query.filter_by(id=int(form.series.data)).first_or_404()
        article.series = series

        article.tags = form.tags.data

        db.session.add(article)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Failed to commit to DB')
            return internal_server_error(e)
        return redirect(url_for('article', id=article.id))
    else:
        # display new or edit page
        categories = Category.query.order_by(Category.name).all()
        form.category.choices = [(str(c.id), c.name) for c in categories]
        form.category.choices.append(('new', u'--新建分类--'))    # special category hint

        all_series = Series.query.order_by(Series.name).all()
        form.series.choices = [(str(s.id), s.name) for s in all_series]
        form.series.choices.insert(0, ('none', u'--无--'))  # default choice, not belongs to any series
        form.series.choices.append(('new', u'--新建系列--'))    # special serial hint

        if opid == 'new':
            new = True
            form.id.data = 'new'
            form.category.data = '1'    # default category
            form.series.data = 'none'    # default series
            return render_template('edit.html', form=form, new=True, 
                        help_article_id=app.config['HEXBLOG_MARKDOWN_ARTICLE_NUM'])
        else:
            id = int(opid)
            article = Article.query.filter_by(id=id).first_or_404()
            form.id.data = id
            form.title.data = article.title
            form.content.data = article.content
            form.private.data = article.private
            form.category.data = str(article.category.id)
            if article.series:
                form.series.data = str(article.series.id)
            form.tags.data = article.tags
            return render_template('edit.html', form=form, new=False, 
                        help_article_id=app.config['HEXBLOG_MARKDOWN_ARTICLE_NUM'])


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    article = Article.query.filter_by(id=id).first_or_404()
    if article:
        db.session.delete(article)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Failed to delete the article')
            return internal_server_error(e)
        flash('Article deleted')
    return redirect(url_for('index'))


@app.route('/delete_category/<int:id>')
@login_required
def delete_category(id):
    if id == 1:
        flash('Cannot delete this special category')
        return redirect(url_for('articles', by='category'))

    category = Category.query.filter_by(id=id).first_or_404()
    if category != None:
        if category.articles.all():
            flash('There are articles in this category, cannot delete')
            return redirect(url_for('articles', by='category'))
        db.session.delete(category)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Failed to delete the category')
            return internal_server_error(e)
        flash('Category deleted')
    return redirect(url_for('articles', by='category'))


@app.route('/delete_series/<int:id>')
@login_required
def delete_series(id):
    series = Series.query.filter_by(id=id).first_or_404()
    if series:
        if series.articles.all():
            flash('There are articles in this series, cannot delete')
            return redirect(url_for('articles', by='series'))
        db.session.delete(series)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Failed to delete the series')
            return internal_server_error(e)
        flash('Series deleted')
    return redirect(url_for('articles', by='series'))


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


# pass needed data to show sidebar, which required for almost every page
@app.context_processor
def fill_sidebar_data():
    sidebar_data = {
                'category': collections.OrderedDict(), 
                'archive': collections.OrderedDict(), 
                'popular': [], 
                'tags': [], 
                'share': None
            }

    # 'category' ordered by category name
    # data format: {cat1: num1, cat2: num2, ...}
    #           category  num of articles
    categories = Category.query.order_by(Category.name).all()
    for category in categories:
        sidebar_data['category'][category] = len(category.articles.all())

    # 'archive' ordered by date
    # data format: {2016: {1: 3}, 2015:{12: 8, 10: 2}, }
    #               year  mon num
    articles = Article.query.order_by(Article.time_created.desc()).all()
    year = month = -1
    for article in articles:
        if article.time_created.year != year:
            year = article.time_created.year
            sidebar_data['archive'][year] = collections.OrderedDict()
        if article.time_created.month != month:
            month = article.time_created.month
            sidebar_data['archive'][year][month] = 0 
        sidebar_data['archive'][year][month] += 1

    # 'popular' ordered by read_count, top 8 articles
    # data format: [article1, article2, ..., article8]
    articles.sort(key=(lambda a: a.read_count), reverse=True)
    sidebar_data['popular'] = articles[:10]

    # 'tags' ordered by name, with member article count
    # data format: [(num_min, num_max), (tag1, num1), (tag2, num2), ...]
    tags_cache = update_tags_cache(articles=articles)
    tags_data = [(t[0], len(t[1])) for t in tags_cache]
    tags_nums = [t[1] for t in tags_data]
    tags_nums.sort()
    if len(tags_nums):
        tags_data.insert(0, (tags_nums[0], tags_nums[-1]))
    else:
        tags_data.insert(0, (-1, -1))
    sidebar_data['tags'] = tags_data

    return dict(sidebar_data=sidebar_data)


@app.route('/search', methods=['POST'])
def search():
    words = request.form.get('searched_words')

    return redirect(url_for('articles', by='search', searched_words=words))



# main entry
#----------------------------------------------------------
db.event.listen(Article.content, 'set', Article.on_changed_content)
db.create_all()

# default category object for any non-categorized articles, its id is 1
category_default = Category(name=u'其他')
db.session.add(category_default)
try:
    db.session.commit()
except IntegrityError:
    db.session.rollback()

# Flask-Admin views
admin.add_view(ImageModelView(Image, db.session))
admin.add_view(FileAdminView(file_path, '/static/files/', name='Files'))


if __name__ == '__main__':
    manager.run()
else:
    # called by WSGI gateway
    application = app.wsgi_app


