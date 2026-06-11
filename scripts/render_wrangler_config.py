import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "wrangler.toml.template"
OUTPUT = ROOT / "wrangler.toml"


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def toml_string(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def main():
    worker_name = os.environ.get("WORKER_NAME", "").strip() or "cloudflare-r2-webdav"
    bucket_name = required_env("R2_BUCKET_NAME")
    preview_bucket_name = os.environ.get("R2_PREVIEW_BUCKET_NAME", "").strip() or bucket_name
    webdav_username = os.environ.get("WEBDAV_USERNAME", "")
    webdav_password = os.environ.get("WEBDAV_PASSWORD", "")

    rendered = TEMPLATE.read_text(encoding="utf-8")
    rendered = rendered.replace("{{WORKER_NAME}}", toml_string(worker_name))
    rendered = rendered.replace("{{R2_BUCKET_NAME}}", toml_string(bucket_name))
    rendered = rendered.replace("{{R2_PREVIEW_BUCKET_NAME}}", toml_string(preview_bucket_name))
    rendered = rendered.replace("{{WEBDAV_USERNAME}}", toml_string(webdav_username))
    rendered = rendered.replace("{{WEBDAV_PASSWORD}}", toml_string(webdav_password))
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"Rendered {OUTPUT.name} with R2 bucket {bucket_name!r}")


if __name__ == "__main__":
    main()
