import os, sys
os.environ['TOPOLOGY_CONFIG'] = '/etc/opt/topology/config-production-webhook.py'
sys.path.insert(0, '/opt/topology-webhook/src')
from webhook_app import app as application
