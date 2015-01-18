import re
from sqlalchemy.ext.declarative import declarative_base
from database import db
from datetime import datetime, timedelta
import json
from uuid import uuid4
from urlparse import urljoin
import fhir_util
from fhir_util import json_response, xml_response
from fhir_spec import RESOURCES
from util import hash_password


# an oauth client can only keep access token for 1800 seconds
EXPIRE_TIME = 1800


class Resource(db.Model):
    '''
    a Resource is either public or has an `owner`.
    upon sign up, all public resources are copied and asign an owner - the new user.
    this is how we manage the sandbox. The user can do what ever he wants to that set of 
    resources, and since resources are replicated, what a user does to a resource won't
    affect that of another user.
    '''
    __tablename__ = 'resource'

    # upon app startup, we create a resource whose owner's email is 'super', which is impossible
    # for a real user, who has to use a syntatically valid email address
    owner_id = db.Column(db.String, db.ForeignKey('User.email'), primary_key=True)
    resource_id = db.Column(db.String, primary_key=True)
    resource_type = db.Column(db.String(50), primary_key=True)
    update_time = db.Column(db.DateTime, primary_key=True)
    create_time = db.Column(db.DateTime)
    data = db.Column(db.Text)
    version = db.Column(db.Integer)
    visible = db.Column(db.Boolean)

    owner = db.relationship('User')

    def __init__(self, resource_type, data, owner_id):
        '''
        data is a json dictionary of a resource
        '''
        self.update_time = self.create_time = datetime.now()
        self.resource_type = resource_type
        self.resource_id = str(uuid4())
        self.data = json.dumps(data)
        self.version = 1
        self.visible = True
        self.owner_id = owner_id

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

    def get_reference(self):
        return {'reference': self.get_url()}


class SearchParam(db.Model):

    '''
    represents a FHIR search param of type reference
    '''
    __tablename__ = 'searchparam'

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['owner_id', 'resource_id', 'resource_type', 'update_time'],
            ['resource.owner_id', 'resource.resource_id', 'resource.resource_type', 'resource.update_time']),
        db.ForeignKeyConstraint(
            ['referenced_id', 'referenced_type', 'referenced_update_time'],
            ['resource.resource_id', 'resource.resource_type', 'resource.update_time']),
        {})

    id = db.Column(db.Integer, primary_key=True)
    # type of param (reference|date|string|token)
    param_type = db.Column(db.String(10))
    # foreign key reference to `Resource`
    owner_id = db.Column(db.String)
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
                                             update_time,
                                             owner_id])

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

    def check_password(self, password):
        hashed, _ = hash_password(password, self.salt)        
        return hashed == self.hashed_password

    def authorize_access(self, client, access_type, resource_types=RESOURCES):
        for resource_type in resource_types:
            access = Access(client=client,
                            resource_type=resource_type,
                            access_type=access_type)
            db.session.add(access)


class Session(db.Model):
    __tablename__ = 'Session'

    id = db.Column(db.String(500), primary_key=True)
    user_id = db.Column(db.String(500), db.ForeignKey('User.email'))
    user = db.relationship('User')


class Access(db.Model):
    '''
    this represents a client's read/write access to a resource type,
    note that an access can be rescricted to a patient's resources
    '''
    __tablename__ = 'Access'

    id = db.Column(db.Integer, primary_key=True) 
    client_id = db.Column(db.String(100), db.ForeignKey('Client.client_id'))
    client = db.relationship('Client')
    resource_type = db.Column(db.String(100))
    patient_id = db.Column(db.String(500),
                    db.ForeignKey('resource.resource_id'),
                    nullable=True)
    # read, write, or admin (shortcut for read+write)
    access_type = db.Column(db.String(10))
    


class Client(db.Model):
    __tablename__ = 'Client'
    
    client_id = db.Column(db.String(100), primary_key=True)
    client_secret = db.Column(db.String(100))
    access_token = db.Column(db.String(100), nullable=True)
    authorizer_id = db.Column(db.String(100), db.ForeignKey('User.email'))
    authorizer = db.relationship('User')
    is_user = db.Column(db.Boolean) 
    expire_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, authorizer, is_user=False):
        self.client_id = str(uuid4())
        self.client_secret = str(uuid4())
        self.authorizer = authorizer
        self.access_token = str(uuid4())
        self.is_user = is_user
        if not is_user:
            self.expire_at = datetime.now() + timedelta(seconds=EXPIRE_TIME)
        
        
