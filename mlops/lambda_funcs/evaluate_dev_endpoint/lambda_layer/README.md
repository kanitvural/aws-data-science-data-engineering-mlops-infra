cd lambda_layer
deactivate
pyenv install 3.12.6
pyenv local 3.12.6 
python --version
mkdir -p python/lib/python3.12/site-packages
sudo apt update
sudo apt install python3-pip -y
/usr/bin/python3 -m pip install --no-cache-dir pandas -t python/lib/python3.12/site-packages/

zip -r lambda_layer.zip python

rm -rf python
rm .python-version

pyenv global 3.11.11
python --version
source .venv/bin/activate
