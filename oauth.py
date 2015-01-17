'''
Takes care of oauth stuff here. Since it's only a demo server, grants are granted by default.
Currently it's only a mock security system. User written resources can be read by everyone.
'''
# TODO make this a real sandbox - i.e. a user's write won't be read by others
from flask.blueprints import Blueprint
from flask import request

oauth = Blueprint('auth', __name__)


def give_access(user, app, resources=[], can_write=False):
    '''
    grant access to a user's resources to an app
    '''
    pass

def init_user_access(user):
    '''
    give user read access to all public data
    '''
    pass


@oauth.route('/authorize')
def authorize():
    pass


@oauth.route('/token', methods=['POST'])
def exchange_token():
    pass




