"""The sandbox image reference. The image is pinned by the full local image ID recorded in
config.json (``sandbox.image_id``, ``sha256:<64 hex>``), not by its tag: this Docker daemon has
answered ``docker image inspect <tag>`` with "No such image" while the tag was listed, whereas
lookup by ID kept working. The same ID is used by the compose file (sample sandbox), by the
trusted LibreOffice conversion path, and by the launcher pre-flight. A local image ID is not a
portable reference; the registry digest for cross-machine use is recorded at freeze."""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config.json")
COMPOSE = os.path.join(ROOT, "harness", "compose.yaml")
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ImageRefError(RuntimeError):
    pass


def sandbox_image_ref(config_path: str = CONFIG) -> str:
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    image_id = cfg.get("sandbox", {}).get("image_id")
    if not isinstance(image_id, str) or not IMAGE_ID_RE.match(image_id):
        raise ImageRefError("config.json sandbox.image_id must be a full local image ID of the form sha256:<64 hex>")
    return image_id


def compose_image(compose_path: str = COMPOSE, service: str = "default") -> str:
    """The image reference of the sandbox service, read from the parsed YAML structure (quoted or
    unquoted scalars alike), never from a regular expression over the text."""
    import yaml
    with open(compose_path, encoding="utf-8") as f:
        try:
            doc = yaml.safe_load(f)
        except yaml.YAMLError as ex:
            raise ImageRefError(f"compose file {compose_path} is not valid YAML: {type(ex).__name__}") from ex
    services = doc.get("services") if isinstance(doc, dict) else None
    svc = services.get(service) if isinstance(services, dict) else None
    image = svc.get("image") if isinstance(svc, dict) else None
    if not isinstance(image, str) or not image.strip():
        raise ImageRefError(f"no string 'image' under services.{service} in {compose_path}")
    return image.strip()


def expected_platform(config_path: str = CONFIG) -> dict:
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    p = cfg.get("sandbox", {}).get("platform") or {}
    return {"os": p.get("os"), "architecture": p.get("architecture")}
