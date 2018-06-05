import os, sys
os.environ['TOPOLOGY_CONFIG'] = '/etc/opt/topology/config-production.py'
sys.path.insert(0, '/opt/topology/src')
from app import app as application
