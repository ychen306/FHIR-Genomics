import re
from sqlalchemy.ext.declarative import declarative_base
from database import db
from datetime import datetime
import json
from uuid import uuid4
from urlparse import urljoin
import fhir_util
from fhir_util import json_response, xml_response
from util import hash_password


class Resource(db.Model):
    __tablename__ = 'resource'

    resource_id = db.Column(db.String, primary_key=True)
    resource_type = db.Column(db.String(50), primary_key=True)
    update_time = db.Column(db.DateTime, primary_key=True)
    create_time = db.Column(db.DateTime)
    data = db.Column(db.Text)
    version = db.Column(db.Integer)
    visible = db.Column(db.Boolean)

    def __init__(self, resource_type, data):
        '''
        data is a json dictionary of a resource
        '''
        self.update_time = self.create_time = datetime.now()
        self.resource_type = resource_type
        self.resource_id = str(uuid4())
        self.data = json.dumps(data)
        self.version = 1
        self.visible = True

    def update(self, data):
        '''
        create a new resource with incremented version number
        and mark the older one unvisible
        '''
        self.visible = False
        latest = Resource(self.resource_type, data)
        latest.resource_id = self.resource_id
        latest.create_time = self.create_time
        latest.version = self.version + 1
        return latest

    def as_response(self, request, created=False):
        '''
        return the resource as a response
        '''
        status = '201' if created else '200'

        if request.format == 'json':
            response = json_response(status=status)
            response.data = self.data
        else:
            response = xml_response(status=status)
            response.data = fhir_util.json_to_xml(json.loads(self.data))

        response.headers['Location'] = urljoin(request.api_base, '%s/%s/_history/%s' % (
            self.resource_type,
            self.resource_id,
            self.version))

        return response

    def get_url(self, version_specific=False):
        url_elements = [self.resource_type, self.resource_id]
        if version_specific:
            url_elements.extend(('_history', str(self.version)))
        return '/'.join(url_elements)


class SearchParam(db.Model):

    '''
    represents a FHIR search param of type reference
    '''
    __tablename__ = 'searchparam'

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['resource_id', 'resource_type', 'update_time'],
            ['resource.resource_id', 'resource.resource_type', 'resource.update_time']),
        db.ForeignKeyConstraint(
            ['referenced_id', 'referenced_type', 'referenced_update_time'],
            ['resource.resource_id', 'resource.resource_type', 'resource.update_time']),
        {})

    id = db.Column(db.Integer, primary_key=True)
    # type of param (reference|date|string|token)
    param_type = db.Column(db.String(10))
    # foreign key reference to `Resource`
    resource_id = db.Column(db.String)
    resource_type = db.Column(db.String(50))
    update_time = db.Column(db.DateTime)
    # name of search param
    name = db.Column(db.String(50))
    # if this param is missing
    missing = db.Column(db.Boolean)
    # common display value of an element
    text = db.Column(db.Text, nullable=True)
    # reference param
    referenced_id = db.Column(db.String, nullable=True)
    referenced_type = db.Column(db.String(50), nullable=True)
    referenced_update_time = db.Column(db.DateTime, nullable=True)
    referenced_url = db.Column(db.String(500), nullable=True)
    # date param
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    # quantity param
    quantity = db.Column(db.Float, nullable=True)
    # token param
    system = db.Column(db.String(500), nullable=True)
    code = db.Column(db.String(100), nullable=True)

    resource = db.relationship('Resource',
                               foreign_keys=[resource_id,
                                             resource_type,
                                             update_time])

    referenced = db.relationship('Resource',
                                 foreign_keys=[referenced_id,
                                               referenced_type,
                                               referenced_update_time])

class User(db.Model):
    __tablename__ = 'User'

    email = db.Column(db.String(500), primary_key=True)
    hashed_password = db.Column(db.String(500))
    salt = db.Column(db.String(500))
    app_id = db.Column(db.String(100))
    app_secret = db.Column(db.String(100))
    app_name = db.Column(db.String(100))
    redirect_url = db.Column(db.String(100))
    # a user is a "client" that has permanent access
    client_id = db.Column(db.String, db.ForeignKey('Client.client_id'))
    client = db.relationship('Client')

    def check_password(self, password):
        hashed, _ = hash_password(password, self.salt)        
        return hashed == self.hashed_password


class Session(db.Model):
    __tablename__ = 'Session'

    id = db.Column(db.String(500), primary_key=True)
    user_id = db.Column(db.String(500), db.ForeignKey('User.email'))
    user = db.relationship('User')


class Access(db.Model):
    '''
    this represents a client's read/write access to a resource
    '''
    __tablename__ = 'Access'

    id = db.Column(db.Integer, primary_key=True) 
    client_id = db.Column(db.String(100), db.ForeignKey('Client.client_id'))
    resource_id = db.Column(db.String(100), db.ForeignKey('resource.resource_id'))
    resource_type = db.Column(db.String(100), db.ForeignKey('resource.resource_type'))
    # read or write
    access_type = db.Column(db.String(10))


class Client(db.Model):
    __tablename__ = 'Client'
    
    client_id = db.Column(db.String(100), primary_key=True)
    client_secret = db.Column(db.String(100))
    access_token = db.Column(db.String(100), nullable=True) 
    authorized = db.Column(db.Boolean)
    expire_at = db.Column(db.DateTime)
    # true for User false for app client
    can_expire = db.Column(db.Boolean)
