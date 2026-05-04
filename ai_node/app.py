# =============================
# CSV Insight AI - Backend Integrated Version
# Works with your Node.js uploadCSVFile
# =============================

import os
import re
import json
import time
import logging
import warnings
import pandas as pd
import numpy as np
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename
import plotly.express as px
import plotly.utils
import base64
import requests
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from AutoClean import AutoClean
    AUTOCLEAN_AVAILABLE = True
except ImportError:
    AUTOCLEAN_AVAILABLE = False

warnings.filterwarnings("ignore")

app = Flask(__name__, template_folder="templates")
app.secret_key = "csv-insight-ai-v2"

# Use WSL path for cross-platform access
WSL_BASE_PATH = r"\\wsl.localhost\Ubuntu\home\rawannada\graduation_infra\backend-node"
UPLOAD_FOLDER = os.path.join(WSL_BASE_PATH, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
logger.info(f"Upload folder set to: {UPLOAD_FOLDER}")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
MAX_SUGGESTIONS = 6

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================
# Utils
# =============================

def detect_column_type(series):
    if pd.api.types.is_datetime64_any_dtype(series): return "date"
    if pd.api.types.is_numeric_dtype(series): return "numeric"
    return "text"

def load_cleaned_df(file_id):
    """Load autoclean CSV using file_id from Node.js backend"""
    # جرب ملف CSV أولاً
    file_name = f"{file_id}_autoclean.csv"
    cleaned_path = os.path.join(UPLOAD_FOLDER, file_name)
    
    if os.path.exists(cleaned_path):
        return pd.read_csv(cleaned_path)
    
    # Fallback: جرب ملف Parquet القديم لو مش موجود
    parquet_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_autoclean.parquet")
    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    
    return None

# =============================
# AI Charts (same as before)
# =============================

def ask_ai(prompt):
    try:
        r = requests.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=30)
        return r.json().get("response", "")
    except:
        return ""

def ai_suggest_charts(df):
    col_profiles = {}
    for col in df.columns:
        dtype = detect_column_type(df[col])
        profile = {"type": dtype}
    
    prompt = f"""You are data analyst. Profile: {json.dumps(col_profiles)}
Suggest {MAX_SUGGESTIONS} charts JSON only..."""
    
    raw = ask_ai(prompt)
    return []  

def fig_to_json(fig):
    import plotly.io as pio
    raw = json.loads(pio.to_json(fig))
    # fix bdata logic
    return raw

def build_chart(df, chart):
    # نفس الكود القديم للـ charts (bar, line, etc.)
    return fig_to_json(fig)  # placeholder

# =============================
# 🚀 MAIN ROUTES - Updated
# =============================

@app.route("/")
def index():
    return render_template("index.html")  # نفس HTML بتاعك

@app.route("/test_path")
def test_path():
    return {
        "BASE_DIR": BASE_DIR,
        "UPLOAD_FOLDER": UPLOAD_FOLDER,
        "exists": os.path.exists(UPLOAD_FOLDER),
        "listdir": os.listdir(UPLOAD_FOLDER) if os.path.exists(UPLOAD_FOLDER) else []
    }

@app.route("/api_status")
def api_status():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return jsonify({"ok": r.status_code == 200, "model": OLLAMA_MODEL})
    except:
        return jsonify({"ok": False})

@app.route("/upload", methods=["POST"])
def upload():
    """🎯 Receives Node.js backend JSON → AutoClean → Ready for analysis"""
    print("🚀 DEBUG: Request received at /upload", flush=True)
    try:
        # Capture raw JSON for debugging
        raw_json = request.get_data(as_text=True)
        logger.info(f"Raw JSON received: {raw_json}")
        
        backend_data = request.get_json()
        logger.info(f"Parsed JSON: {backend_data}")
        
        if not backend_data or "CSV" not in backend_data:
            return jsonify({"error": "No CSV data found in request"}), 400
            
    except Exception as e:
        logger.error(f"JSON parsing error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400

    csv_info = backend_data["CSV"]
    file_id = csv_info["_id"]
    
    linux_path = csv_info["path"]  # مثال: /home/rawannada/graduation_infra/backend-node/uploads/file.csv
    
    base_linux_dir = "/home/rawannada/graduation_infra/backend-node"
    if linux_path.startswith(base_linux_dir):
        relative_path = linux_path[len(base_linux_dir):].lstrip("/")
    else:
        relative_path = linux_path
    
    windows_relative = relative_path.replace("/", "\\")
    
    file_path = os.path.join(WSL_BASE_PATH, windows_relative)
    
    file_path = file_path.replace("\\\\wsl.localhost\\", "\\\\wsl$\\")
    
    logger.info(f"Resolved file path: {file_path}")
    
    if not os.path.exists(file_path):
        logger.warning(f"File not found at primary path, trying sub-folder fallback...")
        user_id = csv_info.get("userId")
        filename = csv_info.get("fileName")
        
        file_path = os.path.join(UPLOAD_FOLDER, user_id, filename)
        logger.info(f"Trying correct fallback path: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"❌ File not found at: {file_path}")
        return jsonify({"error": f"File not found at {file_path}"}), 404
    
    # Simple file access test
    try:
        logger.info(f"📁 Testing file access: {file_path}")
        with open(file_path, 'rb') as f:
            f.read(100)  # Read first 100 bytes to test access
        logger.info(f"✅ File access successful!")
    except Exception as e:
        logger.error(f"❌ File access failed: {str(e)}")
        return jsonify({"error": f"File access failed: {str(e)}"}), 500

    # We're not using AutoClean anymore, so skip this check

    # 2. Manual Cleaning with detailed error reporting
    raw_shape = None
    clean_shape = None
    cleaned_path = None
    autoclean_status = "failed"
    
    try:
        logger.info(f"🔄 Starting safe cleaning for file_id: {file_id}")
        
        # Read file directly with pandas
        logger.info(f"Reading file with pandas: {file_path}")
        #df = pd.read_csv(file_path, engine='python')
        logger.info(f"Reading file with pandas: {file_path}")
        
        try:
            df = pd.read_csv(file_path, sep=None, engine='python', encoding='utf-8-sig', on_bad_lines='skip')
        except Exception as e:
            logger.warning(f"First read attempt failed: {e}, trying cp1252...")
            df = pd.read_csv(file_path, sep=None, engine='python', encoding='cp1252', on_bad_lines='skip')

        logger.info(f"✅ Success! Data loaded. Shape: {df.shape}")
        
        
        
        # Log critical DataFrame info
        logger.info(f"✅ File read successfully. Shape: {df.shape}")
        logger.info(f"Columns: {list(df.columns)}")
        logger.info(f"First row: {df.iloc[0].to_dict() if len(df) > 0 else 'Empty DataFrame'}")
        
        raw_shape = df.shape
        
        try:
            df_clean = df.copy()
            
            # 1. Remove duplicate rows
            logger.info("Removing duplicate rows...")
            df_clean = df_clean.drop_duplicates()
            logger.info(f"✅ Removed {len(df) - len(df_clean)} duplicates")
            
            # 2. Fill empty values
            logger.info("Filling NA values...")
            df_clean = df_clean.fillna("N/A")
            logger.info(f"✅ Filled NA values")
        except Exception as cleaning_error:
            logger.error(f"❌ CRITICAL CLEANING ERROR: {str(cleaning_error)}", exc_info=True)
            logger.error(f"DataFrame shape during error: {df.shape}")
            logger.error(f"DataFrame columns during error: {list(df.columns)}")
            # Use original df as fallback
            df_clean = df
            logger.warning("⚠️ Using original DataFrame as fallback")
        
        clean_shape = df_clean.shape
        logger.info(f"✅ Cleaning completed: {raw_shape} → {clean_shape}")
        
        # Save as CSV
        cleaned_file_name = f"{file_id}_autoclean.csv"
        cleaned_path = os.path.join(UPLOAD_FOLDER, cleaned_file_name)
        
        try:
            logger.info(f"Saving cleaned data to: {cleaned_path}")
            df_clean.to_csv(cleaned_path, index=False)
            logger.info(f"✅ Saved cleaned data successfully")
            autoclean_status = "success"
        except Exception as e:
            logger.error(f"❌ SAVE ERROR: {str(e)}")
            logger.error(f"DataFrame shape during save error: {df_clean.shape}")
            logger.error(f"DataFrame columns during save error: {list(df_clean.columns)}")
            cleaned_path = None
            autoclean_status = "partial"
    except Exception as big_error:
        logger.error(f"❌ Big Error in cleaning: {str(big_error)}")
        autoclean_status = "failed"

    # 3. Response نهائي
    # 3. Response نهائي مع التعامل مع حالات الفشل
    autoclean_response = {
        "status": autoclean_status,
        "file_id": file_id,
        "ready_for_charts": autoclean_status == "success"
    }
    
    if autoclean_status == "success":
        autoclean_response.update({
            "raw_shape": [int(raw_shape[0]), int(raw_shape[1])] if raw_shape else None,
            "clean_shape": [int(clean_shape[0]), int(clean_shape[1])] if clean_shape else None,
            "rows_removed": int(raw_shape[0] - clean_shape[0]) if raw_shape and clean_shape else 0,
            "cleaned_path": cleaned_path
        })
    
    return jsonify({
        **backend_data,
        "autoclean": autoclean_response
    })

@app.route("/suggest", methods=["POST"])
def suggest():
    """AI chart suggestions using cleaned data"""
    data = request.json
    file_id = data.get("file_id") or data.get("uid")
    
    df = load_cleaned_df(file_id)
    if df is None:
        return jsonify({"error": "Cleaned data not found"}), 404
    
    suggestions = ai_suggest_charts(df)
    return jsonify({
        "suggestions": suggestions,
        "file_id": file_id,
        "source": "ai" if suggestions else "fallback"
    })

@app.route("/render", methods=["POST"])
def render_charts():
    """Render Plotly charts"""
    data = request.json
    file_id = data.get("file_id") or data.get("uid")
    charts = data.get("charts", [])
    
    df = load_cleaned_df(file_id)
    if df is None:
        return jsonify({"error": "No cleaned data"}), 404
    
    results = []
    for chart in charts:
        fig_json = build_chart(df, chart)
        results.append({
            "success": fig_json is not None,
            "fig": fig_json,
            "title": chart.get("title", "")
        })
    
    return jsonify({"charts": results, "file_id": file_id})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)