import re
from sqlalchemy.ext.declarative import declarative_base
from database import db
from datetime import datetime, timedelta
import json
from uuid import uuid4
from urlparse import urljoin
from fhir_spec import RESOURCES
from util import json_response, xml_response, json_to_xml, hash_password

# an oauth client can only keep access token for 1800 seconds
EXPIRE_TIME = 1800
# special resources to be launched with
LAUNCH_RESOURCES = set(['Patient', 'Encounter', 'Location'])


def commit_buffers(g): 
    for model, buf in g._nodep_buffers.iteritems():
        model.core_insert(buf) 


def save_buffer(g, model, obj):
    g._nodep_buffers.setdefault(model, []).append(obj.get_insert_params())



# TODO make this more efficient (maybe with a bit of boilerplate...)
class SimpleInsert(object): 
    '''
    Use this as a mixin (maybe there's another word for it), anyway
    Combine this with a ORM class you get to use SqlAlc's core inesrt easily.
    ''' 
    _relationships = None

    def __init__(self):
        raise NotImplementedError

    def _populate(self):
        '''
        populate attributes of a model

        sometimes a model has a relationshiop reflected by foreign key(s)
        this function finds such relationships and
        populates values of those foreign fields
        '''
        if self.__class__._relationships is None:
            self.__class__._relationships = {
                    rel.key: rel
                    for rel in self.__mapper__.relationships
                    }
        relationships = self.__class__._relationships
        update = {}
        for k, v in self.__dict__.iteritems():
            rel = relationships.get(k)
            if rel is not None and v is not None:
                for loc, rem in rel.local_remote_pairs:
                    update[loc.name] = v.__dict__.get(rem.name)

        self.__dict__.update(update) 

    def get_insert_params(self):
        self._populate()
        return {col.name: self.__dict__.get(col.name)
                for col in self.__table__.columns
                # ensure non-null primary_key
                if not col.primary_key or self.__dict__.get(col.name) is not None} 

    def add_and_commit(self):
        db.session.commit()
        self.__class__.core_insert([self.get_insert_params()])

    @classmethod
    def core_insert(cls, objs):
        db.engine.execute(cls.__table__.insert(), objs)


# TODO use autoincrment INT for resource_id instead of uuid (string)
class Resource(db.Model, SimpleInsert):
    '''
    Representation of a SNAPSHOT of a resource

    A Resource is either owned by a real user or is public and owned by the "super" user.
    Upon sign up, all public resources are copied and assigned an owner - the new user.
    this is how we manage the sandbox. The user can do what ever he or she wants to that set of 
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

    # speicalized columns for faster sequence resource query
    chromosome = db.Column(db.String, nullable=True)
    start = db.Column(db.Integer, nullable=True)
    end = db.Column(db.Integer, nullable=True)

    owner = db.relationship('User')

    def __init__(self, resource_type, data, owner_id):
        '''
        data is a json dictionary of a resource
        '''
        self.update_time = self.create_time = datetime.now()
        self.resource_type = resource_type
        self.resource_id = str(uuid4())
        self.data = json.dumps(data, separators=(',', ':'))
        self.version = 1
        self.visible = True
        self.owner_id = owner_id
        if resource_type == 'Sequence':
            self.chromosome = data['chromosome']
            self.start = data['startPosition']
            self.end = data['endPosition']

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
        return the resource as a HTTP response
        '''
        status = '201' if created else '200'

        if request.format == 'json':
            response = json_response(status=status)
            response.data = self.data
        else:
            response = xml_response(status=status)
            response.data = json_to_xml(json.loads(self.data))

        loc_header = 'Location' if created else 'Content-Location'
        response.headers[loc_header] = urljoin(request.api_base, '%s/%s/_history/%s' % (
            self.resource_type,
            self.resource_id,
            self.version))

        return response

    def get_url(self, version_specific=False):
        '''
        return the url to the resource
        '''
        url_elements = [self.resource_type, self.resource_id]
        if version_specific:
            url_elements.extend(('_history', str(self.version)))
        return '/'.join(url_elements)

    def get_reference(self):
        '''
        return the resource as a FHIR Reference
        '''
        return {'reference': self.get_url()}


class SearchParam(db.Model, SimpleInsert):

    '''
    represents a FHIR search param of type reference
    '''
    __tablename__ = 'searchparam'

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['owner_id', 'resource_id', 'resource_type', 'update_time'],
            ['resource.owner_id', 'resource.resource_id', 'resource.resource_type', 'resource.update_time']),
        db.ForeignKeyConstraint(
            ['owner_id', 'referenced_id', 'referenced_type', 'referenced_update_time'],
            ['resource.owner_id', 'resource.resource_id', 'resource.resource_type', 'resource.update_time']),
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
    comparator = db.Column(db.String(2), nullable=True)
    # token param
    system = db.Column(db.String(500), nullable=True)
    code = db.Column(db.String(100), nullable=True)

    # resource which this parameter belongs to
    resource = db.relationship('Resource',
                               foreign_keys=[owner_id,
                                             resource_id,
                                             resource_type,
                                             update_time])

    # resource this parameter is referencing,
    # if this a reference search parameter
    referenced = db.relationship('Resource',
                                 foreign_keys=[owner_id,
                                               referenced_id,
                                               referenced_type,
                                               referenced_update_time])


class User(db.Model):
    '''
    This has nothing to do with FHIR's concepts.
    Just a user who owns a set of resources.
    '''
    __tablename__ = 'User'

    email = db.Column(db.String(500), primary_key=True)
    hashed_password = db.Column(db.String(500))
    salt = db.Column(db.String(500))

    def check_password(self, password):
        hashed, _ = hash_password(password, self.salt)        
        return hashed == self.hashed_password

    def authorize_access(self, client, access_type, resource_types=RESOURCES):
        for resource_type in resource_types:
            access = Access(client_code=client.code,
                            resource_type=resource_type,
                            access_type=access_type)
            db.session.merge(access)


class App(db.Model):
    '''
    A registered app -- either public or confidential in SMART-on-FHIR's term
    Has many to one relationship with User. 
    '''
    __tablename__ = 'App'
    client_id = db.Column(db.String(100), primary_key=True)
    # null if public
    client_secret = db.Column(db.String(100), nullable=True)
    redirect_uri = db.Column(db.String(500))
    launch_uri = db.Column(db.String(500))
    name = db.Column(db.String(100)) 
    user_id = db.Column(db.String(500), db.ForeignKey('User.email'))

    user = db.relationship('User')


class Session(db.Model):
    '''
    Session management.
    Having this here because I am too lazy to read documentation of
    some of Flask's session extension packages and because I don't
    need much functionality anyway.
    '''
    __tablename__ = 'Session'

    id = db.Column(db.String(500), primary_key=True)
    user_id = db.Column(db.String(500), db.ForeignKey('User.email'))

    user = db.relationship('User')


class Access(db.Model):
    '''
    this represents an OAuth-consumer's read/write access to a resource type,
    '''
    __tablename__ = 'Access'

    # can be read or write
    access_type = db.Column(db.String(10), primary_key=True)
    client_code = db.Column(db.String(100), db.ForeignKey('Client.code'), primary_key=True)
    resource_type = db.Column(db.String(100), primary_key=True)


class Context(db.Model):
    '''
    this represents SMART-on-FHIR's application launch context
    '''
    __tablename__ = 'Context'
    id = db.Column(db.Integer, primary_key=True)
    # json representation of launch context
    context = db.Column(db.String(500), default="{}")


class Client(db.Model):
    '''
    An API client(OAuth consumer)
    
    This is different than an OAuth client.
    A consumer is a "bearer" of access token.
    Every user is ONE client, but there can be multiple CONSUMER belonging to 
    multiples user/client.
    '''
    __tablename__ = 'Client'
    
    code = db.Column(db.String, primary_key=True)
    client_id = db.Column(db.String(100), db.ForeignKey('App.client_id'), nullable=True)
    # denormalized so that we can quickly determine if it's a confidential client
    client_secret = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(500), nullable=True)
    access_token = db.Column(db.String(100), unique=True)
    authorizer_id = db.Column(db.String(100), db.ForeignKey('User.email'))
    authorized = db.Column(db.Boolean)
    expire_at = db.Column(db.DateTime, nullable=True)
    scope = db.Column(db.Text, nullable=True)
    context_id = db.Column(db.Integer, db.ForeignKey('Context.id'))
    
    context = db.relationship('Context') 
    authorizer = db.relationship('User')

    def __init__(self, authorizer, app, state, scope, context_id):
        self.client_id = app.client_id
        self.client_secret = app.client_secret
        self.access_token = str(uuid4())
        self.code = str(uuid4())
        self.authorizer = authorizer
        self.authorized = False
        self.state = state
        self.scope = scope
        self.context_id = context_id

    def grant_access_token(self):
        self.expire_at = datetime.now() + timedelta(seconds=3600)
        db.session.commit()
        grant = {
            'access_token': self.access_token,
            'token_type': 'bearer',
            'expires_in': 3600,
            'state': self.state,
            'scope': self.scope,
        } 
        # add content of launch context
        ctx = Context.query.get(self.context_id)
        launch_with = json.loads(ctx.context)
        for resource, resource_id in launch_with.iteritems():
            if resource in LAUNCH_RESOURCES:
                grant[resource.lower()] = resource_id
            else:
                grant['resource'] = '%s/%s'% (resource, resource_id)
        return grant
