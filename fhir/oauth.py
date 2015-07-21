from flask.blueprints import Blueprint
from flask import request, render_template, Response, redirect, jsonify
import re
import base64 
from urllib import urlencode
from fhir_spec import RESOURCES
from models import db, Session, User, Client, App
from ui import require_login

oauth = Blueprint('auth', __name__)

# RE to parse SMART on FHIR's permission (scope), 
# which looks like this "user/Patient.read"
PERMISSION_RE = re.compile(r'(?P<scope>user)/(?P<resource_type>(?:\w+)|\*)\.(?P<type>read|write)')
BA_RE = re.compile(r'Basic (.+)') 


class BadRequest(Exception):
    '''
    We use this to capture an invalid request during during our OAuth dance
    '''
    pass


class OAuthScope(object):
    '''
    Representation of a scope in SMART-on-FHIR
    '''
    desc_tmpl = '%s access to all of your %s resources'

    def __init__(self, permission_str):
        '''
        parse a scope
        '''
        permission = PERMISSION_RE.match(permission_str)
        if permission is None:
            raise BadRequest
        self.scope = permission.group('scope')
        requested_resource = permission.group('resource_type')
        if requested_resource == '*':
            self.is_wildcard = True
        elif requested_resource in RESOURCES:
            self.is_wildcard = False
            self.resource = requested_resource
        else:
            raise BadRequest
        
        self.access_type = permission.group('type')

    def to_readable(self):
        '''
        generate readable content for showing it to user
        '''
        readable = {'is_write': self.access_type == 'write'}
        if self.is_wildcard:
            resource = ''
        else:
            resource = '<b>%s</b> '% self.resource
        readable['desc'] = self.__class__.desc_tmpl% (
                                        self.access_type,
                                        resource)
        return readable

    def get_access_from_user(self, user, client):
        '''
        Get access from user based on the scope
        '''
        if self.is_wildcard:
            user.authorize_access(client, self.access_type)
        else:
            user.authorize_access(client, self.access_type, [self.resource])


@oauth.route('/authorize', methods=['GET', 'POST'])
@require_login
def authorize():
    if request.method == 'GET':
        if request.args['response_type'] != 'code':
            raise BadRequest

        # find app requested this authorization
        app = App.query.filter_by(
                client_id=request.args['client_id'],
                redirect_uri=request.args['redirect_uri']).first()
        if app is None:
            raise BadRequest    
        client = Client(authorizer=request.session.user,
                        app=app,
                        state=request.args.get('state'),
                        scope=request.args['scope'])
        db.session.add(client)
        # parse requested scopes
        scopes = map(OAuthScope, request.args['scope'].split(' '))
        readable_accesses = map(OAuthScope.to_readable, scopes)  
        # we grant access despite user's reaction so that we don't have to keep tract of requested scope
        # security is being taken care of by marking the authorized client as un authorized
        for scope in scopes:
            scope.get_access_from_user(request.session.user, client)
        db.session.commit()
        return render_template('authorization.html',
                    appname=app.name,
                    accesses=readable_accesses,
                    auth_code=client.code)
    elif request.form['authorize'] == 'yes':
        # authorize the client and redirect
        client = Client.query.filter_by(code=request.form['auth_code']).first()
        if client is None:
            raise BadRequest
        client.authorized = True 
        db.session.commit()
        app = App.query.filter_by(client_id=client.client_id).first()
        redirect_uri = app.redirect_uri
        redirect_args = {'code': request.form['auth_code']}
        if client.state is not None:
            redirect_args['state'] = client.state
        return redirect('%s?%s'% (redirect_uri,
                                urlencode(redirect_args))) 
    else:
        return redirect('/')
 

@oauth.route('/token', methods=['POST'])
def exchange_token():
    '''
    exchange access token with authorization code
    '''
    assert request.form['grant_type'] == 'authorization_code'

    client_id = request.form['client_id']
    code = request.form['code']
    redirect_uri = request.form['redirect_uri']
    client = Client.query.filter_by(code=code,
                                    client_id=client_id,
                                    authorized=True,
                                    expire_at=None).first()
    assert client is not None
    app = App.query.filter_by(client_id=client_id).first()
    assert app is not None and app.redirect_uri == redirect_uri

    # authenticate confidential client
    if app.client_secret is not None:
        auth_header = request.headers.get('Authorization')
        assert auth_header is not None
        match = BA_RE.match(auth_header)
        assert match is not None 
        pair = base64.b64decode(match.group(1)).split(':')
        assert len(pair) == 2
        cid, csecret = pair
        assert (client.client_id == cid and
                client.client_secret == csecret) 

    return jsonify(client.grant_access_token()) 


@oauth.before_request
def get_session():
    session_id = request.cookies.get('session_id') 
    request.session = Session.query.filter_by(id=session_id).first()


@oauth.errorhandler(AssertionError)
def handle_invalid_auth_request(_):
    return Response(status='400')
