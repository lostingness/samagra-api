# api/index.py
"""
╔══════════════════════════════════════════════════════════════╗
║  🆔  Samagra MP Intel API — Vercel Serverless              ║
║  GET  /api/samagra?mobile=9171175657                       ║
║  GET  /api/samagra?uid=125142607                            ║
║  POST /api/samagra  {"mobile":"9171175657"}                 ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ============================================================
#  CONFIG
# ============================================================
BASE = "https://samagra.gov.in/Services"
UID_URL = f"{BASE}/CommonWebApi.svc/GetDetailsBySamagra"
KYC_URL = f"{BASE}/CommoneKycApi.svc/GetDetailForKyc"

HEADERS = {
    "User-Agent": "okhttp/3.12.1",
    "Content-Type": "application/json; charset=UTF-8",
    "Authorization": "Basic c2FtYWdyYUFwaTpzYW1hZ3JhQDEyMw==",
    "Host": "samagra.gov.in",
}


# ============================================================
#  CORE: API Calls
# ============================================================
def api_post(url, payload):
    try:
        r = requests.post(
            url, headers=HEADERS, json=payload, timeout=30, verify=False
        )
        if r.status_code != 200:
            return None
        text = r.content.decode("utf-8-sig", errors="ignore").strip()
        return json.loads(text)
    except:
        return None


# ============================================================
#  STEP 1: Mobile → UIDs
# ============================================================
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


# ============================================================
#  STEP 2: UID → Full Details (GetDetailForKyc)
# ============================================================
def uid_to_details(uid):
    res = api_post(KYC_URL, {"samagraID": str(uid), "doEkyc": ""})
    if not res:
        return None

    records = res.get("data", [])
    if not records:
        return None

    r = records[0]

    def fmt_gender(g):
        g = str(g).upper()
        return "Male" if g == "M" else ("Female" if g == "F" else str(g))

    return {
        "uid": str(uid),
        "name": r.get("AadhaarName"),
        "dob": r.get("dob"),
        "gender": fmt_gender(r.get("gender", "")),
        "mobile": r.get("mobile_number"),
        "aadhaar_seeded": r.get("Seeded"),
        "ekyc_date": r.get("EkycDate"),
        "family_members": [
            {
                "name": m.get("AadhaarName"),
                "dob": m.get("dob"),
                "gender": fmt_gender(m.get("gender", "")),
                "mobile": m.get("mobile_number"),
                "aadhaar_seeded": m.get("Seeded"),
                "ekyc_date": m.get("EkycDate"),
            }
            for m in records
        ]
        if len(records) > 1
        else [],
    }


# ============================================================
#  REQUEST PARSING
# ============================================================
def get_param(key):
    val = request.args.get(key, "").strip()
    if val:
        return val
    body = request.get_json(silent=True) or {}
    val = str(body.get(key, "")).strip()
    if val:
        return val
    return request.form.get(key, "").strip() or ""


# ============================================================
#  ROUTES
# ============================================================
@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "service": "Samagra MP Intel API v3.0 — Vercel",
            "provider": "samagra.gov.in — GetDetailForKyc",
            "endpoints": {
                "by_mobile": "/api/samagra?mobile=9171175657",
                "by_uid": "/api/samagra?uid=125142607",
            },
        }
    )


@app.route("/api/samagra", methods=["GET", "POST"])
def samagra_lookup():
    mobile = get_param("mobile")
    uid = get_param("uid")

    # ── Direct UID Lookup ──
    if uid:
        if not uid.isdigit():
            return jsonify({"success": False, "error": "UID must be numeric."}), 400
        info = uid_to_details(uid)
        if not info:
            return jsonify(
                {"success": False, "error": f"No data for UID {uid}."}
            ), 404
        return jsonify(
            {
                "success": True,
                "query_type": "uid",
                "query_value": uid,
                "total_members": 1,
                "members": [info],
            }
        )

    # ── Mobile → UIDs → Details ──
    if mobile:
        if not mobile.isdigit() or len(mobile) != 10:
            return jsonify(
                {"success": False, "error": "Mobile must be 10 digits."}
            ), 400

        uids = mobile_to_uids(mobile)
        if not uids:
            return jsonify(
                {
                    "success": False,
                    "error": f"No Samagra ID found for {mobile}.",
                }
            ), 404

        members = []
        for u in uids:
            info = uid_to_details(u)
            if info:
                members.append(info)

        return jsonify(
            {
                "success": True,
                "query_type": "mobile",
                "query_value": mobile,
                "total_members": len(members),
                "member_ids": uids,
                "members": members,
            }
        )

    return jsonify(
        {
            "success": False,
            "error": "Provide 'mobile' or 'uid'.",
            "usage": {
                "GET": "/api/samagra?mobile=9171175657",
                "POST": '{"mobile":"9171175657"}',
            },
        }
    ), 400


# ============================================================
#  VERCEL SERVERLESS HANDLER
# ============================================================
def handler(environ, start_response):
    """WSGI handler for Vercel serverless runtime."""
    return app(environ, start_response)


# Expose the Flask app directly for Vercel's Python runtime
app.debug = False