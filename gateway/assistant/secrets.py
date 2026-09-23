import os
import subprocess


SERVICE = "local-assistant-gateway"


def get_secret(name: str) -> str | None:
    """Read a key from the Mac login Keychain; env is reserved for CI fixtures."""
    if os.environ.get("LOCAL_ASSISTANT_TEST_MODE") == "1":
        return os.environ.get(f"LOCAL_ASSISTANT_{name.upper()}")
    result = subprocess.run(
        ["security", "find-generic-password", "-s", SERVICE, "-a", name, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def set_secret(name: str, value: str) -> None:
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", SERVICE, "-a", name, "-w", value],
        check=True,
        capture_output=True,
    )
