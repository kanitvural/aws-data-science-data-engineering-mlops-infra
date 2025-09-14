# Container Test

```bash
cd mlops/inference_container
```

```bash
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 058264126563.dkr.ecr.eu-central-1.amazonaws.com
```
```bash
docker build  -f Dockerfile -t xgboost-inference:1.0 . 
```

```bash
cd mlops/tests/local_test
```

## Test of Prediction

```
docker run --rm --name 'xgb_model' \
-v "$PWD/model:/opt/ml/model" xgboost-inference:1.0 --mode=test \
--input_data="2022,6,29,-13.0,399,12,36,54.0,92.92,200.0,8.05546,0.0001,1021.4,10.0,0.06324238003505211,0,272,0,0,0,0,0,0,0,1,0,0,0"
```

## Test the API
```
docker run --rm --name 'xgb_model' -p 8080:8080 -v "$PWD/model:/opt/ml/model" xgboost-inference:1.0

cd ../tests/local_test/ &&\
python server_test.py


curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: text/csv" \
  --data "2022,6,29,-13.0,399,12,36,54.0,92.92,200.0,8.05546,0.0001,1021.4,10.0,0.06324238003505211,0,272,0,0,0,0,0,0,0,1,0,0,0"

```