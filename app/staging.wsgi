#!/usr/bin/env python
DEPLOYMENT_TARGET = 'staging'
import sys, os, os.path, site
import logging, logging.config
sys.stdout = sys.stderr # protect against spurious printing...

try:
    logging.config.fileConfig(os.path.join(os.path.dirname(__file__),'../%s/logging.txt' % DEPLOYMENT_TARGET))
except Exception, e:
    print e

# Reordering the path code from http://code.google.com/p/modwsgi/wiki/VirtualEnvironments

# Remember original sys.path.
prev_sys_path = list(sys.path) 

site.addsitedir(os.path.abspath(os.path.dirname(__file__)))

site.addsitedir(os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../env")),
    "lib/python2.6/site-packages"
))

# Reorder sys.path so new directories at the front.
new_sys_path = [] 
for item in list(sys.path): 
    if item not in prev_sys_path: 
        new_sys_path.append(item) 
        sys.path.remove(item) 
sys.path[:0] = new_sys_path 

from app import app as application
from config import get_settings
application.config['SETTINGS'] = get_settings(DEPLOYMENT_TARGET)
