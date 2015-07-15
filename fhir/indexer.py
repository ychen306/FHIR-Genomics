from flask import g
from models import db, Resource, SearchParam, save_buffer
from query_builder import REFERENCE_RE
import dateutil.parser
from functools import partial
from models import save_buffer


def get_text(data):
    '''
    Helper function to index a string for search later.
    See doc. for `index_string`.
    '''
    if isinstance(data, list):
        return '::'.join(data)
    return str(data)


def index_string(index, element):
    '''
    produce a '::' delimited string of values within element
    e.g. {'family': ['Chen'], 'given': ['Yishen']} would give "::Chen::Yishen::"
    The same principle applies to text components of other data types.

    We do this so in the case of an exact search we can simply do something like
    this `SELECT ... FROM .. like "::Chen::"
    '''
    if isinstance(element, dict):
        text = '::'.join(map(get_text, element.values()))
    else:
        text = str(element) 
    index['text'] = '::%s::' % (text,)
    return index


# TODO: index all Coding if it's a CodeableConcept
def index_token(index, element):
    '''
    index a CodeableConcept, Coding, and code
    Note: this only indexes the first Coding if it's a CodeableConcept
    '''
    # element is a code
    if isinstance(element, basestring):
        index['code'] = element
        return index

    text_elements = []
    if element.get('coding') or element.get('text'):
        # element is CodeableConcept
        coding = element.get('coding', ({},))[0]
    else:
        # element is Coding
        coding = element

    if 'display' in coding:
        text_elements.append(coding['display'])

    if 'text' in element:
        text_elements.append(element['text'])

    index['code'] = coding.get('code')
    index['system'] = coding.get('system', '')

    index['text'] = '::%s::' % ('::'.join(text_elements), )
    return index


def index_reference(index, element, owner_id, g):
    '''
    index a reference
    '''
    if 'display' in element:
        index['text'] = '::%s::' % (element['display'],)

    if 'reference' in element:
        reference_url = element['reference']
        reference = REFERENCE_RE.match(reference_url)
        index['referenced_url'] = reference_url
        if reference.group('extern_base') is None or reference.group('extern_base') == g.api_base:
            # reference is internal reference, we want to link the reference to a Resource
            index['referenced'] = Resource.query.filter_by(resource_type=reference.group('resource_type'),
                                                           resource_id=reference.group('resource_id'),
                                                           owner_id=owner_id,
                                                           visible=True).first()
            
    return index


def index_quantity(index, element):
    '''
    index a quantity
    '''
    index['code'] = element.get('code')
    index['system'] = element.get('system')
    index['quantity'] = element.get('value')
    index['comparator'] = element.get('comparator', '=')
    return index


def index_number(index, element):
    '''
    index a number
    '''
    index['quantity'] = float(element)
    return index


def index_date(index, element):
    '''
    index a period, a date, or a datetime
    '''
    start = None
    end = None
    if 'start' in element or 'end' in element:
        # period
        start = dateutil.parser.parse(element.get('start', '999-1-1'))
        end = dateutil.parser.parse(element.get('end', '9999-1-1'))
    else:
        # date or datetime
        # TODO date like this `1776-7-4` is actually a range,
        # treat it differently than a true instant like `999-1-1:00:00:00`
        start = end = dateutil.parser.parse(element) 
    index.update({
        'start_date': start,
        'end_date': end
    })
    return index


SEARCH_INDEX_FUNCS = {
    'string': index_string,
    'token': index_token,
    'quantity': index_quantity,
    'number': index_number,
    'date': index_date
}


def get_search_args(resource, spec):
    '''
    get init args for SearchParam given value of a search parameter
    '''
    return {
        'resource': resource,
        'param_type': spec['type'],
        'name': spec['name'],
    }


def index_resource(resource, search_elements, g=g):
    resource.add_and_commit()
    params = []
    for search_param in search_elements:
        args = get_search_args(resource, search_param['spec'])
        elements = search_param['elements']
        if len(elements) == 0:
            save_buffer(g, SearchParam, SearchParam(missing=True, **args))
        else:
            for element in elements:
                if args['param_type'] == 'reference':
                    index_func = partial(index_reference, owner_id=resource.owner_id, g=g)
                else:
                    index_func = SEARCH_INDEX_FUNCS[args['param_type']]
                if index_func is None:
                    continue
                search_index = index_func(dict(args), element) 
                save_buffer(g, SearchParam, SearchParam(missing=False, **search_index))
