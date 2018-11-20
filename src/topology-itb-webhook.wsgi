import os, sys
os.environ['TOPOLOGY_CONFIG'] = '/etc/opt/topology/config-itb-webhook.py'
sys.path.insert(0, '/opt/topology-itb-webhook/src')
from app import app as application
