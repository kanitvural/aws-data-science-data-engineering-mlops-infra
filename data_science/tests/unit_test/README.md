# Container Test

```bash
cd data_science/train_container
```

```bash
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 058264126563.dkr.ecr.eu-central-1.amazonaws.com
```
```bash
docker build  -f Dockerfile -t xgboost:1.0 . 
```

```bash
cd data_science/tests/unit_test
```

```bash
 docker run --rm --name 'my_model' \                                                                                                            
    -v "$PWD/model:/opt/ml/model" \
    -v "$PWD/output:/opt/ml/output" \
    -v "$PWD/input:/opt/ml/input" xgboost:1.0
```





