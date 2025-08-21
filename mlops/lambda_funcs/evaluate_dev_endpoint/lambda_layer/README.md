cd lambda_layer
pyenv install 3.9.18
pyenv local 3.9.18 
python --version
mkdir -p python/lib/python3.9/site-packages
pip install numpy pandas -t python/lib/python3.9/site-packages/
zip -r lambda_layer.zip python

rm -rf python
rm .python-version

pyenv global 3.11.11
python --version
source .venv/bin/activate

