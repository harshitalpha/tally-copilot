import os, sys, time, json, re, requests
from dotenv import load_dotenv
from tally_xml import (
    build_purchase_voucher_xml,
    build_ledger_masters_xml,
    build_list_companies_xml,
)

load_dotenv()
BACKEND    = os.getenv("BACKEND_URL", "http://localhost:8000")
TALLY      = os.getenv("TALLY_URL",   "http://localhost:9000")
POLL       = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
STATE_FILE = os.getenv("STATE_FILE", "connector_state.json")


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def headers(state: dict) -> dict:
    return {"X-Connector-Token": state["connector_token"]}


# ── Tally helpers ─────────────────────────────────────────────────────────────

def tally_post(xml: str, timeout: int = 15) -> str:
    r = requests.post(
        TALLY, data=xml.encode("utf-8"),
        headers={"Content-Type": "application/xml"}, timeout=timeout,
    )
    return r.text


def query_companies() -> list[str]:
    """Ask Tally which companies it knows about. Returns [] if unreachable."""
    try:
        text = tally_post(build_list_companies_xml(), timeout=8)
        # Tally returns <COMPANY NAME="..."> or <COMPANYNAME>...</COMPANYNAME>
        names = re.findall(r'<COMPANY[^>]*NAME="([^"]+)"', text)
        names += re.findall(r"<COMPANYNAME>([^<]+)</COMPANYNAME>", text)
        names += re.findall(r"<NAME>([^<]+)</NAME>", text)
        # de-dup, strip, drop empties
        seen, out = set(), []
        for n in names:
            n = n.strip()
            if n and n not in seen:
                seen.add(n); out.append(n)
        return out
    except Exception:
        return []


def tally_reachable() -> bool:
    try:
        requests.get(TALLY, timeout=5)
        return True
    except Exception:
        return False


def _has_error(xml: str) -> bool:
    if "<LINEERROR>" in xml:
        return True
    m = re.search(r"<ERRORS>(\d+)</ERRORS>", xml)
    return bool(m and int(m.group(1)) > 0)


def extract_voucher_id(xml: str) -> str:
    m = re.search(r"<LASTVCHID>(\w+)</LASTVCHID>", xml)
    return m.group(1) if m else ""


# ── Backend helpers ───────────────────────────────────────────────────────────

def pair(state: dict) -> dict:
    code = input("Enter the pairing code shown in your dashboard: ").strip().upper()

    # Try to read real company names straight from Tally; fall back to manual.
    companies = query_companies()
    if companies:
        print(f"Found {len(companies)} company(ies) in Tally: {', '.join(companies)}")
    else:
        print("Could not auto-detect companies from Tally.")
        manual = input("Type your company name EXACTLY as shown in Tally's title bar: ").strip()
        companies = [manual] if manual else ["Unknown Company"]

    resp = requests.post(
        f"{BACKEND}/api/tally/pair",
        json={"pairing_code": code, "company_names": companies},
        timeout=10,
    )
    if resp.status_code == 200:
        state["connector_token"] = resp.json()["connector_token"]
        save_state(state)
        print("Paired successfully!")
        return state
    print(f"Pairing failed: {resp.json().get('detail')}")
    sys.exit(1)


def fetch_config(state: dict) -> dict:
    r = requests.get(f"{BACKEND}/api/tally/config", headers=headers(state), timeout=5)
    if r.status_code == 200:
        state["config"] = r.json()
        save_state(state)
    return state.get("config", {})


def heartbeat(state: dict):
    try:
        r = requests.post(f"{BACKEND}/api/tally/heartbeat", headers=headers(state), json={}, timeout=5)
        if r.status_code == 200 and r.json().get("config_updated"):
            fetch_config(state)
    except Exception:
        pass


# ── Processing ────────────────────────────────────────────────────────────────

def ensure_masters(inv: dict, config: dict):
    """Best-effort: create supplier + ledgers if missing. Errors are ignored
    (a ledger that already exists returns an error we don't care about)."""
    try:
        tally_post(build_ledger_masters_xml(inv, config))
    except Exception as e:
        print(f"  (master pre-create skipped: {e})")


def process_action(action: dict, config: dict, state: dict):
    action_id = action["id"]
    inv = action["data"].get("extracted_invoice", {}) or {}
    supplier = inv.get("supplier_name", "Unknown")
    amount = inv.get("total_amount", 0)
    print(f"  Syncing: {supplier} | ₹{amount}")

    if config.get("auto_create_ledgers"):
        ensure_masters(inv, config)

    try:
        text = tally_post(build_purchase_voucher_xml(inv, config))
        if _has_error(text):
            err = text[:300]
            print(f"  ✗ Tally error: {err}")
            requests.post(f"{BACKEND}/api/tally/actions/{action_id}/sync-failed",
                          headers=headers(state), json={"error": err})
        else:
            vid = extract_voucher_id(text)
            print(f"  ✓ Synced. Voucher: {vid}")
            requests.post(f"{BACKEND}/api/tally/actions/{action_id}/sync-complete",
                          headers=headers(state), json={"voucher_id": vid})
    except requests.ConnectionError:
        err = f"Tally not reachable at {TALLY}"
        print(f"  ✗ {err}")
        requests.post(f"{BACKEND}/api/tally/actions/{action_id}/sync-failed",
                      headers=headers(state), json={"error": err})


def poll_loop(state: dict):
    config = fetch_config(state)
    print(f"Company : {config.get('company_name', 'not set')}")
    print(f"Polling every {POLL}s — Ctrl+C to stop\n")
    while True:
        try:
            heartbeat(state)
            config = state.get("config", {})
            r = requests.get(f"{BACKEND}/api/tally/actions/pending-sync",
                             headers=headers(state), timeout=5)
            actions = r.json()
            if actions:
                print(f"[{len(actions)} to sync]")
                for a in actions:
                    process_action(a, config, state)
            else:
                print(".", end="", flush=True)
        except requests.ConnectionError:
            print("\n[backend offline]", end="", flush=True)
        except Exception as e:
            print(f"\n[error: {e}]", end="", flush=True)
        time.sleep(POLL)


# ── Diagnostics ───────────────────────────────────────────────────────────────

def cmd_test():
    """`python connector.py test` — verify Tally + backend before pairing."""
    print("=" * 50)
    print("Tally Co-pilot Connector — connection test")
    print("=" * 50)

    print(f"\n1. Backend  ({BACKEND})")
    try:
        r = requests.get(f"{BACKEND}/health", timeout=8)
        print(f"   ✓ reachable — {r.json()}")
    except Exception as e:
        print(f"   ✗ NOT reachable: {e}")
        print("     → Check BACKEND_URL in .env. If backend is on another")
        print("       machine, use its LAN IP or public URL (not localhost).")

    print(f"\n2. Tally gateway  ({TALLY})")
    if tally_reachable():
        print("   ✓ port is open")
        companies = query_companies()
        if companies:
            print(f"   ✓ companies detected: {', '.join(companies)}")
        else:
            print("   ⚠ port open but no companies returned.")
            print("     → Make sure a company is OPEN in Tally.")
    else:
        print("   ✗ NOT reachable")
        print("     → In Tally: F1 (Help) → Settings → Connectivity →")
        print("       Client/Server config → 'TallyPrime acts as' = Both,")
        print("       Port = 9000. Then open your company.")
    print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        cmd_test()
        return

    print("=" * 45)
    print("Tally Co-pilot Connector")
    print(f"Backend : {BACKEND}")
    print(f"Tally   : {TALLY}")
    print("=" * 45)
    state = load_state()
    if not state.get("connector_token"):
        state = pair(state)
    poll_loop(state)


if __name__ == "__main__":
    main()
