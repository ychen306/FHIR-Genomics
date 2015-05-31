from os import path
from pysam import TabixFile, asTuple

SNP_FILE = path.join(path.dirname(path.abspath(__file__)), 'snps.sorted.txt.gz')

SNP_IDX = 1 
CHROM_IDX = 2
POS_IDX = 3

def get_snp_data(*args, **kwargs):
    return TabixFile(SNP_FILE, parser=asTuple()).\
            fetch(*args, **kwargs)

SNP_TABLE = {snp[SNP_IDX]: (snp[CHROM_IDX], snp[POS_IDX]) for snp in get_snp_data()}


def _get_snps(chrom, start, end): 
    snps = get_snp_data(chrom, start, end)
    return {snp[SNP_IDX]: (snp[CHROM_IDX], snp[POS_IDX]) for snp in snps}


def _slice(xs, offset, limit):
    '''
    safe version of xs[offset:offset+limit]
    return (sliced_collection, total_count)
    '''
    num_items = len(xs)
    offset = offset if offset < num_items else num_items
    bound = offset + limit
    bound = bound if bound < num_items else num_items
    return xs[offset:bound], num_items


def get_snps(chrom=None, start=None, end=None, offset=0, limit=100):
    snps = _get_snps(chrom, start, end)
    # can't rely on snps.keys being deterministic
    # TODO: make this faster (with something like OrderedDict)
    ids, count = _slice(sorted(snps.keys()), offset, limit) 
    return {snp: snps[snp] for snp in ids}, count 


def get_coord(rsid):
    return SNP_TABLE[rsid] 
