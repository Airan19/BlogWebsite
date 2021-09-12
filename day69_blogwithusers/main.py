from flask import Flask, render_template, redirect, url_for, flash, request, abort
from functools import wraps
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from dotenv import load_dotenv
import pytz
import smtplib
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)
load_dotenv('.env')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL1', "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
IST = pytz.timezone('Asia/Kolkata')


##CONFIGURE TABLES
class User(UserMixin,db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))

    # This will act like a List of BlogPost objects attached to each User.
    # The 'author' refers to the author property in the BlogPost class.
    posts = relationship('BlogPost', back_populates='author')

    # Add parent relationship
    # 'comment_author' refers to the comment_authro property in the Comment Class.
    comments = relationship('Comment', back_populates='comment_author')


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, 'users.id' the users refers to the tablename of User.
    author_id = db.Column(db.Integer,  db.ForeignKey('users.id'))
    # Create reference to the User object, teh 'posts' refers to the posts property in the User class.
    author = relationship('User', back_populates='posts')

    # author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # Parent Relationship
    comments = relationship('Comment', back_populates = 'parent_post')


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(250), nullable=False)
    # Add Child relationship
    # 'users.id' The users refers to the tablename of the Users class.
    # 'comments' refers to the comments property in the User class.
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment_author = relationship('User', back_populates='comments')

    # Child Relationship
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    parent_post = relationship('BlogPost', back_populates='comments')


# db.create_all()

gravatar = Gravatar(app, size=100, default='identicon', rating='g', force_default=False, force_lower=False, use_ssl=False, base_url=None)

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if not current_user.is_authenticated or current_user.id != 1 :
                return abort(403, description="Unauthorized access")
        except AttributeError:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def user_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if not current_user.is_authenticated  :
                return abort(403, description="Unauthorized access")
        except AttributeError:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    # if request.method == 'POST':
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('You have already signed up with that email, login instead.')
            return redirect(url_for('login'))
        hashed_pass = generate_password_hash(
            password=form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
            )
        new_user = User(
            email=form.email.data,
            password=hashed_pass,
            name=form.name.data
            )

        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form)


@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password,password):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Password incorrect, please try again!")
                return redirect(url_for('login'))
        else:
            flash('The email does not exist, please try again.')
            return redirect(url_for('login'))

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


previous_text = ''
@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    form = CommentForm()
    global previous_text
    requested_post = BlogPost.query.get(post_id)
    if form.validate_on_submit():
        if current_user.is_authenticated:
            if form.text.data != previous_text:
                new_comment = Comment(
                    text=form.text.data,
                    comment_author=current_user,
                    parent_post=requested_post,
                    date=datetime.now(IST).strftime('%I:%M %p %b %d, %Y')
                )
                db.session.add(new_comment)
                db.session.commit()
                previous_text = form.text.data
            else:
                return redirect(url_for('show_post', post_id=post_id))
        else:
            flash('You need to login or register to comment.')
            return redirect(url_for('login'))

    return render_template("post.html", post=requested_post, form=form, comments=Comment.query.all(), avatar=gravatar)


@app.route("/about")
def about():
    return render_template("about.html")


saved_message = ''
saved_name = ''
@app.route("/contact", methods=['GET', 'POST'])
def contact():
    global saved_message , saved_name
    if request.method == "POST" and request.form['message'] != saved_message and request.form['name'] != saved_name:
        name = request.form["name"]
        saved_name = name
        email = request.form["email"]
        phone = request.form["phone"]
        message = request.form["message"]
        saved_message = message
        user = os.environ.get('EMAIL')
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()
            connection.login(user=user, password=os.environ.get('PASSWORD'))
            connection.sendmail(
                from_addr=user,
                to_addrs=user,
                msg=f"Subject: New Message!\n\n"
                    f"Name: {name}\n"
                    f"Email: {email}\n"
                    f"Phone: {phone}\n"
                    f"Message: {message}\n"
            )

        return render_template("contact.html", posted=True)
    return render_template("contact.html")


@app.route("/new-post", methods=['GET', 'POST'])
@user_login
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            # author=current_user.name,
            author_id = current_user.id,
            # author=form.author.data,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@user_login
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@user_login
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route('/<name>/dashboard', methods=['GET', 'POST'])
def user_dashboard(name):
    try:
        if current_user.is_anonymous or not current_user.is_authorised:
            return redirect(url_for('login'))
    except AttributeError:
        # if current_user.is_authorised:
        author_id = User.query.filter_by(name=name).first()
        posts = BlogPost.query.filter_by(author_id=author_id.id).all()
        current_user_dashboard = False
        if current_user.name == name:
            current_user_dashboard = True
        return render_template('dashboard.html', name=name, all_posts=posts, current_user_dashboard=current_user_dashboard)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
