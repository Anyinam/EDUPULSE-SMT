import json
import os
import re
import sys
from pathlib import Path


def _prune_empty_secrets(task_definition):
    for container in task_definition.get("containerDefinitions", []):
        secrets = container.get("secrets")
        if not isinstance(secrets, list):
            continue
        container["secrets"] = [
            entry
            for entry in secrets
            if str(entry.get("valueFrom") or "").strip()
        ]


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: render_task_definition.py <template> <output>")

    template_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    template = template_path.read_text(encoding="utf-8")
    rendered = os.path.expandvars(template)

    unresolved = re.findall(r"\$\{([A-Za-z0-9_]+)\}", rendered)
    if unresolved:
        raise SystemExit(
            f"Unresolved environment variable(s) in {template_path}: {', '.join(sorted(set(unresolved)))}"
        )

    task_definition = json.loads(rendered)
    _prune_empty_secrets(task_definition)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{json.dumps(task_definition, indent=2)}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())