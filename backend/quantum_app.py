import os
import sys

# Ensure CSW project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template, Response
from flask_cors import CORS
from backend.flask_db.db import db
from backend.routes.api import api_bp
from backend.camera_stream import gen_frames, start_camera_auto_logger

def create_app():
    app = Flask(__name__, template_folder=os.path.join(PROJECT_ROOT, "templates"))
    CORS(app)
    
    # Configure SQLite database
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'waste_platform.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Home route serving the React Dashboard
    @app.route('/')
    def index():
        return render_template('index.html')

    # Live Webcam Stream Route
    @app.route('/video_feed')
    def video_feed():
        return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'error.log'), 'a') as f:
            traceback.print_exc(file=f)
        return str(e), 500

    with app.app_context():
        db.create_all()
        try:
            from backend.seed_db import seed_data_if_empty
            seed_data_if_empty(app)
        except Exception as e:
            print(f"[!] Warning seeding database: {e}")
        start_camera_auto_logger(app)
        
    return app

if __name__ == '__main__':
    app = create_app()
    print("==================================================")
    print("      UNIFIED SMARTWASTE FRONTEND DASHBOARD       ")
    print("==================================================")
    print(" Running web server on http://127.0.0.1:5000")
    print(" Video Feed Endpoint: http://127.0.0.1:5000/video_feed")
    print("==================================================")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
