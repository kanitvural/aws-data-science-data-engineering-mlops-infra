import os
import io
import signal
import subprocess
import argparse
import sys
import logging

# Basit logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/ml_pipeline.log') if os.path.exists('/tmp') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_parser():
    parser = argparse.ArgumentParser(description="Inference server")
    
    parser.add_argument("--mode", choices=["serve","test"], default="serve",
                        help="Mode to run the script in: train, test, or serve")
    parser.add_argument("--timeout", type=int, default=os.environ.get('MODEL_SERVER_TIMEOUT', 60),
                        help="Timeout for the server in seconds")
    parser.add_argument("--workers", type=int, default=os.environ.get('MODEL_SERVER_WORKERS', os.cpu_count() or 1),
                        help="Number of workers for the server")
    parser.add_argument("--input_data", type=str, help="Input data for testing in string format, e.g. '0.1, 0.2, ...'")
    return parser.parse_known_args()
    

def sigterm_handler(nginx_pid, gunicorn_pid):
    logger.info("Shutting down gracefully...")
    try:
        os.kill(nginx_pid, signal.SIGQUIT)
    except OSError:
        pass
    try:
        os.kill(gunicorn_pid, signal.SIGTERM)
    except OSError:
        pass
    sys.exit(0)

def start_server(timeout, workers):
    logger.info(f"🚀 Starting inference server with {workers} workers and timeout {timeout}s")

    subprocess.check_call(['ln', '-sf', '/dev/stdout', '/var/log/nginx/access.log'])
    subprocess.check_call(['ln', '-sf', '/dev/stderr', '/var/log/nginx/error.log'])

    nginx = subprocess.Popen(['nginx', '-c', '/opt/ml/code/nginx.conf'])
    gunicorn = subprocess.Popen([
        'gunicorn',
        '-k', 'uvicorn.workers.UvicornWorker',
        '-w', str(workers),
        '-b', 'unix:/tmp/gunicorn.sock',
        'wsgi:app',
        '--timeout', str(timeout)
    ])

    signal.signal(signal.SIGTERM, lambda a, b: sigterm_handler(nginx.pid, gunicorn.pid))

    pids = {nginx.pid, gunicorn.pid}
    while True:
        pid, _ = os.wait()
        if pid in pids:
            break

    sigterm_handler(nginx.pid, gunicorn.pid)
    logger.info("🛑 Inference server exiting")

def run_test(input_data):
    """Test the inference endpoint"""
    try:
        import inference
        import pandas as pd
        
        model = inference.load_xgb_model()
        if model is None:
            logger.error("❌ Model not loaded")
            sys.exit(1)
        
        cols = [
            'year','month','day','arr_delay','distance','hour','minute','temp','humid',
            'wind_dir','wind_speed','precip','pressure','visib','distance_ratio_by_total',
            'distance_category','aircraft_count_by_airline','allegiant_air','american_airlines_inc',
            'delta_air_lines_inc','frontier_airlines_inc','hawaiian_airlines_inc','horizon_air','jetblue_airways',
            'skywest_airlines_inc','southwest_airlines_co','spirit_air_lines','united_air_lines_inc'
        ]
    
        df = pd.read_csv(io.StringIO(input_data), header=None)
        df.columns = cols
        dmatrix = inference.xgb.DMatrix(df)
        prediction = model.predict(dmatrix)
        logger.info(f"✅ Prediction result: {prediction[0]:.2f}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    args, _ = get_parser()
    
    if args.mode == "serve":
        start_server(args.timeout, args.workers)
    elif args.mode == "test":
        if not args.input_data:
            logger.error("❌ Test mode requires --input-data argument")
            sys.exit(1)
        run_test(args.input_data)
    else:
        raise Exception(f"Unknown mode: {args.mode}. Use 'serve' or 'test'.")