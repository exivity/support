import os
import sys
import requests

BASE_URL = os.getenv("EXIVITY_BASE_URL", "https://localhost")
USERNAME = os.getenv("EXIVITY_USERNAME", "username")
PASSWORD = os.getenv("EXIVITY_PASSWORD", "password")
VERIFY = True  # set False in case of self signed SSL certificate (not recommended)

def get_token():
    url = f"{BASE_URL}/v1/auth/token"
    r = requests.post(
        url,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        data={"username": USERNAME, "password": PASSWORD},
        verify=VERIFY,
    )
    r.raise_for_status()
    token = r.json().get("token")
    if not token:
        raise RuntimeError("No token returned from /v1/auth/token")
    return token

def get_paginated_rates(token, include_service=True):
    items = []
    limit = 500
    offset = 0
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    while True:
        params = {"page[limit]": str(limit), "page[offset]": str(offset)}
        if include_service:
            params["include"] = "service"
        r = requests.get(f"{BASE_URL}/v1/rates", headers=headers, params=params, verify=VERIFY)
        r.raise_for_status()
        payload = r.json()
        batch = payload.get("data", [])
        items.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return items

def get_services_map_from_included(payload_items):
    # When include=service is used, each rate object has relationships.service.data or the service is in 'included'.
    # v1 responses commonly allow include=service. [[get rates](https://api.exivity.com)]
    services = {}
    for item in payload_items:
        # We can’t access top-level 'included' here because we paginated; so we take service id from relationships
        rel = item.get("relationships", {}) or {}
        svc_rel = rel.get("service", {}) or {}
        svc_data = svc_rel.get("data") or {}
        svc_id = svc_data.get("id")
        if svc_id:
            services.setdefault(svc_id, True)
    return services

def effective_date_key(date_str):
    # yyyy-mm or yyyy-mm-dd -> comparable int
    if not date_str:
        return -1
    digits = date_str.replace("-", "")
    if len(digits) == 6:  # yyyyMM
        digits += "00"
    try:
        return int(digits)
    except Exception:
        return -1

def is_global_rate(rate_obj):
    rel = rate_obj.get("relationships", {}) or {}
    acc = rel.get("account", {}) or {}
    return acc.get("data") is None

def main():
    try:
        token = get_token()
    except Exception as e:
        print(f"ERROR: authentication failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Get all rates with included service linkage
    try:
        rates = get_paginated_rates(token, include_service=True)  # bearerAuth required [[get rates](https://api.exivity.com)]
    except Exception as e:
        print(f"ERROR: fetching rates failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Build latest global rate per service
    latest_rate_by_service = {}
    for rate in rates:
        attrs = rate.get("attributes", {}) or {}
        eff = attrs.get("effective_date")  # string yyyy-mm(-dd) [[Rate object](https://api.exivity.com)]
        rel = rate.get("relationships", {}) or {}
        svc_rel = rel.get("service", {}) or {}
        svc_data = svc_rel.get("data") or {}
        svc_id = svc_data.get("id")
        if not svc_id or not eff:
            continue
        if not is_global_rate(rate):
            continue

        current = latest_rate_by_service.get(svc_id)
        if (current is None) or (effective_date_key(eff) > effective_date_key(current["effective_date"])):
            latest_rate_by_service[svc_id] = {
                "effective_date": eff,
                "rate": attrs.get("rate"),
                "fixed": attrs.get("fixed"),
                "cogs_rate": attrs.get("cogs_rate"),
                "cogs_fixed": attrs.get("cogs_fixed"),
            }

    # We still need service names. Fetch services separately and map id -> description.
    # v1 services endpoint exists; bearerAuth applies. [[get services](https://api.exivity.com)]
    try:
        services = []
        # simple paginator
        limit, offset = 500, 0
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        while True:
            r = requests.get(f"{BASE_URL}/v1/services", headers=headers,
                             params={"page[limit]": str(limit), "page[offset]": str(offset)}, verify=VERIFY)
            r.raise_for_status()
            data = r.json().get("data", [])
            services.extend(data)
            if len(data) < limit:
                break
            offset += limit
    except Exception as e:
        print(f"ERROR: fetching services failed: {e}", file=sys.stderr)
        sys.exit(1)

    services_by_id = {s["id"]: s for s in services}

    print("service_id,service_name,rate_effective_date,rate,cogs")
    for svc_id, rateinfo in latest_rate_by_service.items():
        svc = services_by_id.get(svc_id, {})
        sattrs = svc.get("attributes", {}) or {}
        service_name = sattrs.get("description", "")  # friendly name on Rates screen [[Rates basics](https://docs.exivity.com/the%20basics/services/rates/)]
        # Prefer per-unit; fall back to per-interval
        rate_val = rateinfo.get("rate")
        if rate_val in (None, 0) and rateinfo.get("fixed") not in (None, 0):
            rate_val = rateinfo.get("fixed")
        cogs_val = rateinfo.get("cogs_rate")
        if cogs_val in (None, 0) and rateinfo.get("cogs_fixed") not in (None, 0):
            cogs_val = rateinfo.get("cogs_fixed")

        print(f'{svc_id},"{service_name}",{rateinfo.get("effective_date","")},{"" if rate_val is None else rate_val},{"" if cogs_val is None else cogs_val}')

if __name__ == "__main__":
    main()