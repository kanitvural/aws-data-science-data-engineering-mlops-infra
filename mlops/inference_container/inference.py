import os
import io
import logging
import tarfile
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, Request, Response

# Basit logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

model_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
model_tar_path = os.path.join(model_dir, "model.tar.gz")
model_path = os.path.join(model_dir, "xgboost-model.json")

model = None

def load_xgb_model():
    global model
    if model is None:
        if os.path.exists(model_tar_path) and not os.path.exists(model_path):
            with tarfile.open(model_tar_path, "r:gz") as tar:
                tar.extractall(path=model_dir)
            logger.info("Model extracted")

        if os.path.exists(model_path):
            model = xgb.Booster()
            model.load_model(model_path)
            logger.info("Model loaded")
        else:
            logger.error(f"Model file not found: {model_path}")
            return None
    return model

app = FastAPI()

@app.get("/ping")
async def ping():
    """Health check"""
    current_model = load_xgb_model()
    is_ready = current_model is not None
    return Response(status_code=200 if is_ready else 404)

@app.post("/invocations")
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
        
        cols = [
            'year','month','day','arr_delay','distance','hour','minute','temp','humid',
            'wind_dir','wind_speed','precip','pressure','visib','distance_ratio_by_total',
            'distance_category','aircraft_count_by_airline','allegiant_air','american_airlines_inc',
            'delta_air_lines_inc','frontier_airlines_inc','hawaiian_airlines_inc','horizon_air','jetblue_airways',
            'skywest_airlines_inc','southwest_airlines_co','spirit_air_lines','united_air_lines_inc'
        ]
        
        
        df = pd.read_csv(io.StringIO(body.decode("utf-8")), header=None)
        df.columns = cols
        
        
        dmatrix = xgb.DMatrix(df)
        predictions = current_model.predict(dmatrix)
        formatted_preds = [f"{x:.2f}" for x in predictions]
        
        
        csv_buffer = io.StringIO()
        pd.DataFrame({"predictions": formatted_preds}).to_csv(csv_buffer, header=False, index=False)
        
        
        return Response(
            content=csv_buffer.getvalue(),
            media_type="text/csv"
        )
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return Response(content=f"Error: {str(e)}", status_code=500)
