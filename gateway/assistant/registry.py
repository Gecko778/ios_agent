import json
from pathlib import Path


CONNECTOR_ROOT = Path(__file__).resolve().parents[1] / "connectors"


def list_connectors() -> dict[str, dict]:
    """Load reviewed connector metadata; action execution remains adapter-owned."""
    result = {}
    for path in CONNECTOR_ROOT.glob("*/manifest.json"):
        manifest = json.loads(path.read_text())
        actions = {}
        for action_path in (path.parent / "actions").glob("*.json"):
            action = json.loads(action_path.read_text())
            actions[action["name"]] = {
                "risk": action["risk"],
                "executor": action["executor"],
                "input_schema": action["input_schema"],
            }
        declared = set(manifest["actions"])
        if declared != set(actions):
            raise ValueError(f"Connector {manifest['id']} has missing or undeclared actions")
        result[manifest["id"]] = {
            "version": manifest["version"],
            "region": manifest["region"],
            "actions": actions,
        }
    return result
