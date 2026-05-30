# tests/conftest.py
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "kinneret_app"))
sys.path.insert(0, str(ROOT / "Automation"))

# Register 08_train_forecast_model.py as _08_train_forecast_model (digit prefix workaround)
_spec = importlib.util.spec_from_file_location(
    "_08_train_forecast_model",
    ROOT / "Automation" / "08_train_forecast_model.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["_08_train_forecast_model"] = _mod
_spec.loader.exec_module(_mod)
