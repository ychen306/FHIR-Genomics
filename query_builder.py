import re
from functools import partial
from itertools import repeat
import dateutil.parser
from models import db, Resource, SearchParam
from fhir_spec import SPECS
from fhir_util import iterdict

PARAM_RE = re.compile(r'(?P<param>[^\.:]+)(?::(?P<modifier>[^\.:]+))?(?:\.(?P<chained_param>.+))?')
COMPARATOR_RE = r'(?P<comparator><|<=|>|>=)'
REFERENCE_RE = re.compile(r'(?:(?P<extern_base>.+)/)?(?P<resource_type>.+)/(?P<resource_id>.+)')
TOKEN_RE = re.compile(r'(?:(?P<system>.*)?\|)?(?P<code>.+)')
QUANTITY_RE = re.compile(r'%s?(?P<quantity>\d+(?:\.\d+)?)' % COMPARATOR_RE)
DATE_RE = re.compile(r'%s?(?P<date>.+)' % COMPARATOR_RE)
SELECT_FROM_SEARCH_PARAM = db.select([SearchParam.resource_id]).select_from(SearchParam)


class InvalidQuery(Exception):
    pass


def make_reference_pred(param_data, param_val, resource_type):
    '''	
    make a predicate basing on a ResourceReference
    :param param_data: meta data of a search param (i.e. modifier, param name, and chained param)
    :param param_val: value of the param
    :param resource_type: type of resource of the root of the reference element
    '''
    chained_param = param_data['chained_param']
    if chained_param is not None:
        # chained query
        modifier = param_data['modifier']
        possible_reference_types = REFERENCE_TYPES[
            resource_type][param_data['param']]
        if modifier not in possible_reference_types:
            # can't deduct type of the referenced resource
            # or invalid type
            raise InvalidQuery
        referenced_type = modifier if modifier is not None else possible_reference_types[0]
        chained_query = {chained_param: param_val}
        # make a subquery that finds referenced resoruce that fits the
        # description
        pred = db.and_(SearchParam.referenced_type == referenced_type,
                       SearchParam.referenced_id == build_query(referenced_type,
                                                                chained_query,
                                                                id_only=True).subquery())
    else:
        pred = (SearchParam.referenced_url == param_val)

    return pred


def make_quantity_pred(param_data, param_val):
    quantity = QUANTITY_RE.match(param_val)
    if not quantity:
        raise InvalidQuery
    try:
        value = float(quantity.group('quantity'))
        comparator = quantity.group('comparator')

        if comparator is not None:
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
    'reference': make_reference_pred,
    'quantity': make_quantity_pred,
    'token': make_token_pred,
    'date': make_date_pred,
    'string': make_string_pred
}


def make_pred_from_param(param_and_val, possible_param_types, resource_type):
    raw_param, param_val = param_and_val
    matched_param = PARAM_RE.match(raw_param)
    if matched_param is None:
        return None
    param_data = matched_param.groupdict()
    param = param_data['param']
    modifier = param_data['modifier']
    if param not in possible_param_types:
        return None

    param_type = possible_param_types[
        param] if modifier != 'text' else 'string'
    if modifier == 'missing':
        pred = ((SearchParam.missing == True)
                if param_val == 'true'
                else (SearchParam.missing == False))
    else:
        if param_type == 'reference':
            #pred = make_reference_pred(param_data, param_val, resource_type)
            pred_maker = partial(
                make_reference_pred, resource_type=resource_type)
        else:
            pred_maker = PRED_MAKERS[param_type]
            if pred_maker is None:
                raise InvalidQuery
        alts = param_val.split(',')
        preds = map(pred_maker, repeat(param_data, len(alts)), alts)
        pred = db.or_(*preds)

    return db.and_(pred,
                   SearchParam.name == param,
                   SearchParam.param_type == possible_param_types[param])


def intersect_predicates(predicates):
    return db.intersect(*[SELECT_FROM_SEARCH_PARAM.where(pred)
                          for pred in predicates])

# TODO: rewrite this using JOIN or (and) EXISTS


def build_query(resource_type, params, id_only=False):
    query_args = [Resource.visible == True,
                  Resource.resource_type == resource_type]

    valid_search_params = SPECS[resource_type]['searchParams']
    make_pred = partial(make_pred_from_param,
                        possible_param_types=valid_search_params,
                        resource_type=resource_type)
    predicates = filter(lambda p: p is not None,
                        map(make_pred, iterdict(params)))

    if len(predicates) > 0:
        query_args.append(
            Resource.resource_id.in_(
                    db.session.query(intersect_predicates(predicates))
                    .subquery()))

    if '_id' in params:
        query_args.append(Resource.resource_id == params.get('_id'))

    if id_only:
        return db.session.query(db.select([Resource.resource_id]).
                                select_from(Resource).
                                where(db.and_(*query_args)))

    return Resource.query.filter(*query_args)
