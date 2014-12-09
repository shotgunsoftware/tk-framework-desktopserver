import os, sys
python_path = os.path.join(os.path.dirname(__file__), "../../resources/python")
sys.path.append(os.path.join(python_path, "common"))

if sys.platform.startswith("darwin"):
    sys.path.append(os.path.join(python_path, "mac"))
elif os.name == "nt":
    sys.path.append(os.path.join(python_path, "windows"))
elif os.name == "posix":
    sys.path.append(os.path.join(python_path, "linux"))

from server import Server
from process_manager import ProcessManager
