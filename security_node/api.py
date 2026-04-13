from flask import Flask, request, jsonify
import os
import tempfile

from scanner.pipeline import run as run_pipeline

app = Flask(__name__)
# Security: Max upload size set to 20MB
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for Load Balancers or Docker."""
    return jsonify({"status": "healthy", "service": "pdf-security-scanner"})

@app.route('/scan', methods=['POST'])
def scan_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "No filename"}), 400

    suffix = os.path.splitext(file.filename)[1].lower() or ".pdf"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        filepath = tmp.name
        file.save(filepath)

    try:
        result = run_pipeline(filepath)
        return jsonify(result.to_dict()), 200
    except Exception as e:
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e)
        }), 500
    finally:
        if os.path.exists(filepath):
            os.unlink(filepath)

if __name__ == '__main__':
    # Use Waitress or Gunicorn in production instead of app.run()
    # e.g., waitress-serve --port=5000 api:app
    print("[*] Starting Secure API Server (Dev Mode)...")
    app.run(debug=False, host='0.0.0.0', port=5000)