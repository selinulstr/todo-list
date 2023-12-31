from authlib.jose import jwt
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_redmail import RedMail
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from authlib.integrations.flask_client import OAuth
from authlib.common.security import generate_token
import datetime
import os


db = SQLAlchemy()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///todo.db"
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
OAuth = OAuth(app)
app.config["EMAIL_HOST"] = "localhost"
app.config["EMAIL_PORT"] = 587
app.config["EMAIL_USERNAME"] = "me@example.com"
app.config["EMAIL_PASSWORD"] = "<PASSWORD>"
mail = RedMail(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).filter_by(id=int(user_id))).scalar()


is_dark = False
today = datetime.datetime.today().date().strftime("%d/%m/%Y")
list_name = f"My to-do list {today}"
first_google_list_id = None


def get_path():
    return request.full_path


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    login_with_google = db.Column(db.Boolean)
    verified = db.Column(db.Boolean)

    all_lists = relationship("TodoList", back_populates="user")
    tasks = relationship("Todo", back_populates="user")


class TodoList(db.Model):
    __tablename__ = "lists"
    id = db.Column(db.Integer, primary_key=True)
    list_name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship("User", back_populates="all_lists")
    tasks = relationship("Todo", back_populates="parent_list")


class Todo(db.Model):
    __tablename__ = "todo_tasks"
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey("lists.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    parent_list = relationship("TodoList", back_populates="tasks")
    user = relationship("User", back_populates="tasks")
    task = db.Column(db.String(200))
    starred = db.Column(db.Boolean)
    complete = db.Column(db.Boolean)


@app.route("/")
def home():

    if current_user.is_authenticated:
        return redirect(url_for("saved", user_id=current_user.id))
    else:
        return redirect(url_for("new"))


@app.route("/<int:list_id>")
def show_list(list_id):
    global is_dark, list_name
    list_to_show = db.get_or_404(TodoList, list_id)
    todos = db.session.execute(db.select(Todo).filter_by(list_id=list_id)).scalars()

    return render_template("list.html", todo_list=todos.all(),
                           is_dark=is_dark,
                           list_id=list_id,
                           list_name=list_to_show.list_name,
                           current_user=current_user,
                           path=get_path()
                           )


@app.route("/add", methods=["POST", "GET"])
def add():
    if request.method == "GET":
        task = request.args.get("task")
        p_list_id = int(request.args.get("p_list_id"))

    else:
        task = request.form.get("task")
        p_list_id = int(request.form.get("task_submit"))

    p_list = db.get_or_404(TodoList, p_list_id)
    if current_user.is_authenticated:

        if task != "":
            new_todo = Todo(task=task, complete=False, starred=False, parent_list=p_list, user=current_user)
            db.session.add(new_todo)
            db.session.commit()
            return redirect(url_for("show_list", list_id=p_list_id))
        else:
            return redirect(url_for("show_list", list_id=p_list_id))

    else:
        if task != "":
            new_todo = Todo(task=task, complete=False, starred=False, parent_list=p_list)
            db.session.add(new_todo)
            db.session.commit()
            return redirect(url_for("show_list", list_id=p_list_id))
        else:
            return redirect(url_for("show_list", list_id=p_list_id))


@app.route("/first_save", methods=["POST"])
def first_list():
    global list_name
    if current_user.is_authenticated:
        new_list_to_add = TodoList(list_name=list_name, user=current_user)
        db.session.add(new_list_to_add)
        db.session.commit()

        return redirect(url_for("add", p_list_id=new_list_to_add.id, task=request.form.get("task")))
    else:
        new_list_to_add = TodoList(list_name=list_name)
        db.session.add(new_list_to_add)
        db.session.commit()

        return redirect(url_for("add", p_list_id=new_list_to_add.id, task=request.form.get("task")))


@app.route("/update/<int:todo_id>")
def update(todo_id):
    todo = db.get_or_404(Todo, todo_id)
    todo.complete = not todo.complete
    db.session.commit()

    return redirect(url_for("show_list", list_id=todo.list_id))


@app.route("/delete/<int:todo_id>")
def delete(todo_id):
    task_to_delete = db.get_or_404(Todo, todo_id)
    db.session.delete(task_to_delete)
    db.session.commit()
    return redirect(url_for("show_list", list_id=task_to_delete.list_id))


@app.route("/dark/<page_name>")
def dark(page_name):
    global is_dark
    is_dark = not is_dark
    return redirect(f"/{page_name}")


@app.route("/star/<int:todo_id>")
def star(todo_id):
    task_to_star = db.get_or_404(Todo, todo_id)
    task_to_star.starred = not task_to_star.starred
    db.session.commit()
    return redirect(url_for("show_list", list_id=task_to_star.list_id))


@app.route("/new_list/<int:list_id>")
def new_list(list_id):

    todos = db.session.execute(db.select(Todo).filter_by(list_id=list_id)).scalars()
    for todo in todos.all():
        db.session.delete(todo)
        db.session.commit()
    list_to_delete = db.get_or_404(TodoList, list_id)
    db.session.delete(list_to_delete)
    db.session.commit()
    return redirect(url_for("new"))


@app.route("/delete_list/<int:list_id>")
@login_required
def delete_list(list_id):
    todos = db.session.execute(db.select(Todo).filter_by(list_id=list_id)).scalars()
    for todo in todos.all():
        db.session.delete(todo)
        db.session.commit()
    list_to_delete = db.get_or_404(TodoList, list_id)
    db.session.delete(list_to_delete)
    db.session.commit()
    return redirect(url_for("saved"))


@app.route("/save_list/<int:list_id>")
def save_list(list_id):

    return redirect(url_for("login", list_id=list_id))


@app.route("/save_list_for_new_user/<int:list_id>")
def save_list_for_new_user(list_id):
    return redirect(url_for("register", list_id=list_id))


@app.route("/save_list_for_google/<int:list_id>")
def save_list_for_google(list_id):
    return redirect(url_for("google", list_id=list_id))


@app.route("/new")
def new():
    return render_template("index.html", today=today,
                           is_dark=is_dark,
                           current_user=current_user,
                           path=get_path())


@app.route("/login", methods=["GET", "POST"])
def login():
    global is_dark
    list_id = request.args.get("list_id")

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = db.session.execute(db.select(User).filter_by(email=email)).scalar()

        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for("login"))

        elif not check_password_hash(user.password, password):
            flash("Password incorrect, please try again.")
            return redirect(url_for("login"))

        else:
            login_user(user)
            list_id = request.form.get("list_id")
            if list_id:
                list_to_add = db.get_or_404(TodoList, list_id)
                list_to_add.user = current_user
                for todo in list_to_add.tasks:
                    todo.user_id = current_user.id
                db.session.commit()

            return redirect(url_for("saved"))
    return render_template("login.html", is_dark=is_dark, current_user=current_user, path=get_path(), list_id=list_id)


@app.route("/register", methods=["GET", "POST"])
def register():
    global is_dark
    list_id = request.args.get("list_id")

    if request.method == "POST":
        list_id = request.form.get("list_id")
        if db.session.execute(db.select(User).filter_by(email=request.form.get("email"))).scalar():
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))
        hash_and_salted_password = generate_password_hash(
            request.form.get("password"),
            method="pbkdf2:sha256",
            salt_length=8
        )
        user = User()
        user.email = request.form.get("email")
        user.name = request.form.get("name")
        user.password = hash_and_salted_password
        user.login_with_google = False
        user.valid = False
        db.session.add(user)
        db.session.commit()
        login_user(user)
        token = jwt.encode({"email": current_user.email}, app.config["SECRET_KEY"])
        mail.send(
            subject="Verify email",
            receivers=current_user.email,
            html_template="verification.html",
            body_params={
                "token": token
            }
        )

        if list_id is not None:
            list_to_add = db.get_or_404(TodoList, list_id)
            list_to_add.user = current_user
            for todo in list_to_add.tasks:
                todo.user_id = current_user.id
            db.session.commit()
        return redirect(url_for("saved"))
    return render_template("register.html", is_dark=is_dark, current_user=current_user,
                           path=get_path(), list_id=list_id)


@app.route("/forgot_password/", methods=["GET", "POST"])
def forgot_password():
    global is_dark
    if request.method == "POST":
        email = request.form.get("email")
        token = jwt.encode({"email": current_user.email}, app.config["SECRET_KEY"])
        if db.session.execute(db.select(User).filter_by(email=email)).scalar():
            mail.send(
                        subject="Verify email",
                        receivers=current_user.email,
                        html_template="reset_password.html",
                        body_params={
                            "token": token
                        }
                    )

        else:
            flash("That email does not exist, please try again.")
            return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html", is_dark=is_dark, path=get_path())


@app.route("/reset_password/<token>")
def reset_password(token):
    data = jwt.decode(token, app.config["SECRET_KEY"])
    email = data["email"]

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar()
    if request.method == "POST":

        hash_and_salted_password = generate_password_hash(
            request.form.get("password"),
            method="pbkdf2:sha256",
            salt_length=8
        )

        if request.form.get("password") != "":
            user.password = hash_and_salted_password
            db.session.commit()
        return redirect("/login")
    else:
        return render_template("reset_password.html", token=token)


@app.route("/verified/<token>")
def verify_email(token):
    data = jwt.decode(token, app.config["SECRET_KEY"])
    email = data["email"]

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar()
    user.verified = True
    db.session.commit()
    return render_template("verified.html")


@app.route("/change_list_name/", methods=["POST"])
def change_list_name():

    list_id = request.form.get("list-name-button")
    new_list_name = request.form.get("list-name-input")
    list_to_change = db.get_or_404(TodoList, list_id)
    list_to_change.list_name = new_list_name
    db.session.commit()
    return redirect(url_for("show_list", list_id=list_id))


@app.route("/saved_lists")
@login_required
def saved():
    global is_dark
    lists = db.session.execute(db.select(TodoList).filter_by(user_id=current_user.id)).scalars()
    return render_template("saved.html", is_dark=is_dark, email=current_user.email, lists=lists.all(), path=get_path())


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    global is_dark
    if not current_user.login_with_google:
        if request.method == "POST":

            new_name = request.form.get("name")

            new_email = request.form.get("email")
            if new_name != "":
                current_user.name = new_name
                db.session.commit()

            if new_email != "":
                current_user.email = new_email
                db.session.commit()

            return redirect("/")
        else:

            return render_template("account.html", is_dark=is_dark, current_user=current_user, path=get_path())
    else:
        return redirect("/")


@app.route("/change_password", methods=["POST", "GET"])
@login_required
def change_password():
    global is_dark
    if not current_user.login_with_google:
        if request.method == "POST":

            hash_and_salted_password = generate_password_hash(
                request.form.get("password"),
                method="pbkdf2:sha256",
                salt_length=8
            )

            if request.form.get("password") != "":
                current_user.password = hash_and_salted_password
                db.session.commit()
            return redirect("/")
        else:
            return render_template("password.html", is_dark=is_dark, current_user=current_user, path=get_path())
    else:
        return redirect("/")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/google/")
def google():
    global first_google_list_id
    first_google_list_id = request.args.get("list_id")

    GOOGLE_CLIENT_ID = os.environ.get("CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("CLIENT_SECRET")

    CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
    OAuth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url=CONF_URL,
        client_kwargs={
            "scope": "openid email profile"
        }
    )

    redirect_uri = url_for("google_auth", _external=True)
    session["nonce"] = generate_token()
    return OAuth.google.authorize_redirect(redirect_uri, nonce=session["nonce"])


@app.route("/google/auth/")
def google_auth():
    global first_google_list_id

    token = OAuth.google.authorize_access_token()
    user = OAuth.google.parse_id_token(token, nonce=session["nonce"])
    session["user"] = user

    email = user["email"]
    name = user["name"]
    hash_and_salted_password = generate_password_hash(
        user["nonce"],
        method="pbkdf2:sha256",
        salt_length=8
    )
    user_with_email = db.session.execute(db.select(User).filter_by(email=email)).scalar()
    if user_with_email:
        login_user(user_with_email)

    else:
        user = User()
        user.email = email
        user.name = name
        user.password = hash_and_salted_password
        user.login_with_google = True
        db.session.add(user)
        db.session.commit()
        login_user(user)
    if first_google_list_id is not None:
        list_to_add = db.get_or_404(TodoList, first_google_list_id)
        list_to_add.user = current_user
        for todo in list_to_add.tasks:
            todo.user_id = current_user.id
        db.session.commit()
        first_google_list_id = None

    return redirect("/")


if __name__ == "__main__":
    with app.app_context():

        db.create_all()

    app.run(debug=True)
