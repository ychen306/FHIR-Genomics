from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from api import api
from ui import ui
from database import db
from config import APP_CONFIG
import os


def register_blueprints(app):
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(ui)


def create_app(sync_db=False):
    app = Flask(__name__)
    app.config.update(APP_CONFIG)
    register_blueprints(app)
    db.init_app(app)
    if sync_db:
        setup_db(app)
    return app


def setup_db(app):
    with app.app_context():
        db.create_all()

if __name__ == "__main__":
    app = create_app(sync_db=True)
    setup_db(app)
    app.run(debug=True)
