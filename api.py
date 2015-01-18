from flask.blueprints import Blueprint
from flask import request, Response
import fhir_api
from fhir_api import NOT_FOUND
from fhir_spec import RESOURCES
from urlparse import urljoin
from models import Session, Client
from functools import partial, wraps

API_URL_PREFIX = 'api'
api = Blueprint(API_URL_PREFIX, __name__)

FORBIDDEN = Response(status='403')

def verify_access(request, resource_type, access_type):
    if request.accessor is None:
        return False
    request.authorizer = request.accessor.authorizer
    return True

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
            return view(*args, **kwargs)

    return protected_view


@api.before_request
def get_accessor():
    session_id = request.cookies.get('session_id') 
    session = Session.query.filter_by(id=session_id).first()
    if session is not None:
        request.accessor = Client.query.filter_by(is_user=True,
                                                authorizer=session.user).first()
    else:
        request.accessor = None


@api.route('/<resource_type>', methods=['GET', 'POST'])
@protected
def handle_resource(resource_type):
    if resource_type not in RESOURCES:
        return NOT_FOUND

    request.api_base = urljoin(request.url_root, API_URL_PREFIX) + '/'
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
