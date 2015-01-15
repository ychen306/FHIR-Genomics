from flask.blueprints import Blueprint
from flask import request
import fhir_api
from fhir_api import NOT_FOUND
from fhir_spec import RESOURCES
from urlparse import urljoin


API_URL_PREFIX = 'api'
api = Blueprint(API_URL_PREFIX, __name__)


@api.route('/<resource_type>', methods=['GET', 'POST'])
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
def read_history(resource_type, resource_id, version):
    if resource_type is not None and resource_type not in RESOURCES:
        return NOT_FOUND

    request.api_base = urljoin(request.url_root, API_URL_PREFIX) + '/'
    fhir_request = fhir_api.FHIRRequest(request)
    return fhir_api.handle_history(fhir_request, resource_type, resource_id, version)


@api.route('/test')
def test():
    from flask import request
    for i in request.args.iteritems():
        print i
    from models import *
    criteria = db.session.query(db.select([SearchParam.resource_id]).select_from(SearchParam).where(
        db.and_(SearchParam.name == "status", SearchParam.code == "final"))).subquery()
    resources = Resource.query.filter(
        Resource.resource_id == criteria).all()
    print resources
    return 'hello, world!'
