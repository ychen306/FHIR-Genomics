from flask.blueprints import Blueprint
from flask import request, Response, g
import fhir_api
from fhir_api import NOT_FOUND
from fhir_spec import RESOURCES
from models import Access, Session, Client, commit_buffers
import ttam
from urlparse import urljoin
from functools import partial, wraps
from datetime import datetime
import re

API_URL_PREFIX = 'api'
api = Blueprint('api', __name__)


AUTH_HEADER_RE = re.compile(r'Bearer (?P<access_token>.+)')
FORBIDDEN = Response(status='403')

def verify_access(request, resource_type, access_type):
    if request.session is not None:
        request.authorizer = request.session.user
        return True
    elif request.client is not None:
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
    @wraps(view)
    def protected_view(*args, **kwargs):
        access_type = 'read' if request.method == 'GET' else 'write' 
        resource_type = (args[0]
                        if len(args) > 0
                        else kwargs['resource_type'])
        if not verify_access(request, resource_type, access_type):
            return FORBIDDEN
        else:
            ttam.acquire_client()
            return view(*args, **kwargs)

    return protected_view


@api.before_request
def get_client():
    session_id = request.cookies.get('session_id') 
    request.session = Session.query.filter_by(id=session_id).first()
    request.client = None
    auth_header = AUTH_HEADER_RE.match(request.headers.get('authorization', ''))
    if auth_header is not None:
        request.client = Client.query.\
                    filter_by(
                        access_token=auth_header.group('access_token'),
                        authorized=True).\
                    first()
        

@api.route('/<resource_type>', methods=['GET', 'POST'])
@protected
def handle_resource(resource_type):
    if resource_type not in RESOURCES:
        return NOT_FOUND

    g.api_base = request.api_base = urljoin(request.url_root, API_URL_PREFIX) + '/'
    fhir_request = fhir_api.FHIRRequest(request)

    if request.method == 'GET':
        return fhir_api.handle_search(fhir_request, resource_type)
    else:
        return fhir_api.handle_create(fhir_request, resource_type)


@api.route('/<resource_type>/<resource_id>', methods=['GET', 'PUT', 'DELETE'])
@protected
def handle_resources(resource_type, resource_id):
    if resource_type not in RESOURCES:
        return NOT_FOUND

    request.api_base = urljoin(request.url_root, API_URL_PREFIX) + '/'
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
        return NOT_FOUND

    request.api_base = urljoin(request.url_root, API_URL_PREFIX) + '/'
    fhir_request = fhir_api.FHIRRequest(request)
    return fhir_api.handle_history(fhir_request, resource_type, resource_id, version)

@api.before_request
def init_globals():
    g._nodep_buffers = {}

@api.after_request
def cleanup(resp):
    commit_buffers(g)
    return resp

@api.errorhandler(ttam.NoTTAMClient)
def handle_ttam_no_client(_):
    return NOT_FOUND
