import os, sys
python_path = os.path.join(os.path.dirname(__file__), "../../resources/python")
sys.path.append(os.path.join(python_path, "common"))

distributions_path = os.path.join(python_path, "distributions")
if sys.platform.startswith("darwin"):
    sys.path.append(os.path.join(distributions_path, "mac"))
elif os.name == "nt":
    sys.path.append(os.path.join(distributions_path, "windows"))
elif os.name == "posix":
    sys.path.append(os.path.join(distributions_path, "linux"))

from server import Server
from process_manager import ProcessManager
