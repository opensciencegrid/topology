import os, sys
os.environ['TOPOLOGY_CONFIG'] = '/etc/opt/topology/config-itb.py'
sys.path.insert(0, '/opt/topology-itb/src')
from app import app as application
