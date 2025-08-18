import os
import io
import logging
import tarfile
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

# Basit logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
MODEL_TAR_PATH = os.path.join(MODEL_DIR, "model.tar.gz")
MODEL_PATH = os.path.join(MODEL_DIR, "xgboost-model.json")

model = None

def load_xgb_model():
    global model
    if model is None:
        if os.path.exists(MODEL_TAR_PATH) and not os.path.exists(MODEL_PATH):
            with tarfile.open(MODEL_TAR_PATH, "r:gz") as tar:
                tar.extractall(path=MODEL_DIR)
            logger.info("Model extracted")

        if os.path.exists(MODEL_PATH):
            model = xgb.Booster()
            model.load_model(MODEL_PATH)
            logger.info("Model loaded")
        else:
            logger.error(f"Model file not found: {MODEL_PATH}")
            return None
    return model

app = FastAPI()

@app.get("/ping")
async def ping():
    """Health check"""
    current_model = load_xgb_model()
    is_ready = current_model is not None
    return Response(status_code=200 if is_ready else 404)

@app.post("/invocations", response_class=PlainTextResponse)
async def invocations(request: Request):
    """SageMaker inference endpoint"""
    current_model = load_xgb_model()
    if current_model is None:
        return Response(
            content="Model not loaded. Please ensure model file exists.",
            status_code=503
        )
    
    if request.headers.get("content-type") != "text/csv":
        return Response(
            content="Invalid content type. Only 'text/csv' is supported.",
            status_code=415
        )
    
    body = await request.body()
    if not body:
        return Response(content="Empty request", status_code=400)

    try:
        
        cols = ['year','month','day','arr_delay','distance','hour','minute','temp','humid',
        'wind_dir','wind_speed','precip','pressure','visib','distance_ratio_by_total',
        'distance_category','airline_daily_performance_kpi','aircraft_count_by_airline',
        'dep_delay_category','Allegiant Air','American Airlines Inc.','Delta Air Lines Inc.',
        'Frontier Airlines Inc.','Hawaiian Airlines Inc.','Horizon Air','JetBlue Airways',
        'SkyWest Airlines Inc.','Southwest Airlines Co.','Spirit Air Lines','United Air Lines Inc.']

        df = pd.read_csv(io.StringIO(body.decode("utf-8")), header=None)
        df.columns = cols
        dmatrix = xgb.DMatrix(df)
        predictions = current_model.predict(dmatrix)
        formatted_preds = [f"{x:.2f}" for x in predictions]
        csv_buffer = io.StringIO()
        pd.DataFrame({"predictions": formatted_preds}).to_csv(csv_buffer, header=False, index=False)
        return csv_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return Response(content=f"Error: {str(e)}", status_code=500)