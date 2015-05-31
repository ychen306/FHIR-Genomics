from flask import Flask, g
from api import api
from ui import ui
from oauth import oauth
from ttam.view import ttam
from database import db
from argparse import ArgumentParser


def register_blueprints(app):
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(oauth, url_prefix='/auth')
    app.register_blueprint(ui)
    app.register_blueprint(ttam, url_prefix='/ttam')


def create_app(config):
    app = Flask(__name__)
    app.config.update(config)
    register_blueprints(app)
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app 

if __name__ == "__main__":
    arg_parser = ArgumentParser()
    args = arg_parser.parse_args()
    app = create_app(APP_CONFIG)
    if args.option == 'run':
        app.run(debug=True) 
    elif args.option == 'clear':
        clear_db(app)
