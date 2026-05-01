import json
import logging
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests as http_lib
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ai_client
from ai_client import PROVIDERS
from models import TestCase
from openapi_importer import load_spec
from postman_importer import load_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="API TestGen AI")

SETTINGS_FILE = "settings.json"
STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _load_settings() -> dict:
    p = Path(SETTINGS_FILE)
    return json.loads(p.read_text()) if p.exists() else {}


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@app.get("/api/providers")
def get_providers():
    return {
        key: {
            "label": cfg["label"],
            "models": [
                {"id": v[0], "label": v[1]}
                for v in cfg["models"].values()
                if v[0] != "__custom__"
            ],
            "default_model": cfg["default_model"],
            "needs_key": bool(cfg["env_key"]),
        }
        for key, cfg in PROVIDERS.items()
    }


@app.get("/api/settings")
def get_settings():
    return _load_settings()


# ---------------------------------------------------------------------------
# Parse — fast, no AI, just read the file
# ---------------------------------------------------------------------------

@app.post("/api/parse/postman")
async def parse_postman(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        reqs = load_collection(tmp_path)
        return {"endpoints": [
            {"method": r.method, "path": r.path, "payload": r.payload, "name": r.name}
            for r in reqs
        ]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/api/parse/openapi")
async def parse_openapi_spec(file: UploadFile = File(...)):
    suffix = ".yaml" if file.filename.endswith((".yaml", ".yml")) else ".json"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        base_url, reqs = load_spec(tmp_path)
        return {
            "base_url": base_url,
            "endpoints": [
                {"method": r.method, "path": r.path, "payload": r.payload,
                 "name": r.name, "description": r.description}
                for r in reqs
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

class GenerateURLRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    url: str
    method: str = "GET"
    payload: Optional[str] = None
    description: Optional[str] = None
    count: Optional[int] = None


@app.post("/api/generate/url")
def generate_url(req: GenerateURLRequest):
    from urllib.parse import urlparse
    parsed = urlparse(req.url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    try:
        ai_client.setup(req.provider, req.model, req.api_key)
        cases = ai_client.generate_test_cases(
            req.method.upper(), path, req.payload, req.description, req.count
        )
        return {"base_url": base_url, "test_cases": [tc.model_dump() for tc in cases]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

class SaveRequest(BaseModel):
    test_cases: list[dict]
    filename: str = "test_cases.json"


@app.post("/api/save")
def save_cases(req: SaveRequest):
    path = Path(req.filename)
    path.write_text(json.dumps(req.test_cases, indent=2))
    return {"path": str(path.resolve())}


# ---------------------------------------------------------------------------
# Run — HTTP mode (built-in)
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    test_cases: list[dict]
    base_url: str
    bearer: Optional[str] = None


@app.post("/api/run")
def run_http(req: RunRequest):
    cases = [TestCase.model_validate(tc) for tc in req.test_cases]
    global_headers = {}
    if req.bearer:
        global_headers["Authorization"] = f"Bearer {req.bearer}"

    results = []
    for tc in cases:
        url = req.base_url.rstrip("/") + tc.input.endpoint
        headers = {**global_headers, **tc.input.headers}
        start = time.time()
        try:
            resp = http_lib.request(
                method=tc.input.method, url=url,
                json=tc.input.payload, headers=headers, timeout=30,
            )
            elapsed_ms = int((time.time() - start) * 1000)
            failures = _check(tc, resp, elapsed_ms)
            results.append({
                "name": tc.name, "category": tc.category, "description": tc.description,
                "passed": not failures, "status_code": resp.status_code,
                "expected_status_code": tc.expected_result.status_code,
                "elapsed_ms": elapsed_ms, "failures": failures,
            })
        except Exception as e:
            results.append({
                "name": tc.name, "category": tc.category, "description": tc.description,
                "passed": False, "status_code": None,
                "expected_status_code": tc.expected_result.status_code,
                "elapsed_ms": None, "failures": [str(e)],
            })

    passed = sum(1 for r in results if r["passed"])
    return {"results": results, "passed": passed, "failed": len(results) - passed, "total": len(results)}


def _check(tc: TestCase, resp, elapsed_ms: int) -> list[str]:
    er = tc.expected_result
    failures = []
    if resp.status_code != er.status_code:
        failures.append(f"Status: expected {er.status_code}, got {resp.status_code}")
    if er.max_response_time_ms and elapsed_ms > er.max_response_time_ms:
        failures.append(f"Too slow: {elapsed_ms}ms > {er.max_response_time_ms}ms")
    if er.contains_key or er.contains_value:
        try:
            body = resp.json()
            if er.contains_key and er.contains_key not in body:
                failures.append(f"Missing key '{er.contains_key}'")
            if er.contains_value:
                for k, v in er.contains_value.items():
                    if body.get(k) != v:
                        failures.append(f"{k}: expected {v!r}, got {body.get(k)!r}")
        except Exception:
            failures.append("Response body is not valid JSON")
    if er.response_headers:
        for k, v in er.response_headers.items():
            actual = resp.headers.get(k, "")
            if v.lower() not in actual.lower():
                failures.append(f"Header {k}: expected '{v}', got '{actual}'")
    return failures


# ---------------------------------------------------------------------------
# Run — tester.py mode
# ---------------------------------------------------------------------------

class TesterRunRequest(BaseModel):
    test_cases: list[dict]
    base_url: str
    bearer: Optional[str] = None
    generate_report: bool = False


@app.post("/api/run/tester")
def run_tester(req: TesterRunRequest):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        json.dump(req.test_cases, tmp, indent=2)
        tmp_path = tmp.name

    report_path = str(STATIC_DIR / "report.html") if req.generate_report else None
    try:
        cmd = ["venv/bin/python3", "tester.py", tmp_path, req.base_url]
        if req.bearer:
            cmd += ["--bearer", req.bearer]
        if report_path:
            cmd += ["--html", report_path]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output = _strip_ansi(result.stdout)
        if result.stderr:
            output += f"\n[stderr]\n{_strip_ansi(result.stderr)}"

        return {
            "output": output,
            "exit_code": result.returncode,
            "report_url": "/static/report.html" if (report_path and Path(report_path).exists()) else None,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Tester timed out after 180s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Run — pytest mode
# ---------------------------------------------------------------------------

class PytestRunRequest(BaseModel):
    test_cases: list[dict]
    base_url: str
    bearer: Optional[str] = None
    generate_xml: bool = False
    generate_html: bool = False


@app.post("/api/run/pytest")
def run_pytest(req: PytestRunRequest):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        json.dump(req.test_cases, tmp, indent=2)
        tmp_path = tmp.name

    xml_path = str(STATIC_DIR / "results.xml") if req.generate_xml else None
    html_path = str(STATIC_DIR / "pytest-report.html") if req.generate_html else None
    try:
        cmd = [
            "venv/bin/python3", "-m", "pytest", "tests/test_api.py",
            f"--test-file={tmp_path}",
            f"--base-url={req.base_url}",
            "-v", "--tb=short", "--no-header",
        ]
        if req.bearer:
            cmd += [f"--bearer={req.bearer}"]
        if xml_path:
            cmd += [f"--junit-xml={xml_path}"]
        if html_path:
            cmd += [f"--html={html_path}", "--self-contained-html"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output = _strip_ansi(result.stdout)
        if result.stderr:
            output += f"\n[stderr]\n{_strip_ansi(result.stderr)}"

        return {
            "output": output,
            "exit_code": result.returncode,
            "xml_url": "/static/results.xml" if (xml_path and Path(xml_path).exists()) else None,
            "report_url": "/static/pytest-report.html" if (html_path and Path(html_path).exists()) else None,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="pytest timed out after 180s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
