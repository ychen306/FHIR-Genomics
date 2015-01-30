import re
from functools import partial
from itertools import repeat
import dateutil.parser
from models import db, Resource, SearchParam
from fhir_spec import SPECS, REFERENCE_TYPES
from fhir_util import iterdict

PARAM_RE = re.compile(r'(?P<param>[^\.:]+)(?::(?P<modifier>[^\.:]+))?(?:\.(?P<chained_param>.+))?')
COMPARATOR_RE = r'(?P<comparator><|<=|>|>=)'
REFERENCE_RE = re.compile(r'(?:(?P<extern_base>.+)/)?(?P<resource_type>.+)/(?P<resource_id>.+)')
TOKEN_RE = re.compile(r'(?:(?P<system>.*)?\|)?(?P<code>.+)')
NUMBER_RE = re.compile(r'%s?(?P<number>\d+(?:\.\d+)?)' % COMPARATOR_RE)
DATE_RE = re.compile(r'%s?(?P<date>.+)' % COMPARATOR_RE)
COORD_RE = re.compile(r'(?P<chrom>.+):(?P<start>\d+)-(?P<end>\d+)')
SELECT_FROM_SEARCH_PARAM = db.select([SearchParam.resource_id]).select_from(SearchParam)

NON_TYPE_MODIFIERS = ['missing', 'text', 'exact']

class InvalidQuery(Exception):
    pass



def intersect_predicates(predicates):
    return db.intersect(*[SELECT_FROM_SEARCH_PARAM.where(pred)
                          for pred in predicates])

def make_coord_preds(coord_str):
    coord = COORD_RE.match(coord_str)
    if coord is None:
        raise InvalidQuery
    chrom = coord.group('chrom')
    start = coord.group('start')
    end = coord.group('end')
    right_chrom = db.and_(SearchParam.text == ('::%s::'% chrom),
                        SearchParam.name == 'chromosome',
                        SearchParam.resource_type == 'Sequence')
    # query end >= start
    right_start = db.and_(SearchParam.quantity <= end,
                        SearchParam.name == 'start-position',
                        SearchParam.resource_type == 'Sequence')
    # query start <= end
    right_end = db.and_(SearchParam.quantity >= start,
                        SearchParam.name == 'end-position',
                        SearchParam.resource_type == 'Sequence')

    return [right_chrom, right_start, right_end]

    
def make_number_pred(param_data, param_val):
    number = QUANTITY_RE.match(param_val)
    if not number:
        raise InvalidQuery
    try:
        value = float(number.group('number'))
        comparator = number.group('comparator')

        if comparator is None:
            pred = (SearchParam.quantity == value)
        elif comparator == '<':
            pred = (SearchParam.quantity < value)
        elif comparator == '<=':
            pred = (SearchParam.quantity <= value)
        elif comparator == '>':
            pred = (SearchParam.quantity > value)
        elif comparator == '>=':
            pred = (SearchParam.quantity >= value)

        return pred

    except ValueError:
        raise InvalidQuery


def make_token_pred(param_data, param_val):
    token = TOKEN_RE.match(param_val)
    if not token:
        raise InvalidQuery

    pred = (SearchParam.code == token.group('code'))
    if token.group('system') is not None:
        pred = db.and_(pred, SearchParam.system == token.group('system'))

    return pred


def make_string_pred(param_data, param_val):
    if param_data['modifier'] == 'exact':
        return SearchParam.text.like('%%::%s::%%' % param_val)
    else:
        preds = [SearchParam.text.ilike('%%%s%%' % text)
                 for text in param_val.split()]
        return db.or_(*preds)

# FIXME: this is a hack that approximates any iso8601s datetime as its closest instant
# and hence doesn't have very high accuracy for range based date comparison


def make_date_pred(param_data, param_val):
    date = DATE_RE.match(param_val)
    if date is None:
        raise InvalidQuery
    try:
        value = dateutil.parser.parse(date.group('date'))
        comparator = date.group('comparator')

        if comparator is None:
            pred = db.and_(SearchParam.start_date <= value,
                           SearchParam.end_date >= value)
        elif comparator in ('<', '<='):
            pred = (SearchParam.end_date <= value)
        elif comparator in ('>', '>='):
            pred = (SearchParam.start_date >= value)

        return pred

    except ValueError:
        raise InvalidQuery

PRED_MAKERS = {
    'number': make_number_pred,
    'token': make_token_pred,
    'date': make_date_pred,
    'string': make_string_pred
}


class QueryBuilder(object):
    def __init__(self, resource_owner):
        self.owner_id = resource_owner.email

    def make_reference_pred(self, param_data, param_val, resource_type):
        '''	
        make a predicate basing on a ResourceReference
        :param param_data: meta data of a search param (i.e. modifier, param name, and chained param)
        :param param_val: value of the param
        :param resource_type: type of resource of the root of the reference element
        '''
        modifier = param_data['modifier']
        possible_reference_types = REFERENCE_TYPES[resource_type][param_data['param']]
        if modifier not in possible_reference_types and (
            possible_reference_types[0] == 'Any' or
            len(possible_reference_types) > 1):
            # can't deduct type of the referenced resource
            # or invalid type
            raise InvalidQuery
    
        referenced_type = (modifier
                        if modifier is not None and modifier not in NON_TYPE_MODIFIERS
                        else possible_reference_types[0])
    
        chained_param = param_data['chained_param']
        if chained_param is not None:
            # chained query
            chained_query = {chained_param: param_val}
            # make a subquery that finds referenced resoruce that fits the
            # description
            reference_query = self.build_query(referenced_type,
                                         chained_query,
                                         id_only=True)
    
            pred = db.and_(SearchParam.referenced_type == referenced_type,
                            SearchParam.referenced_id.in_(reference_query))
        else:
            pred = db.and_(SearchParam.referenced_id == param_val,
                            SearchParam.referenced_type == referenced_type)
    
        return pred


    def make_pred_from_param(self, resource_type, param_and_val, possible_param_types):
        raw_param, param_val = param_and_val 
        matched_param = PARAM_RE.match(raw_param)
        if matched_param is None:
            return None
        param_data = matched_param.groupdict()
        param = param_data['param']
        modifier = param_data['modifier']
        if param not in possible_param_types:
            return None
    
        param_type = possible_param_types[param] if modifier != 'text' else 'string'
        if modifier == 'missing':
            pred = ((SearchParam.missing == True)
                    if param_val == 'true'
                    else (SearchParam.missing == False))
        else:
            if param_type == 'reference':
                pred_maker = partial(self.make_reference_pred,
                                resource_type=resource_type)
            else:
                pred_maker = PRED_MAKERS[param_type]
                if pred_maker is None:
                    raise InvalidQuery

            alts = param_val.split(',')
            preds = map(pred_maker, repeat(param_data, len(alts)), alts)
            pred = db.or_(*preds)
    
        return db.and_(pred,
                       SearchParam.name == param,
                       SearchParam.param_type == possible_param_types[param],
                       SearchParam.owner_id == self.owner_id)
    
    # TODO: rewrite this using JOIN or (and) EXISTS
    def build_query(self, resource_type, params, id_only=False):
        '''
        If `id_only` is true, a SQL query that selects `resource_id` will be returned
        '''
        query_args = [Resource.visible == True,
                      Resource.resource_type == resource_type,
                      Resource.owner_id == self.owner_id]
    
        valid_search_params = SPECS[resource_type]['searchParams']
        make_pred = partial(self.make_pred_from_param,
                            resource_type,
                            possible_param_types=valid_search_params)

        predicates = filter(lambda p: p is not None,
                            map(make_pred, iterdict(params)))
    
        # customized coordinate query
        if 'coordinate' in params and resource_type == 'Sequence':
            # TODO: support union (e.g. something like coordinate=chr1:123-234,chr2:234-345)
            predicates.extend(make_coord_preds(params['coordinate']))
    
        if len(predicates) > 0:
            query_args.append(
                Resource.resource_id.in_(intersect_predicates(predicates).alias()))
    
        if '_id' in params:
            query_args.append(Resource.resource_id == params.get('_id'))
    
        if id_only:
            return db.select([Resource.resource_id]).\
                                    select_from(Resource).\
                                    where(db.and_(*query_args)).alias()
    
        return Resource.query.filter(*query_args)
