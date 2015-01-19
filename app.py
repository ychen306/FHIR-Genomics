from flask import Flask
from api import api
from ui import ui
from oauth import oauth
from database import db
import example_loader
from config import APP_CONFIG


def register_blueprints(app):
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(oauth, url_prefix='/auth')
    app.register_blueprint(ui)


def create_app():
    app = Flask(__name__)
    app.config.update(APP_CONFIG)
    register_blueprints(app)
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app
                
def load_sample_data(app):
    '''
    re-create all tables and load sample data
    '''
    with app.app_context():
        db.drop_all()
        db.create_all()
        example_loader.load_examples()
        db.session.commit()

if __name__ == "__main__":
    from sys import argv
    app = create_app()
    if len(argv) > 1 and argv[1] == 'reload':
        load_sample_data(app)
    else:
        app.run(debug=True)


