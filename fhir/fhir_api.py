from flask import Response, render_template, g
from database import db
from models import Resource, SearchParam
import fhir_parser
from util import json_response, xml_response, xml_bundle_response, xml_to_json, json_to_xml
from fhir_spec import SPECS, REFERENCE_TYPES
from query_builder import QueryBuilder, InvalidQuery
from indexer import index_resource
import ttam
import json
from urlparse import urljoin
from urllib import urlencode
from datetime import datetime
from lxml import etree

# TODO: support composite search param

PAGE_SIZE = 50
BUNDLE_TITLE = 'SMART Genomics Atom Feed'

NOT_FOUND = Response(status='404')
GONE = Response(status='410')
NOT_ALLOWED = Response(status='405')
BAD_REQUEST = Response(status='400')
NO_CONTENT = Response(status='204')


def find_latest_resource(resource_type, resource_id, owner_id):
    return Resource.query.filter_by(
        resource_type=resource_type,
        resource_id=resource_id,
        owner_id=owner_id).order_by(Resource.version.desc()).first()


class FHIRRequest(object):
    '''
    represent a request in FHIR's RESTful framework
    '''
    def __init__(self, request, is_resource=True):
        self.args = request.args
        self.format = self.args.get('_format', 'xml')
        self.api_base = request.api_base
        self.url = request.url
        self.base_url = request.base_url
        self.authorizer = request.authorizer
        # paging params
        self.count = int(self.args.get('_count', PAGE_SIZE))
        self.offset = int(self.args.get('_offset', 0))

        if request.method in ('POST', 'PUT'):
            # process data as a dictionary
            if self.format == 'xml':
                dataroot = etree.fromstring(request.data)
                resource_type = dataroot.tag.split('}')[-1]
                self.data = xml_to_json(dataroot, resource_type)
            else:
                self.data = json.loads(request.data)

    def _get_url(self, is_prev):
        '''
        helper function for generating paged links
        '''
        args = self.args.to_dict(flat=False)
        if is_prev:
            new_offset = self.offset - self.count
        else:
            new_offset = self.offset + self.count

        args.update({'_offset': new_offset})

        return "%s?%s" % (self.base_url, urlencode(args, doseq=True))

    def get_next_url(self):
        '''
        return the url of next page
        '''
        return self._get_url(is_prev=False)

    def get_prev_url(self):
        '''
        return the url of previous page
        '''
        return self._get_url(is_prev=True)


class FHIRBundle(object): 
    '''
    Represent a bundle in FHIR
    ''' 
    def __init__(self, query, request, version_specific=False, ttam_resource=None):
        self.api_base = request.api_base
        self.request_url = request.url
        self.data_format = request.format
        self.version_specific = version_specific
        self.update_time = datetime.now().isoformat()

        self.resources = query.\
                limit(request.count).\
                offset(request.offset).all()
        self.resource_count = query.count() 
        self.next_url = (request.get_next_url()
                         if len(self.resources) + request.offset < self.resource_count
                         else None) 
        self.prev_url = (request.get_prev_url()
                         if request.offset - request.count >= 0
                         else None)

        if ttam_resource is not None:
            # get data from 23and me
            num_resources = len(self.resources) 
            ttam_offset = (request.offset - self.resource_count
                    if request.offset >= self.resource_count
                    else 0)
            ttam_limit = request.count - num_resources
            ttam_resources, ttam_count = ttam.get_many(ttam_resource, request.args, ttam_offset, ttam_limit)
            self.resource_count += ttam_count 
            if num_resources < request.count:
                self.resources.extend(ttam_resources)


    def _make_bundle(self):
        '''
        helper function for creating a bundle as a dictionary
        '''
        bundle = {}

        entries = []
        for resource in self.resources:

            relative_resource_url = resource.get_url(self.version_specific)
            resource_url = urljoin(self.api_base, relative_resource_url)
            resource_content = json.loads(resource.data)
            if self.data_format == 'xml':
                resource_content = json_to_xml(resource_content)

            entries.append({
                'content': resource_content,
                'created': resource.create_time.isoformat(),
                'updated': resource.update_time.isoformat(),
                'id': resource_url,
                'title': relative_resource_url
            })

        bundle['entry'] = entries

        links = [{'rel': 'self', 'href': self.request_url}]
        if self.next_url is not None:
            links.append({
                'rel': 'next',
                'href': self.next_url
            })
        if self.prev_url is not None:
            links.append({
                'rel': 'previous',
                'href': self.prev_url
            })

        bundle['link'] = links
        bundle['totalResults'] = self.resource_count
        bundle['updated'] = self.update_time
        bundle['title'] = BUNDLE_TITLE
        bundle['id'] = self.request_url
        bundle['resourceType'] = 'Bundle'
        return bundle

    def as_response(self):
        '''
        return a bundle as a response
        '''
        bundle_dict = self._make_bundle()

        if self.data_format == 'json':
            response = json_response()
            response.data = json.dumps(bundle_dict)
        else:
            response = xml_bundle_response()
            response.data = render_template('bundle.xml', **bundle_dict)

        return response


def handle_create(request, resource_type):
    '''
    handle FHIR create operation
    '''
    correctible = (request.format == 'xml')
    valid, search_elements = fhir_parser.parse_resource(
        resource_type, request.data, correctible)
    if not valid:
        return BAD_REQUEST

    resource = Resource(resource_type, request.data, owner_id=request.authorizer.email)
    index_resource(resource, search_elements)

    return resource.as_response(request, created=True)


def handle_read(request, resource_type, resource_id):
    '''
    handle FHIR read operation
    '''
    if resource_type in ('Patient', 'Sequence') and resource_id.startswith('ttam_'):
        resource = ttam.get_one(resource_type, resource_id)
    else:
        resource = find_latest_resource(resource_type, resource_id, owner_id=request.authorizer.email)

    if resource is None:
        return NOT_FOUND
    elif not resource.visible:
        return GONE

    return resource.as_response(request)


def handle_update(request, resource_type, resource_id):
    '''
    handle FHIR update operation
    '''
    old = find_latest_resource(resource_type, resource_id, owner=request.authorizer)
    if old is None:
        return NOT_ALLOWED

    correctible = (request.format == 'xml')
    valid, search_elements = fhir_parser.parse_resource(
        resource_type, request.data, correctible)
    if not valid:
        return BAD_REQUEST

    new = old.update(request.data)
    index_resource(new, search_elements)

    return new.as_response(request)


def handle_search(request, resource_type):
    '''
    handle FHIR search operation
    '''
    try:
        query_builder = QueryBuilder(request.authorizer)
        search_query = query_builder.build_query(resource_type, request.args)
    except InvalidQuery:
        return BAD_REQUEST
    ttam_resource = None
    if (resource_type in ('Patient', 'Sequence') and
            g.ttam_client is not None):
        ttam_resource = resource_type 
    resp_bundle = FHIRBundle(search_query, request, ttam_resource=ttam_resource)
    return resp_bundle.as_response()


def handle_delete(request, resource_type, resource_id):
    '''
    handle FHIR delete operation
    '''
    resource = find_latest_resource(resource_type, resource_id)
    if resource.visible:
        resource.visible = False
        db.session.add(resource)
        db.session.commit()
        return NO_CONTENT
    else:
        return NOT_FOUND


def handle_history(request, resource_type, resource_id, version):
    '''
    handle FHIR history operation
    '''
    query_args = []
    if version is not None:
        query_args.append(Resource.version == version)
    if resource_type is not None:
        query_args.append(Resource.resource_type == resource_type)
    if resource_id is not None:
        query_args.append(Resource.resource_id == resource_id)

    hist_query = Resource.query.filter(*query_args)

    if version is not None:
        # corresponds to GET [api base]/[resource]/[resource_id]/_history/[version]
        # don't render as a bundle in this case
        resource = hist_query.first()
        if resource is None:
            return NOT_FOUND
        else:
            return resource.as_response(request)

    resp_bundle = FHIRBundle(hist_query, request, version_specific=True)

    return resp_bundle.as_response()
