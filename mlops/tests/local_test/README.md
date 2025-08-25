# Container Test

```bash
cd data_science/train_container
```

```bash
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 058264126563.dkr.ecr.eu-central-1.amazonaws.com
```
```bash
docker build  -f Dockerfile -t xgboost-inference:1.0 . 
```

```bash
cd mlops/tests/unit_test
```

## Test of Prediction

```
docker run --rm --name 'xgb_model' \
-v "$PWD/model:/opt/ml/model" xgboost-inference:1.0 --mode=test \
--input_data="2022,4,10,48,2701,11,54,39,88.87,220,11.5078,0.01,1016.1,9,0.462188114,2,7.931330472,228,4,0,0,0,0,0,0,0,0,0,0,0"
```

## Test the API
```
docker run --rm --name 'xgb_model' -p 8080:8080 -v "$PWD/model:/opt/ml/model" xgboost-inference:1.0

cd ../tests/unit_test/ &&\
python server_test.py


curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: text/csv" \
  --data "2022,4,10,48,2701,11,54,39,88.87,220,11.5078,0.01,1016.1,9,0.462188114,2,7.931330472,228,4,0,0,0,0,0,0,0,0,0,0,0"

```