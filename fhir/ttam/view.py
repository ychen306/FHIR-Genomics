from flask import Blueprint, current_app, redirect, request, Response
from urllib import urlencode
from models import TTAMClient, TTAMOAuthError
from ..ui import require_login, get_session
from ..database import db

ttam = Blueprint('ttam', __name__)

ttam.before_request(get_session)

NOT_ALLOWED = Response(status='405')

@ttam.route('/import')
@require_login
def import_from_ttam():
    '''
    redirect user to 23andme and prompt authorization to access his or her data
    '''
    ttam_client = TTAMClient.query.get(request.session.user.email)
    if ttam_client is not None:
        return NOT_ALLOWED
    ttam_config = current_app.config['TTAM_CONFIG']
    redirect_params = urlencode({
        'redirect_uri': ttam_config['redirect_uri'],
        'response_type': 'code',
        'client_id': ttam_config['client_id'],
        'scope': ttam_config['scope']}) 
    return redirect('%s?%s'% (ttam_config['auth_uri'], redirect_params))


@ttam.route('/recv_redirect')
@require_login
def recv_ttam_auth_code():
    '''
    handle redirect from 23andme's OAuth dance and initiate our 23andme client
    '''
    code = request.args.get('code')
    if code is None:
        return TTAMOAuthError 
    ttam_config = current_app.config['TTAM_CONFIG']
    ttam_client = TTAMClient(code, request.session.user.email, ttam_config)
    db.session.add(ttam_client)
    db.session.commit()
    return redirect('/') 


@ttam.route('/clear')
@require_login
def clear_ttam_data():
    '''
    removed the 23andme client associated with user in session
    '''
    ttam_client = TTAMClient.query.get(request.session.user.email)
    if ttam_client is None:
        return NOT_ALLOWED
    db.session.delete(ttam_client)
    db.session.commit()
    return redirect('/') 
