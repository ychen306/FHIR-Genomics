from flask.blueprints import Blueprint
from flask import request, Response, g
import fhir_api
import fhir_error
from fhir_spec import RESOURCES
from query_builder import InvalidQuery
from models import Access, Session, Client, commit_buffers
import ttam
import util
from functools import partial, wraps
from datetime import datetime
import re

api = Blueprint('api', __name__)


AUTH_HEADER_RE = re.compile(r'Bearer (?P<access_token>.+)')


def verify_access(request, resource_type, access_type):
    '''
    Verify if a request should be accessing a type of resource
    '''
    if request.session is not None:
        # if a request has a session then it's definitely a user
        # and a user has access to all of his or her resources
        request.authorizer = request.session.user
        return True
    elif request.client is not None:
        # not a user but a OAuth consumer
        # check database and verify if the consumer has access
        request.authorizer = request.client.authorizer
        if datetime.now() > request.client.expire_at:
            return False
        accesses = Access.query.filter_by(client_code=request.client.code,
                                            access_type=access_type,
                                            resource_type=resource_type)
        return accesses.count() > 0
    else:
        return False


def protected(view):
    '''
    Decorator to make sure a view a request is only handled as requested
    when it has proper access.
    '''
    @wraps(view)
    def protected_view(*args, **kwargs):
        access_type = 'read' if request.method == 'GET' else 'write' 
        resource_type = (args[0]
                        if len(args) > 0
                        else kwargs['resource_type'])
        if not verify_access(request, resource_type, access_type):
            # no access
            return fhir_error.inform_forbidden() 
        else:
            # has access
            # try to acquire a 23andme API client since the request
            # might be accessing 23andme's API
            ttam.acquire_client()
            return view(*args, **kwargs)

    return protected_view


@api.before_request
def get_client():
    '''
    check if a user is logged-in via current session
    '''
    session_id = request.cookies.get('session_id') 
    request.session = Session.query.filter_by(id=session_id).first()
    request.client = None
    auth_header = AUTH_HEADER_RE.match(request.headers.get('authorization', ''))
    if auth_header is not None:
        request.client = Client.query.\
                    filter_by(access_token=auth_header.group('access_token'),
                        authorized=True).\
                    first()
        

@api.route('/<resource_type>', methods=['GET', 'POST'])
@protected
def handle_resource(resource_type):
    if resource_type not in RESOURCES:
        return fhir_error.inform_not_found()

    g.api_base = request.api_base = util.get_api_base() 
    fhir_request = fhir_api.FHIRRequest(request)

    if request.method == 'GET':
        return fhir_api.handle_search(fhir_request, resource_type)
    else:
        return fhir_api.handle_create(fhir_request, resource_type)


@api.route('/<resource_type>/<resource_id>', methods=['GET', 'PUT', 'DELETE'])
@protected
def handle_resources(resource_type, resource_id):
    if resource_type not in RESOURCES:
        return fhir_error.inform_not_found()

    request.api_base = get_api_base() 
    fhir_request = fhir_api.FHIRRequest(request, is_resource=False)

    if request.method == 'GET':
        return fhir_api.handle_read(fhir_request,
                                    resource_type,
                                    resource_id)
    elif request.method == 'PUT':
        return fhir_api.handle_update(fhir_request,
                                      resource_type,
                                      resource_id)
    else:
        return fhir_api.handle_delete(fhir_request,
                                      resource_type,
                                      resource_id)


@api.route('/_history', defaults={'resource_type': None, 'resource_id': None, 'version': None})
@api.route('/<resource_type>/_history', defaults={'resource_id': None, 'version': None})
@api.route('/<resource_type>/<resource_id>/_history', defaults={'version': None})
@api.route('/<resource_type>/<resource_id>/_history/<version>')
@protected
def read_history(resource_type, resource_id, version):
    if resource_type is not None and resource_type not in RESOURCES:
        return fhir_error.inform_not_found()

    request.api_base = get_api_base() 
    fhir_request = fhir_api.FHIRRequest(request)
    return fhir_api.handle_history(fhir_request, resource_type, resource_id, version)

@api.before_request
def init_globals():
    '''
    SQLAlchemy CORE can be a lot more performant than its ORM when doing bulk insert
    What we do here is we "cache" all insert that doensn't have any dependency issue
    in the memory and inesrt them at once.

    To do so, before every request, we declare a global variable (in flasks term) for caching,
    and after every request, we "commit" those buffers.
    '''
    g._nodep_buffers = {}

@api.after_request
def cleanup(resp):
    '''
    See doc of `init_globals`
    '''
    commit_buffers(g)
    return resp


@api.errorhandler(ttam.TTAMOAuthError)
def handle_ttam_no_client(_):
    '''
    If a request is attempting to access a 23andme resource and gets an error.
    (e.g. the user hasn't imported resources 23andme),
    we simply return a 404.
    The resource might be or not be in the server, but without a client it's 
    hard to check with 23andme, so we simply pretend that resource is not here.
    '''
    return fhir_error.inform_not_found()


@api.errorhandler(InvalidQuery)
def handle_invalid_query(_):
    return fhir_error.inform_bad_request()
