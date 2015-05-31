from ..database import db
from datetime import datetime, timedelta
from urlparse import urljoin
from urllib import urlencode
import requests
import grequests

TOKEN_URI = 'https://api.23andme.com/token/' 
API_BASE = 'https://api.23andme.com/1/'

class TTAMOAuthError(Exception): pass

def assert_good_resp(resp):
    if resp.status_code != 200:
        raise TTAMOAuthError(resp.text)


class TTAMClient(db.Model): 
    user_id = db.Column(db.String(200), db.ForeignKey('User.email'), primary_key=True)
    access_token = db.Column(db.String(150), nullable=True)
    refresh_token = db.Column(db.String(150), nullable=True)
    expire_at = db.Column(db.DateTime, nullable=True)
    # might be a demo account
    api_base = db.Column(db.String(200), nullable=True)
    profiles = db.Column(db.Text, nullable=True)
    
    def __init__(self, code, user_id, ttam_config): 
        post_data = {
            'client_id': ttam_config['client_id'],
            'client_secret': ttam_config['client_secret'],
            'grant_type': 'authorization_code',
            'redirect_uri': ttam_config['redirect_uri'],
            'scope': ttam_config['scope'],
            'code': code
        }
        resp = requests.post(TOKEN_URI, data=post_data)
        assert_good_resp(resp)
        self._set_tokens(resp.json())
        # see if need to use demo data
        self.set_api_base()
        patients = self.get_patients()
        self.profiles = ' '.join(p['id'] for p in patients)
        self.user_id = user_id 

    def set_api_base(self):
        self.api_base = API_BASE
        if len(self.get_patients()) == 0:
            self.api_base = urljoin(API_BASE, 'demo')

    def _set_tokens(self, credentials):
        self.access_token = credentials['access_token']
        self.refresh_token = credentials['refresh_token']
        # just to be safe, set expire time 100 seconds earlier than acutal expire time
        self.expire_at = datetime.now() + timedelta(seconds=int(credentials['expires_in']-100))

    def is_expired(self):
        return datetime.now() > self.expire_at 

    def update(self, ttam_config):
        post_data = {
            'client_id': ttam_config['client_id'],
            'client_secret': ttam_config['client_secret'],
            'grant_type': 'refresh_token',
            'redirect_uri': ttam_config['redirect_uri'],
            'scope': ttam_config['scope'],
            'refresh_token': self.refresh_token
        }
        update_resp = requests.post(TOKEN_URI, data=post_data)
        assert_good_resp(update_resp)
        self._set_tokens(update_resp.json())
        db.session.add(self)
        db.session.commit()


    def has_patient(self, pid):
        return pid in self.profiles.split()


    def get_snps(self, query, patient=None):
        patients = [patient] if patient is not None else self.profiles.split()
        api_endpoint = urljoin(self.api_base, 'genotypes/')
        snps_str = ' '.join(query)
        args = {'locations': snps_str, 'format': 'embedded'}
        urls = (urljoin(api_endpoint, p)+"?"+urlencode(args)
                for p in patients)
        auth_header = self.get_header() 
        reqs = (grequests.get(u, headers=auth_header) for u in urls)
        resps = grequests.map(reqs) 
        if any(resp.status_code != 200 for resp in resps):
            raise TTAMOAuthError(map(lambda r: r.text, resps))
        patient_data = (resp.json() for resp in resps) 
        return {pdata['id']: pdata['genotypes'] for pdata in patient_data}

    def get_header(self):
        return {'Authorization': 'Bearer '+self.access_token} 

    def get_patients(self):
        auth_header = self.get_header()
        resp = requests.get(urljoin(self.api_base, 'names/'), headers=auth_header)
        assert_good_resp(resp)
        return resp.json()['profiles']

    def count_patients(self):
        return len(self.profiles.split())
