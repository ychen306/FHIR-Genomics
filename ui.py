'''
Blueprint taking care of dev regiserring and basic app dashboard
'''
from flask.blueprints import Blueprint
from flask import request, render_template, redirect, Response
from urllib import urlencode
from models import db, User, Session
from util import hash_password
import uuid

ui = Blueprint('/', __name__)


def log_in(user):
    session_id = str(uuid.uuid4())
    new_session = Session(user=user, id=session_id)
    db.session.add(new_session)
    db.session.commit()
    return session_id


def rand_app_id():
    app_id = str(uuid.uuid4())
    while User.query.filter_by(app_id=app_id).first() is not None:
        app_id = str(uuid.uuid4())
    return app_id


def require_login(view):
    def protected_view(*args, **kwargs):
        # check if user is logged in
        if  (request.session is None or
            request.session.user is None):
            return redirect('/')
        return view(*args, **kwargs) 

    return protected_view


@ui.before_request
def get_session():
    session_id = request.cookies.get('session_id') 
    request.session = Session.query.filter_by(id=session_id).first()


@ui.route('/')
def index():
    '''
    dashboard for app, no fancy stuff
    '''
    logged_in = False
    app_id = None
    app_secret = None
    app_name = None
    redirect_url = None
    email = request.args.get('email')
    message = request.args.get('message')

    if request.session is not None:
        logged_in = True
        user = request.session.user
        app_id = user.app_id
        app_secret = user.app_secret
        app_name = user.app_name 
        redirect_url = user.redirect_url

    return render_template('index.html', **locals())


@ui.route('/login', methods=['POST'])
def login():
    password = request.form['password']
    email = request.form['email']
    user = User.query.filter_by(email=email).first()
    resp = redirect('/')
    if user is not None and user.check_password(password):
        session_id = log_in(user)
        resp.set_cookie('session_id', session_id)
    else:
        redirect_args = {'email':email,
                        'message': 'Incorrect email or password'}
        resp = redirect('/?%s'% urlencode(redirect_args))
    return resp


@ui.route('/logout')
def logout():
    resp = redirect('/')
    resp.set_cookie('session_id', expires=0)
    return resp


@ui.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    elif request.method == 'POST':
        message = None
        if request.form['password'] != request.form['confirmPassword']:
            message = "Confirm password doesn't match."
        elif User.query.filter_by(email=request.form['email']).first() is not None:
            message = "Email has been used by other user."
        if message is not None:
            return render_template('signup.html', message=message)
        else:
            hashed, salt = hash_password(request.form['password'])
            new_user = User(email=request.form['email'],
                            app_name=request.form['appname'],
                            redirect_url='http://localhost:8000',
                            hashed_password=hashed,
                            app_id=rand_app_id(),
                            app_secret=str(uuid.uuid4()),
                            salt=salt)
            db.session.add(new_user)
            db.session.commit()
            session_id = log_in(new_user)
            resp = redirect('/')
            resp.set_cookie('session_id', session_id)
            return resp


@ui.route('/update_app', methods=['POST'])
@require_login
def update_app():
    user = request.session.user
    user.redirect_url = request.form['redirect_url']
    user.app_name = request.form['appname']
    db.session.add(user)
    db.session.commit()
    return redirect('/')
