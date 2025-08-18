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
--input_data="2022,2,10,-1.0,-16.0,1426,6,20,44.0,85.06,0.0,0.0,0.0,1033.0,10.0,0.1993620148040375,2,-12.707865168539326,610,2,0,0,1,0,0,0,0,0,0,0,0"
```

## Test the API
```
docker run --rm --name 'xgb_model' -p 8080:8080 -v "$PWD/model:/opt/ml/model" xgboost-inference:1.0

cd ../tests/unit_test/ &&\
python server_test.py


curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: text/csv" \
  --data "2022,3,30,-4,696,15,22,46,79.13,220,5.7539,0,1021.7,10,0.063272379,1,-4.59375,272,1,0,0,0,0,0,0,0,1,0,0,0"

```