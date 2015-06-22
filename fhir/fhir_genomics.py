from flask import Flask, g
from api import api
from ui import ui
from oauth import oauth
from ttam.view import ttam
from database import db
from argparse import ArgumentParser


def register_blueprints(app):
    '''
    Register all blueprints with an app.
    `api` deals with FHIR's operational logic
    `oauth` deals with SMART on FHIR's OAuth protocol
    `ui` deals with user registration, etc
    `ttam` deals with 23andMe's API
    '''
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(oauth, url_prefix='/auth')
    app.register_blueprint(ui)
    app.register_blueprint(ttam, url_prefix='/ttam')


def create_app(config):
    '''
    Given a configuration object, create a WSGI(Flask) app
    See `APP_CONFIG` in ../config.py for example configuration.
    '''
    app = Flask(__name__)
    app.config.update(config)
    register_blueprints(app)
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app 
