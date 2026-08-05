from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://samagra.gov.in/Services"
UID_URL = f"{BASE}/CommonWebApi.svc/GetDetailsBySamagra"
KYC_URL = f"{BASE}/CommoneKycApi.svc/GetDetailForKyc"

HEADERS = {
    "User-Agent": "okhttp/3.12.1",
    "Content-Type": "application/json; charset=UTF-8",
    "Authorization": "Basic c2FtYWdyYUFwaTpzYW1hZ3JhQDEyMw==",
    "Host": "samagra.gov.in",
}

def api_post(url, payload):
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=25, verify=False)
        if r.status_code != 200:
            return None
        text = r.content.decode("utf-8-sig", errors="ignore").strip()
        return json.loads(text)
    except:
        return None

def mobile_to_uids(mobile):
    res = api_post(UID_URL, {"samagraID": "0", "MobileNo": mobile})
    if not res:
        return []
    data = res.get("d", res)
    items = data if isinstance(data, list) else data.get("data", []) or [data]
    uids = []
    for item in items:
        if isinstance(item, dict):
            for k in ("UserID", "samagraID", "MemberID"):
                v = item.get(k)
                if v:
                    uids.append(str(v))
                    break
    return list(dict.fromkeys(uids))

def uid_to_details(uid):
    res = api_post(KYC_URL, {"samagraID": str(uid), "doEkyc": ""})
    if not res:
        return None
    records = res.get("data", [])
    if not records:
        return None
    r = records[0]

    def g(val):
        v = str(val or "").upper()
        return "Male" if v == "M" else ("Female" if v == "F" else str(val))

    return {
        "uid": str(uid),
        "name": r.get("AadhaarName"),
        "dob": r.get("dob"),
        "gender": g(r.get("gender", "")),
        "mobile": r.get("mobile_number"),
        "aadhaar_seeded": r.get("Seeded"),
        "ekyc_date": r.get("EkycDate"),
        "family_members": [
            {
                "name": m.get("AadhaarName"),
                "dob": m.get("dob"),
                "gender": g(m.get("gender", "")),
                "mobile": m.get("mobile_number"),
                "aadhaar_seeded": m.get("Seeded"),
                "ekyc_date": m.get("EkycDate"),
            }
            for m in records
        ] if len(records) > 1 else [],
    }

def json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def parse_query(path):
    parsed = urllib.parse.urlparse(path)
    params = urllib.parse.parse_qs(parsed.query)
    return {k: v[0] for k, v in params.items()}, parsed.path

def parse_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", 0))
        if length > 0:
            raw = handler.rfile.read(length)
            return json.loads(raw)
    except:
        pass
    return {}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle()
    def do_POST(self):
        self.handle()
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def handle(self):
        params, path = parse_query(self.path)
        body = parse_body(self)

        mobile = params.get("mobile", "") or body.get("mobile", "")
        uid = params.get("uid", "") or body.get("uid", "")

        # Health check
        if path in ("/", "/health", ""):
            return json_response(self, {
                "service": "Samagra MP Intel API",
                "endpoints": {
                    "mobile": "/api/samagra?mobile=9171175657",
                    "uid": "/api/samagra?uid=125142607"
                }
            })

        # Samagra lookup
        if "/api/samagra" in path:
            if uid:
                if not uid.isdigit():
                    return json_response(self, {"success": False, "error": "UID must be numeric."}, 400)
                info = uid_to_details(uid)
                if not info:
                    return json_response(self, {"success": False, "error": f"No data for UID {uid}."}, 404)
                return json_response(self, {"success": True, "query_type": "uid", "query_value": uid, "total_members": 1, "members": [info]})

            if mobile:
                if not mobile.isdigit() or len(mobile) != 10:
                    return json_response(self, {"success": False, "error": "Mobile must be 10 digits."}, 400)
                uids = mobile_to_uids(mobile)
                if not uids:
                    return json_response(self, {"success": False, "error": f"No Samagra ID found for {mobile}."}, 404)
                members = [info for u in uids if (info := uid_to_details(u))]
                return json_response(self, {"success": True, "query_type": "mobile", "query_value": mobile, "total_members": len(members), "member_ids": uids, "members": members})

            return json_response(self, {"success": False, "error": "Pass ?mobile= or ?uid="}, 400)

        return json_response(self, {"success": False, "error": "Not found"}, 404)

    def log_message(self, format, *args):
        pass
