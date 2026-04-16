"""
Comprehensive test suite for FlowBridge v3.0.
Run from the backend directory: python comprehensive_test.py
"""
import os
import sys
import json
import time
import uuid
import requests

BASE_URL = os.environ.get('TEST_BASE_URL', 'http://localhost:5000')
TOKEN = None
TEST_USER = {"username": "testuser_auto", "email": "testuser_auto@example.com", "password": "Test1234!"}
RESULTS = []


def log(name, passed, duration_ms, note=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"test": name, "status": status, "ms": duration_ms, "note": note})
    print(f"[{status}] {name:<45} {duration_ms:>6}ms  {note}")


def req(method, path, **kwargs):
    global TOKEN
    headers = kwargs.pop("headers", {})
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    t = time.time()
    try:
        r = requests.request(method, BASE_URL + path, headers=headers, timeout=15, **kwargs)
        ms = int((time.time() - t) * 1000)
        return r, ms
    except Exception as e:
        ms = int((time.time() - t) * 1000)
        return None, ms


def test_health():
    r, ms = req("GET", "/health")
    log("Health Check", r and r.status_code == 200, ms)


def test_signup():
    r, ms = req("POST", "/api/auth/signup", json=TEST_USER)
    # 200/201 = created, 400 = already exists — both are acceptable
    passed = r is not None and r.status_code in (200, 201, 400)
    note = ""
    if r is not None:
        body = r.json() or {}
        note = body.get("message") or body.get("error") or ""
    else:
        note = "no response"
    log("User Signup", passed, ms, note)


def test_login():
    global TOKEN
    r, ms = req("POST", "/api/auth/login", json={"username": TEST_USER["username"], "password": TEST_USER["password"]})
    passed = r and r.status_code == 200 and "token" in (r.json() or {})
    if passed:
        TOKEN = r.json()["token"]
    log("User Login", passed, ms)


def test_me():
    r, ms = req("GET", "/api/auth/verify")
    log("Get Current User", r and r.status_code == 200, ms)


def test_upload():
    # Use unique filename to avoid duplicate detection
    unique_name = f"test_{uuid.uuid4().hex[:8]}.txt"
    content = f"FlowBridge test file content {uuid.uuid4()}".encode() * 10
    r, ms = req("POST", "/api/user/upload", files={"file": (unique_name, content, "text/plain")})
    passed = r and r.status_code in (200, 201)
    file_id = None
    if passed:
        data = r.json()
        uploaded = data.get("uploaded") or data.get("files") or []
        file_id = data.get("file_id") or (uploaded[0].get("file_id") if uploaded else None)
    log("File Upload", passed, ms)
    return file_id


def test_list_files():
    r, ms = req("GET", "/api/user/files")
    log("List Files", r and r.status_code == 200, ms)


def test_share_generate(file_id):
    if not file_id:
        log("Share Link Generate", False, 0, "no file_id")
        return None, None
    r, ms = req("POST", "/api/share/generate", json={"file_id": file_id, "expiry_hours": 1})
    passed = r and r.status_code == 200
    token, otp = None, None
    if passed:
        data = r.json()
        token = data.get("share_token")
        otp = data.get("otp")
    log("Share Link Generate", passed, ms)
    return token, otp


def test_verify_otp(share_token, otp):
    if not share_token or not otp:
        log("OTP Verify", False, 0, "missing token/otp")
        return
    r, ms = req("POST", "/api/share/verify-otp", json={"share_token": share_token, "otp": otp})
    log("OTP Verify", r and r.status_code == 200, ms)


def test_advanced_status():
    r, ms = req("GET", "/api/advanced/status")
    log("Advanced Status", r and r.status_code == 200, ms)


def test_crdt():
    r, ms = req("POST", "/api/advanced/crdt/counter/test_counter/increment", json={"amount": 1})
    log("CRDT Counter Increment", r and r.status_code == 200, ms)


def test_wasm():
    r, ms = req("GET", "/api/advanced/wasm/modules")
    log("WASM List Modules", r and r.status_code == 200, ms)


def test_scaling():
    r, ms = req("GET", "/api/scaling/status")
    log("Scaling Status", r and r.status_code == 200, ms)


def test_scaling_health():
    r, ms = req("GET", "/api/scaling/health")
    log("Scaling Health", r and r.status_code in (200, 503), ms)


def save_results():
    with open("test_results.json", "w") as f:
        json.dump({"results": RESULTS, "timestamp": time.time()}, f, indent=2)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    total = len(RESULTS)
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    print(f"Saved to test_results.json")


if __name__ == "__main__":
    print(f"Testing FlowBridge at {BASE_URL}\n{'='*60}")
    test_health()
    test_signup()
    test_login()
    test_me()
    file_id = test_upload()
    test_list_files()
    share_token, otp = test_share_generate(file_id)
    test_verify_otp(share_token, otp)
    test_advanced_status()
    test_crdt()
    test_wasm()
    test_scaling()
    test_scaling_health()
    save_results()
