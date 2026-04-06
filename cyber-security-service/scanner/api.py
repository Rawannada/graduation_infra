from flask import Flask, request, jsonify
import os
import tempfile
import sys

# ← DEE هنا: pipeline بتاعك الـ600 سطر
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import run as run_pipeline  # ✅ الـimport الصح

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

@app.route('/scan', methods=['POST'])
def scan_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "No filename"}), 400
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        filepath = tmp.name
        file.save(filepath)
    
    result = run_pipeline(filepath)  # ✅ يشغل الـ14 steps كامل من pipeline بتاعك
    
    os.unlink(filepath)
    
    return jsonify(result.to_dict())  # ✅ يرجع JSON كامل للـNode.js

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
