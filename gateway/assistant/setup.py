"""Set secrets without placing them in shell history or project files."""

import argparse
import getpass
import secrets

from .secrets import set_secret


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the local assistant Mac Keychain")
    parser.add_argument("name", choices=["amap", "openai", "deepseek", "anthropic", "glm", "kimi", "device_token"])
    args = parser.parse_args()
    value = secrets.token_urlsafe(32) if args.name == "device_token" else getpass.getpass(f"{args.name} API Key: ")
    if not value:
        parser.error("Empty secret")
    set_secret(args.name, value)
    if args.name == "device_token":
        print(f"Save this device token in iPhone Keychain: {value}")
    else:
        print(f"Saved {args.name} to Mac Keychain")


if __name__ == "__main__":
    main()
