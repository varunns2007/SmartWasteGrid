import os
from flask import Flask, render_template, Response
from backend.flask_db.db import db
from backend.routes.api import api_bp
from backend.camera_stream import gen_frames, start_camera_auto_logger

def create_app(test_config=None):
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))

    app.config['SECRET_KEY'] = 'smartwastegrid-secret-key-2026'
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', 'waste_platform.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/video_feed')
    def video_feed():
        return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route('/favicon.ico')
    def favicon():
        return "", 204

    with app.app_context():
        db.create_all()

    try:
        start_camera_auto_logger(app)
    except Exception:
        pass

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
