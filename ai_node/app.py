import os
import re
import json
import logging
import warnings
import base64
import pandas as pd
import numpy as np
from flask import Flask, jsonify, request
import requests
import plotly.express as px
import plotly.io as pio

# =============================
# 1. إعدادات السيرفر والـ Logging
# =============================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

app = Flask(__name__)
app.secret_key = "csv-insight-ai-local-final-v2"

# تأكد من أن هذا المسار يطابق المجلد في جهازك
UPLOAD_FOLDER = r"E:\graduationn-main\graduationn-main\uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
MAX_SUGGESTIONS = 6

# =============================
# 2. الأدوات التقنية (المحرك الاحترافي)
# =============================

def fix_bdata(obj):
    """
    تحويل أي بيانات NumPy أو Binary ناتجة من Plotly إلى قوائم عادية (Lists)
    لضمان عدم حدوث خطأ أثناء تحويل الـ Response إلى JSON في الـ Node.js
    """
    if isinstance(obj, dict):
        if "bdata" in obj and "dtype" in obj:
            try:
                dtype = np.dtype(obj["dtype"])
                arr = np.frombuffer(base64.b64decode(obj["bdata"]), dtype=dtype)
                return arr.tolist()
            except: return obj
        return {k: fix_bdata(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [fix_bdata(i) for i in obj]
    return obj

def detect_column_type(series):
    if pd.api.types.is_datetime64_any_dtype(series): return "date"
    if pd.api.types.is_numeric_dtype(series): return "numeric"
    return "text"

def load_cleaned_df(file_id):
    file_name = f"{file_id}_autoclean.csv"
    path = os.path.join(UPLOAD_FOLDER, file_name)
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

# =============================
# 3. منطق الذكاء الاصطناعي (Ollama)
# =============================

def ask_ai(prompt):
    try:
        r = requests.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=35)
        return r.json().get("response", "")
    except Exception as e:
        logger.error(f"Ollama Connection Error: {e}")
        return ""

def ai_suggest_charts(df):
    col_profiles = {}
    for col in df.columns:
        dtype = detect_column_type(df[col])
        profile = {"type": dtype}
        if dtype == "numeric":
            profile.update({"min": float(df[col].min()), "max": float(df[col].max())})
        else:
            profile["unique_count"] = int(df[col].nunique())
        col_profiles[col] = profile

    prompt = f"""You are a data analyst expert. Data Profile: {json.dumps(col_profiles)}
    Suggest exactly {MAX_SUGGESTIONS} chart configurations. 
    Return ONLY a JSON array. No text before or after.
    JSON Format: [{{"type": "bar|line|scatter|pie|histogram", "x": "col1", "y": "col2", "title": "title"}}]
    Rules:
    - If type is bar/pie and column has many unique values, the renderer will handle Top 15.
    - If y is unique_count, it means count of x categories.
    """
    
    raw = ask_ai(prompt)
    try:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            suggestions = json.loads(match.group())
            for s in suggestions:
                if s.get("type") == "hist": s["type"] = "histogram"
                if not s.get("title"): s["title"] = f"Distribution of {s.get('x')}"
            return suggestions
    except Exception as e:
        logger.error(f"JSON Parsing Error: {e}")
    return []

# =============================
# 4. محرك بناء الرسومات (الرسم الفعلي المعدل)
# =============================

def build_chart(df, chart_spec):
    try:
        ctype = chart_spec.get("type") or chart_spec.get("chartType")
        x = chart_spec.get("x")
        y = chart_spec.get("y")
        
        if isinstance(x, dict): x = x.get("column")
        if isinstance(y, dict): y = y.get("column")
        
        title = chart_spec.get("title", "Data Visualization")
        fig = None

        if not x or x not in df.columns: return None

        # نسخة مؤقتة للمعالجة الرقمية لتجنب خطأ nlargest مع الـ object dtype
        temp_df = df.copy()

        # --- رسم الـ Bar Chart ---
        if ctype == "bar":
            if y == "unique_count" or not y or y not in df.columns:
                plot_df = temp_df[x].value_counts().nlargest(15).reset_index()
                plot_df.columns = [x, 'count']
                fig = px.bar(plot_df, x=x, y='count', title=title)
            else:
                # تحويل العمود لرقمي قبل الحساب لضمان عدم حدوث Error
                temp_df[y] = pd.to_numeric(temp_df[y], errors='coerce')
                plot_df = temp_df.groupby(x)[y].sum().nlargest(15).reset_index()
                fig = px.bar(plot_df, x=x, y=y, title=title)

        # --- رسم الـ Scatter ---
        elif ctype == "scatter":
            if y and y in df.columns:
                temp_df[y] = pd.to_numeric(temp_df[y], errors='coerce')
                fig = px.scatter(temp_df.head(500), x=x, y=y, title=title)

        # --- رسم الـ Pie ---
        elif ctype == "pie":
            plot_df = temp_df[x].value_counts().nlargest(10).reset_index()
            fig = px.pie(plot_df, names=x, values=plot_df.columns[1], title=title)

        # --- رسم الـ Histogram ---
        elif ctype in ["histogram", "hist"]:
            fig = px.histogram(temp_df, x=x, title=title)

        # --- رسم الـ Line Chart ---
        elif ctype == "line":
            if y and y in df.columns:
                temp_df[y] = pd.to_numeric(temp_df[y], errors='coerce')
                plot_df = temp_df.sort_values(x).head(100)
                fig = px.line(plot_df, x=x, y=y, title=title)

        if fig:
            return fix_bdata(json.loads(pio.to_json(fig)))
        return None
    except Exception as e:
        logger.error(f"Plotly Rendering Error: {e}")
        return None

# =============================
# 5. الـ API Routes
# =============================

@app.route("/upload", methods=["POST"])
def upload():
    try:
        data = request.get_json()
        csv_info = data.get("CSV", {})
        file_id = csv_info.get("_id")
        filename = csv_info.get("fileName")
        
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            user_id = csv_info.get("userId", "")
            file_path = os.path.join(UPLOAD_FOLDER, str(user_id), filename)

        if not os.path.exists(file_path):
            return jsonify({"error": "File not found at path"}), 404

        try:
            df = pd.read_csv(file_path, sep=None, engine='python', encoding='utf-8-sig')
        except:
            df = pd.read_csv(file_path, sep=None, engine='python', encoding='cp1252')

        df_clean = df.drop_duplicates().fillna("N/A")
        cleaned_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_autoclean.csv")
        df_clean.to_csv(cleaned_path, index=False)
        
        return jsonify({
            **data,
            "autoclean": {
                "status": "success",
                "file_id": file_id,
                "shape": list(df_clean.shape)
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/suggest", methods=["POST"])
def suggest():
    data = request.json
    file_id = data.get("file_id")
    df = load_cleaned_df(file_id)
    if df is None: return jsonify({"error": "Data not found"}), 404
    
    suggestions = ai_suggest_charts(df)
    return jsonify({"suggestions": suggestions, "file_id": file_id})

@app.route("/render", methods=["POST"])
def render_charts():
    data = request.json
    file_id = data.get("file_id")
    charts_to_render = data.get("charts", [])
    
    df = load_cleaned_df(file_id)
    if df is None: return jsonify({"error": "Cleaned data not found"}), 404
    
    results = []
    for chart in charts_to_render:
        fig_json = build_chart(df, chart)
        if fig_json:
            results.append({
                "success": True, 
                "fig": fig_json, 
                "title": chart.get("title", "Chart")
            })
            
    return jsonify({"charts": results, "file_id": file_id})

if __name__ == "__main__":
    logger.info("Python AI Service is running on http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=True)