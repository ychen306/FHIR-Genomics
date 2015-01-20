'''
Takes care of oauth stuff here
'''
from flask.blueprints import Blueprint
from flask import request, render_template, Response, redirect, jsonify
import re
from urllib import urlencode
from fhir_spec import RESOURCES
from models import db, Session, User, Client
from ui import require_login

oauth = Blueprint('auth', __name__)

PERMISSION_RE = re.compile(r'(?P<scope>user)/(?P<resource_type>(?:\w+)|\*)\.(?P<type>read|write)')

class BadRequest(Exception):
    pass


class OAuthScope(object):
    desc_tmpl = '%s access to all of your %s resources'

    def __init__(self, permission_str):
        permission = PERMISSION_RE.match(permission_str)
        if permission is None:
            raise BadRequest
        self.scope = permission.group('scope')
        self.is_wildcard = False
        requested_resource = permission.group('resource_type')
        if requested_resource == '*':
            self.is_wildcard = True
        elif requested_resource in RESOURCES:
            self.resource = requested_resource
        else:
            raise BadRequest
        
        self.access_type = permission.group('type')

    def to_readable(self):
        '''
        generate readable content and show it to user
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
        if self.is_wildcard:
            user.authorize_access(client, self.access_type)
        else:
            user.authorize_access(client, self.access_type, (self.resource,))

@oauth.before_request
def get_session():
    session_id = request.cookies.get('session_id') 
    request.session = Session.query.filter_by(id=session_id).first()

@oauth.errorhandler(BadRequest)
def handle_invalid_auth_request(error):
    return Response(status='400')


@oauth.route('/authorize', methods=['GET', 'POST'])
@require_login
def authorize():
    if request.method == 'GET':
        if request.args['response_type'] != 'code':
            raise BadRequest

        # find dev user whose app requested this authorization
        client_user = User.query.filter_by(app_id=request.args['client_id'],
                                            redirect_url=request.args['redirect_uri']).first()
        if client_user is None:
            raise BadRequest    

        client = Client(request.session.user,
                        client_user,
                        request.args.get('state'))
        # parse requested scopes
        scopes = map(OAuthScope, request.args['scope'].split(' '))
        accesses = map(OAuthScope.to_readable, scopes)  
        # we grant access despite user's reaction so that we don't have to keep tract of requested scope
        # security is being taken care of by marking the authorized client as un authorized
        for scope in scopes:
            scope.get_access_from_user(request.session.user, client)
        db.session.commit()
        return render_template('authorization.html',
                    appname=client_user.app_name,
                    accesses=accesses,
                    auth_code=client.code)
    elif request.form['authorize'] == 'yes':
        client = Client.query.filter_by(code=request.form['auth_code']).first()
        if client is None:
            raise BadRequest
        client.authorized = True 
        db.session.commit()
        client_user = User.query.filter_by(app_id=client.client_id).first()
        redirect_url = client_user.redirect_url
        redirect_args = {'code': request.form['auth_code']}
        if client.state is not None:
            redirect_args['state'] = client.state
        return redirect('%s?%s'% (redirect_url,
                                urlencode(redirect_args))) 
    else:
        return redirect('/')
 

@oauth.route('/token', methods=['POST'])
def exchange_token():
    if request.form['grant_type'] != 'authorization_code':
        raise BadRequest
    client_id = request.form['client_id']
    client_secret = request.form['client_secret']
    code = request.form['code']
    redirect_uri = request.form['redirect_uri']
    client = Client.query.filter_by(code=code,
                                    client_id=client_id,
                                    client_secret=client_secret,
                                    authorized=True,
                                    expire_at=None).first()
    if client is not None:
        client_user = User.query.filter_by(app_id=client_id).first()
        if client_user is None or client_user.redirect_url != redirect_uri:
            raise BadRequest
    else:
        raise BadRequest

    return jsonify(client.grant_access_token())




