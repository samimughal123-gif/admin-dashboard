"""
WSGI configuration file for PythonAnywhere deployment
"""

import sys
import os

# Add the application directory to the Python path
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

# Import the Flask application
from simple_app import app as application

# This is the WSGI entry point
if __name__ == '__main__':
    application.run()
