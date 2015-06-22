class TTAMOAuthError(Exception):
    '''
    Exception used to capture error resulting from
    attempt to get 23andme resources.

    This usually happens when an API call is issued but the user
    hasn't imported resources from 23andMe.
    '''
    pass
