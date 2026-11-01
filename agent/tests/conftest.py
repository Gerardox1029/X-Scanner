import os
import tempfile

_root = tempfile.mkdtemp(prefix="xscanner-pytest-")
os.environ["XDG_CONFIG_HOME"] = _root + "/config"
os.environ["XDG_DATA_HOME"] = _root + "/data"
os.environ["XDG_CACHE_HOME"] = _root + "/cache"
os.environ["XSCANNER_ORIGIN"] = "https://test.example"
