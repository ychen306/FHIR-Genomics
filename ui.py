'''
Blueprint taking care of dev registerring and basic app dashboard
'''
from flask.blueprints import Blueprint
from flask import request, render_template, redirect, Response
from urllib import urlencode
from util import hash_password
import uuid
from models import db, User, Session, Resource, Access, Client, SearchParam
from fhir_spec import RESOURCES
from functools import wraps
from urllib import urlencode

ui = Blueprint('/', __name__)

DEFAULT_REDIRECT_URL = 'http://localhost:8000'

def log_in(user):
    session_id = str(uuid.uuid4())
    new_session = Session(user=user, id=session_id)
    db.session.add(new_session)
    db.session.commit()
    return session_id


def authorize_public_data(user):
    # find all resources owned by super user, replicate them,
    # and set owner to user
    for resource in Resource.query.filter_by(owner_id='super'):
        db.make_transient(resource) 
        resource.owner = user
        db.session.add(resource)
    # find all search param owned by super user and replicate them
    for sp in SearchParam.query.filter_by(owner_id='super'):
        db.make_transient(sp)
        sp.owner_id = user.email
        sp.id = None
        db.session.add(sp)
    db.session.commit()


def create_user(form):
    hashed, salt = hash_password(form['password'])
    new_user = User(email=form['email'],
                    app_name=form['appname'],
                    redirect_url=DEFAULT_REDIRECT_URL,
                    hashed_password=hashed,
                    app_id=rand_app_id(),
                    app_secret=str(uuid.uuid4()),
                    salt=salt)
    # give user access to public data
    authorize_public_data(new_user)
    db.session.add(new_user)
    db.session.commit()
    return new_user


def rand_app_id():
    app_id = str(uuid.uuid4())
    while User.query.filter_by(app_id=app_id).first() is not None:
        app_id = str(uuid.uuid4())
    return app_id


def require_login(view):
    @wraps(view)
    def logged_in_view(*args, **kwargs):
        # check if user is logged in
        if  (request.session is None or
            request.session.user is None):
            if request.method != 'GET':
                return Response(status='403')
            else:
                redirect_arg = {'redirect': request.url}
                return redirect('/?%s'% urlencode(redirect_arg))
        return view(*args, **kwargs) 

    return logged_in_view


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
    app_redirect_url = None
    email = request.args.get('email')
    message = request.args.get('message')
    redirect_url = request.args.get('redirect', '/')

    if request.session is not None:
        logged_in = True
        user = request.session.user
        app_id = user.app_id
        app_secret = user.app_secret
        app_name = user.app_name 
        app_redirect_url = user.redirect_url
    
    return render_template('index.html', **locals())


@ui.route('/login', methods=['POST'])
def login():
    password = request.form['password']
    email = request.form['email']
    user = User.query.filter_by(email=email).first()
    if user is not None and user.check_password(password):
        session_id = log_in(user)
        resp = redirect(request.form['redirect_url'])
        resp.set_cookie('session_id', session_id)
    else:
        redirect_args = {'email':email,
                        'message': 'Incorrect email or password',
                        'redirect': request.form['redirect_url']}
        resp = redirect('/?%s'% urlencode(redirect_args))
    return resp


@ui.route('/logout')
def logout():
    if request.cookies.get('session_id'):
        session_id = request.cookies['session_id']
        session = Session.query.get(session_id)
        if session is not None:
            db.session.delete(session)
            db.session.commit()

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
        # if there's an error, we ask the user to redo the form
        if message is not None:
            return render_template('signup.html', message=message)
        # otherwise we create a new user in the database given the form
        else:
            new_user = create_user(request.form)
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
