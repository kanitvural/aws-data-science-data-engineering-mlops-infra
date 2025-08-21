cd lambda_layer
mkdir -p python/lib/python3.9/site-packages 
pip install numpy pandas -t python/lib/python3.9/site-packages
zip -r lambda_layer.zip python   