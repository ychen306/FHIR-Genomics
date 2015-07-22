'''
Blueprint taking care of dev registerring and basic app dashboard
'''
from flask.blueprints import Blueprint
from flask import request, render_template, redirect, Response, url_for
from urllib import urlencode
import json
import uuid
from functools import wraps
from urllib import urlencode
from util import hash_password, get_api_base
from ttam.models import TTAMClient
from models import db, User, Session, Resource, Access, Client, SearchParam, App, Context
from fhir_spec import RESOURCES

ui = Blueprint('ui', __name__)

UNAUTHORIZED = Response(status='403')
NOT_FOUND = Response(status='404')
BAD_REQUEST = Response(status='400')

def log_in(user):
    '''
    create a new session for a user
    '''
    session_id = str(uuid.uuid4())
    new_session = Session(user=user, id=session_id)
    db.session.add(new_session)
    db.session.commit()
    return session_id


# TODO make this more efficient using core insert
def authorize_public_data(user):
    '''
    find all resources owned by super user, replicate them,
    and set owner to user
    '''
    # find all resources owned by super user and replicate them
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
    '''
    Create a new user given registration form
    '''
    hashed, salt = hash_password(form['password'])
    new_user = User(email=form['email'],
                    hashed_password=hashed,
                    salt=salt)
    # give user access to public data
    authorize_public_data(new_user)
    db.session.add(new_user)
    db.session.commit()
    return new_user


def rand_client_id():
    '''
    return a random and unique client_id
    '''
    client_id = str(uuid.uuid4())
    # make sure it's unique
    while App.query.filter_by(client_id=client_id).first() is not None:
        client_id = str(uuid.uuid4())
    return client_id


def require_login(view):
    '''
    Decorator to ensure a route is only accessed by logged in user
    Prompt the user to login with proper redirect if the user is not loggedin.
    '''
    @wraps(view)
    def logged_in_view(*args, **kwargs):
        # check if user is logged in
        if  (request.session is None or
            request.session.user is None):
            if request.method != 'GET':
                return UNAUTHORIZED
            else:
                redirect_arg = {'redirect': request.url}
                return redirect('/?%s'% urlencode(redirect_arg))
        return view(*args, **kwargs) 

    return logged_in_view


@ui.before_request
def get_session():
    '''
    get associated session from `session_id` cookie
    '''
    session_id = request.cookies.get('session_id') 
    request.session = Session.query.filter_by(id=session_id).first()


@ui.route('/')
def index():
    '''
    dashboard for app, no fancy stuff
    '''
    logged_in = False
    app_name = None
    app_redirect_url = None
    email = request.args.get('email')
    message = request.args.get('message')
    redirect_url = request.args.get('redirect', '/')

    if request.session is not None:
        logged_in = True
        user = request.session.user
        apps = [{ 'name': app.name, 'client_id': app.client_id }
            for app in App.query.filter_by(user_id=user.email).all()]
        can_import_ttam = TTAMClient.query.get(user.email) is None
    
    return render_template('index.html', **locals())


@ui.route('/login', methods=['POST'])
def login():
    '''
    handle user login here and redirect to proper url after success login
    '''
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
    '''
    logout by delete current user session
    '''
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
    '''
    handle user signup here
    '''
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


@ui.route('/create_app', methods=['GET', 'POST'])
@require_login
def create_app():
    if request.method == 'GET':
        return render_template('create_app.html')
    else:
        client_type = request.form['client_type']
        if client_type not in ('public', 'confidential'):
            return BAD_REQUEST 
        client_secret = (str(uuid.uuid4())
                if client_type == 'confidential'
                else None)
        client_id = rand_client_id()
        app = App(client_id=client_id,
                client_secret=client_secret, 
                user=request.session.user,
                redirect_uri=request.form['redirect_uri'],
                launch_uri=request.form['launch_uri'],
                name=request.form['appname'])
        db.session.add(app)
        db.session.commit()
        return redirect(url_for('ui.update_app', client_id=client_id))


@ui.route('/update_app/<client_id>', methods=['GET', 'POST'])
@require_login
def update_app(client_id):
    '''
    handle app info update here
    '''
    # make sure the user owns the app
    user = request.session.user
    app = (App.query
            .filter_by(user_id=user.email, client_id=client_id)
            .first())
    if app is None:
        return NOT_FOUND

    if request.method == 'GET':
        return render_template('update_app.html', app=app)
    else:
        app.redirect_uri = request.form['redirect_uri']
        app.launch_uri = request.form['launch_uri']
        app.name = request.form['appname']
        db.session.add(app)
        db.session.commit()
        return redirect(url_for('ui.update_app', client_id=app.client_id))


@ui.route('/launch/<client_id>', methods=['GET', 'POST'])
@require_login
def launch_app(client_id):
    # TODO refactor this. No DRY!!!
    user = request.session.user
    app = (App.query
            .filter_by(user_id=user.email, client_id=client_id)
            .first())
    if app is None:
        return NOT_FOUND 
    if request.method == 'GET':
        # prompt user to select a patient to launch
        # TODO make this more readable
        patients = [{'id': pt.resource_id, 'desc': json.loads(pt.data).get('text', {}).get('div', 'No description available')}
                for pt in Resource
                .query
                .filter_by(
                    owner_id=user.email,
                    resource_type='Patient')
                .all()]
        if len(patients) > 0:
            return render_template(
                    'launch_context.html',
                    cont_url=request.url,
                    resources=json.dumps({'Patient': patients}))
        else:
            selected_pt = None
    else:
        selected_pt = request.form['Patient']

    ctx = Context()
    if selected_pt is not None:
        ctx.context = json.dumps({'Patient': selected_pt})
    db.session.add(ctx)
    db.session.commit()
    # launch!
    launch_args = {
        'launch': ctx.id,
        'iss': get_api_base()
    }
    return redirect('%s?%s'% (
        app.launch_uri,
        urlencode(launch_args)))
