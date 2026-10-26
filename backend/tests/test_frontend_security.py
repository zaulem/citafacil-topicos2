"""H-23: el panel admin no debe ejecutar código escrito por un visitante.

El nombre y el teléfono del cliente los escribe cualquiera al reservar, y el panel
los inserta en la tabla con innerHTML. Estos tests verifican que pasen por esc().
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ADMIN_HTML = Path(__file__).resolve().parents[2] / "frontend" / "admin.html"
MALICIOUS = "<img src=x onerror=alert('XSS')>"


def _admin_source() -> str:
    return ADMIN_HTML.read_text(encoding="utf-8")


def test_admin_escapes_customer_fields():
    src = _admin_source()
    for field in ("a.customer_name", "a.customer_phone"):
        assert f"${{esc({field})}}" in src, f"{field} debe mostrarse con esc()"
        assert f"${{{field}}}" not in src, f"{field} se inserta sin escapar"


@pytest.mark.skipif(shutil.which("node") is None, reason="requiere Node.js")
def test_esc_neutralizes_html_payload():
    match = re.search(r"const esc = .*?;\n", _admin_source())
    assert match, "no se encontró la función esc() en admin.html"
    script = match.group(0) + f"process.stdout.write(esc({json.dumps(MALICIOUS)}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert "<" not in out and ">" not in out
    assert out == "&lt;img src=x onerror=alert(&#39;XSS&#39;)&gt;"
