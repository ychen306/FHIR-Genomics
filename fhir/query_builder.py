'''
Build SQL query from FHIR search parameters
'''
from models import db, Resource, SearchParam
from fhir_spec import SPECS, REFERENCE_TYPES
import dateutil.parser
from util import iterdict
from functools import partial
import re

# REs used to parse FHIR's crazily complex search parameters 
PARAM_RE = re.compile(r'(?P<param>[^\.:]+)(?::(?P<modifier>[^\.:]+))?(?:\.(?P<chained_param>.+))?')
COMPARATOR_RE = r'(?P<comparator><|<=|>|>=)'
REFERENCE_RE = re.compile(r'(?:(?P<extern_base>.+/))?(?P<resource_type>.+)/(?P<resource_id>.+)')
TOKEN_RE = re.compile(r'(?:(?P<system>.+)?\|)?(?P<code>.+)')
NUMBER_RE = re.compile(r'%s?(?P<number>\d+(?:\.\d+)?)'% COMPARATOR_RE)
QUANTITY_RE = re.compile(r'%s\|(?P<system>.+)?\|(?P<code>.+)?'% NUMBER_RE.pattern)
DATE_RE = re.compile(r'%s?(?P<date>.+)' % COMPARATOR_RE)
COORD_RE = re.compile(r'(?P<chrom>.+):(?P<start>\d+)-(?P<end>\d+)') 
# there are two types of modifier: Resource modifier and others...
NON_TYPE_MODIFIERS = ['missing', 'text', 'exact'] 
# select helper
SELECT_FROM_SEARCH_PARAM = db.select([SearchParam.resource_id]).select_from(SearchParam)


class InvalidQuery(Exception):
    '''
    We use this to capture an invalid query
    so that we can return a HTTP 400 as required by FHIR's specs.
    '''
    pass 


def intersect_predicates(predicates):
    '''
    helper function to intersect a set of predicates
    '''
    return db.intersect(*[SELECT_FROM_SEARCH_PARAM.where(pred)
                          for pred in predicates])

def union_predicates(predicates):
    '''
    helper function to union a set of predicates
    '''
    return db.union(*[SELECT_FROM_SEARCH_PARAM.where(pred)
                          for pred in predicates]) 


def make_number_pred(param_data, param_val):
    '''
    Compile a number search parameter into a SQL predicate
    '''
    number = NUMBER_RE.match(param_val)
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


def make_quantity_pred(param_data, param_val):
    '''
    Compile a quantity search parameter into a SQL predicate
    '''
    quantity = QUANTITY_RE.match(param_val)
    if quantity is None:
        raise InvalidQuery

    preds = [] 
    if quantity.group('code') is not None:
        preds.append(SearchParam.code == quantity.group('code'))
    if quantity.group('system') is not None:
        preds.append(SearchParam.system == quantity.group('system')) 
    # tough stuff here... because quantity stored in the database can also have comparator
    # we have to build query based on the comparators from both the search and the db
    value = quantity.group('number') 
    comparator = quantity.group('comparator') 
    if comparator is None:
        comparator = '=' 

    val_preds = []
    if '<' in comparator:
        val_preds = [
            SearchParam.comparator.in_('<', '<='),
            SearchParam.comparator.quantity < value]
    elif '>' in comparison:
        val_preds = [
            SearchParam.comparator.in_('>', '>='),
            SearchParam.comparator.quantity > value]

    if '=' in comparator:
        val_preds.append(db.and_(
                            SearchParam.comparator.in_(None, '<=', '>='),
                            SearchParam.quantity == value))

    preds.append(db.or_(*val_preds)) 
    return db.and_(*preds)


def make_token_pred(param_data, param_val):
    '''
    Compile a token search parameter into a SQL predicate
    '''
    token = TOKEN_RE.match(param_val)
    if token is None:
        raise InvalidQuery

    pred = (SearchParam.code == token.group('code'))
    if token.group('system') is not None:
        pred = db.and_(pred, SearchParam.system == token.group('system')) 
    return pred


def make_string_pred(param_data, param_val):
    '''
    Comiple a string search parameter into a SQL predicate 

    When we store a resource in database,
    we store any text associated text search param by enclosing them in a pair of "::".
    E.g. "hello, world!" would be stored like this "::hello, world::".
    This is so that an exact search can be done simply by surrounding a the searched text
    with "::". (So a search like this `greeting:exact=hello world` will be translated like this
    SELECT ... FROM ... WHERE ... like "%::hello world::%").
    '''
    if param_data['modifier'] == 'exact':
        return SearchParam.text.like('%%::%s::%%' % param_val)
    else:
        # we split the search param here so that
        # an (inexact) search like "hello world" will get a hit 
        # for text like "hello tom" even though the whole text might not be hit.
        preds = [SearchParam.text.ilike('%%%s%%' % text)
                 for text in param_val.split()]
        return db.or_(*preds)


def make_date_pred(param_data, param_val):
    '''
    Compile a date search into a SQL predicate
    '''
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
    'quantity': make_quantity_pred,
    'number': make_number_pred,
    'token': make_token_pred,
    'date': make_date_pred,
    'string': make_string_pred
}

def make_coord_pred(coord): 
    coord_match = COORD_RE.match(coord) 
    if coord_match is None:
        raise InvalidQuery
    chrom = coord_match.group('chrom')
    start = coord_match.group('start')
    end = coord_match.group('end')
    return db.and_(
            Resource.resource_type == 'Sequence',
            Resource.chromosome == chrom,
            Resource.start <= end,
            Resource.end >= start) 


class QueryBuilder(object):
    def __init__(self, resource_owner):
        self.owner_id = resource_owner.email

    def make_reference_pred(self, param_data, param_val, resource_type):
        '''	
        make a predicate based on a ResourceReference

        Implement it as a method here because `make_reference_pred`,
        unlike other `make_**_pred`s, can potentially be dealing with
        chained query -- which requires us to reinvoke `build_query`
        method recursively.
        '''
        # a reference search must have exactly ONE resource type,
        # which is either specified via a modifier
        # or implied because a resource def. that says it can only be one resource type.
        # either way, we have to figure it out.
        modifier = param_data['modifier']
        possible_reference_types = REFERENCE_TYPES[resource_type][param_data['param']]
        if modifier not in possible_reference_types and (
            possible_reference_types[0] == 'Any' or
            len(possible_reference_types) > 1):
            # either can't deduct type of the referenced resource
            # or the modifier supplied is an invalid type
            raise InvalidQuery 
        referenced_type = (modifier
                        if modifier is not None and modifier not in NON_TYPE_MODIFIERS
                        else possible_reference_types[0]) 
        chained_param = param_data['chained_param']
        if chained_param is not None:
            # we have a chained query...
            chained_query = {chained_param: param_val}
            # make a subquery that finds referenced resoruce that fits the description
            reference_query = self.build_query(referenced_type,
                                         chained_query,
                                         id_only=True) 
            pred = db.and_(SearchParam.referenced_type==referenced_type,
                            SearchParam.referenced_id.in_(reference_query))
        else:
            pred = db.and_(SearchParam.referenced_id==param_val,
                            SearchParam.referenced_type==referenced_type)
    
        return pred


    def make_pred_from_param(self, resource_type, param_and_val, possible_param_types):
        '''
        Compile FHIR search parameter into a SQL predicate

        This is the "master" function that invokes other `make_*_pred` functions.
        `param_and_val` is the key-value pair of a parameter and its value
        `possible_param_types` is a dictionary maintaining the mapping between
        a name of a search parameter and it's type (string, number, etc).
        '''
        raw_param, param_val = param_and_val 
        matched_param = PARAM_RE.match(raw_param)
        if matched_param is None:
            # invalid search param
            return None
        param_data = matched_param.groupdict()
        param = param_data['param']
        modifier = param_data['modifier']
        if param not in possible_param_types:
            # an undefined search parameter is supplied
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
            # deal with FHIR's union search (e.g. `abc=x,y,z`) here
            alts = param_val.split(',')
            preds = [pred_maker(param_data, alt) for alt in alts]
            pred = db.or_(*preds)
    
        return db.and_(pred,
                       SearchParam.name==param,
                       SearchParam.param_type==possible_param_types[param],
                       SearchParam.owner_id==self.owner_id)
    
    def build_query(self, resource_type, params, id_only=False):
        '''
        Compile a SQL query from a set of FHIR search params
        
        If `id_only` is true, a SQL query that selects only `resource_id` will be returned
        '''
        query_args = [Resource.visible == True,
                      Resource.resource_type == resource_type,
                      Resource.owner_id == self.owner_id]
    
        valid_search_params = SPECS[resource_type]['searchParams']
        make_pred = partial(self.make_pred_from_param,
                            resource_type,
                            possible_param_types=valid_search_params) 
        predicates = [pred for pred in map(make_pred, iterdict(params))
                if pred is not None]
    
        # customized coordinate search parameter
        if 'coordinate' in params and resource_type == 'Sequence':
            coords = params['coordinate'].split(',') 
            coord_preds = map(make_coord_pred, coords)
            query_args.append(db.or_(*coord_preds))
        if len(predicates) > 0:
            query_args.append(
                Resource.resource_id.in_(intersect_predicates(predicates).alias())) 
        if '_id' in params:
            query_args.append(Resource.resource_id.in_(params['_id'].split(',')))

        if id_only:
            return db.select([Resource.resource_id]).\
                                    select_from(Resource).\
                                    where(db.and_(*query_args)).alias()
        else: 
            return Resource.query.filter(*query_args)
