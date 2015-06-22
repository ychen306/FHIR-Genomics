'''
Adaptor for 23andMe API

NOTE: we don't store any 23andMe data except OAuth tokens and
profile ids associated with the user who granted the access
'''
from flask import request, g
from functools import wraps
from itertools import chain
from models import TTAMClient
from error import TTAMOAuthError
from ..models import Resource
from ..query_builder import COORD_RE, InvalidQuery
from util import slice_, get_snps, get_coord

# we use this to distinguish any 23andMe resource from internal resources
PREFIX = 'ttam_'
PREFIX_LEN = len(PREFIX)


def acquire_client():
    '''
    Get the client from database
    '''
    g.ttam_client = TTAMClient.query.get(request.authorizer.email)


def require_client(adaptor):
    '''
    decorator for functions that makes 23andme API call
    '''
    @wraps(adaptor)
    def checked(*args, **kwargs):
        if g.ttam_client is None:
            raise TTAMOAuthError
        return adaptor(*args, **kwargs)
    return checked 


def make_ttam_seq(snp, coord, pid):
    '''
    convert 23andMe snp into a Sequence Resource
    '''
    chrom, pos = coord
    narrative = '<div xmlns="http://www.w3.org/1999/xhtml">Genotype of %s is %s</div>'% (
            snp['location'],
            snp['call'])
    seq_data = {
        'resourceType': 'Sequence',
        'text': {
            'status': 'generated',
            'div': narrative
        },
        'genomeBuild': 'GRch37', 
        'type': 'dna',
        'chromosome': chrom,
        'startPosition': int(pos),
        'endPosition': int(pos),
        'observedSeq': list(snp['call']),
        'patient': {'reference': '/Patient/ttam_%s'% pid}
    }
    # we don't really care about the owner here
    # since the main purpose of using Resource class here
    # is to use its `as_repsonse` method
    seq = Resource('Sequence', seq_data, owner_id=None)
    seq.resource_id = 'ttam_%s|%s'% (snp['location'], pid)
    return seq


def make_ttam_patient(profile):
    '''
    convert a 23andme profile into a Patient Resource
    '''
    first_name = profile['first_name']
    last_name = profile['last_name']
    narrative = '<div xmlns="http://www.w3.org/1999/xhtml">%s %s</div>'% (first_name, last_name)
    patient_data = {
        'resourceType': 'Patient',
        'text': {
            'status': 'generated',
            'div': narrative
        },
        'name': [{
            'use': 'official',
            'family': [last_name],
            'given': [first_name]
         }]
    }
    patient = Resource('Patient', patient_data, owner_id=None)
    patient.resource_id = 'ttam_%s'% profile['id']
    return patient
    

def get_one_snp(internal_id):
    '''
    get an Sequence (SNP to be exact) from 23andme given an id

    format of the id is like this: {rsid}|{profile id}
    '''
    rsid, pid = internal_id.split('|')
    data_set = g.ttam_client.get_snps([rsid], [pid])
    pid, snps = next(data_set.iteritems())
    snp = snps[0]
    return make_ttam_seq(snp, get_coord(snp['location']), pid)


def get_one_patient(pid):
    '''
    given a 23andme profile id, return a Patient
    '''
    for patient in g.ttam_client.get_patients():
        if patient['id'] == pid:
            return make_ttam_patient(patient)


def extract_coord(coord):
    '''
    given a coord literal (e.g. "1:123-123123")
    return arguments for calling `get_snp_data`
    '''
    args = {}
    matched = COORD_RE.match(coord)
    if matched is None:
        raise InvalidQuery
    args['chrom'] = str(matched.group('chrom'))
    args['start'] = int(matched.group('start'))
    args['end'] = int(matched.group('end'))
    return args


def extract_coords(query):
    '''
    given a query (HTTP GET args) return a list of coords (args for calling `get_snp_data`)

    e.g. /Sequence?coordinate=1:123-123123,2:234-234234 is a query for TWO stretches of DNA,
    which should be parsed as
    ```
    [{
        'chrom': '1',
        'start': 123,
        'end': 123123
    }, {
        'chrom': '2',
        'start': 234,
        'end': 234234
    }]
    ```
    TODO Currently, when a query for chromosome, startPosition, and/or endPosition is issued,
    we let these argument overrite coordinate search (if there's any). In the future,
    we would like to do a proper intersection on these search criteria.
    '''
    overwrite_args = {}
    if 'chromosome' in query:
        overwrite_args['chrom'] = str(query['chromosome'])
    if 'startPosition' in query:
        overwrite_args['start'] = int(query['startPosition'])
    if 'endPosition' in query:
        overwrite_args['end'] = int(query['endPosition'])
    coords = ([dict(overwrite_args)]
            if 'coordinate' not in query or len(overwrite_args) > 0
            else map(extract_coord, query['coordinate'].split(',')))
    return coords
    

def extract_pids(extern_pids):
    '''
    a list of patient ids, extract all ids associated with 23andme profiles
    '''
    return [pid[PREFIX_LEN:]
            for pid in extern_pids
            if pid.startswith(PREFIX)]

def is_dna_query(query):
    '''
    given a query, check if it's a query for DNA sequences
    '''
    return ('type' not in query or
            'dna' in query['type'].split(','))


@require_client
def get_one(resource_type, resource_id):
    '''
    Get one Sequence/Patient resource from 23andme
    '''
    internal_id = resource_id[PREFIX_LEN:]
    if resource_type == 'Sequence':
        return get_one_snp(internal_id)
    else:
        return get_one_patient(internal_id)


# TODO support _id query for Sequence resources
@require_client
def get_many(resource_type, query, offset, limit):
    '''
    Get a list of Sequence/Patient resources from 23andMe
    and its total count (returned resources might be a slice).
    '''
    if resource_type == 'Sequence':
        if not is_dna_query(query):
            # 23andMe only has DNA sequences
            return [], 0 
        pids = (extract_pids(query['patient'].split(','))
                if 'patient' in query
                else g.ttam_client.get_profiles())
        if len(pids) == 0:
            return [], 0
        limit /= len(pids) 
        coords = extract_coords(query)
        snp_table = {}
        for coord in coords:
            snp_table.update(get_snps(**coord))
        rsids, num_snps = slice_(snp_table.keys(), offset, limit)
        if num_snps == 0 or len(rsids) == 0:
            # here we either find no snps
            # or we find snps but don't have to make any
            # query because of paging (i.e. limit is 0 or overly large offset)
            return [], num_snps
        snps_data = g.ttam_client.get_snps(rsids, pids)
        seqs = []
        for pid, snps in snps_data.iteritems():
            for snp in snps:
                coord = snp_table[snp['location']]
                seqs.append(make_ttam_seq(snp, coord, pid)) 
        return seqs, num_snps*len(pids)
    else:
        pids = (extract_pids(query['_id'].split(','))
                if '_id' in query
                else g.ttam_client.get_profiles())
        patients = [pt for pt in g.ttam_client.get_patients()
                if pt['id'] in pids]
        patients, count = slice_(patients, offset, limit)
        return map(make_ttam_patient, patients), count
