import os, time, json, re, requests
from dotenv import load_dotenv
from tally_xml import build_purchase_voucher_xml

load_dotenv()
BACKEND    = os.getenv("BACKEND_URL", "http://localhost:8000")
TALLY      = os.getenv("TALLY_URL",   "http://localhost:8000/api/mock/tally/voucher")
POLL       = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
STATE_FILE = "connector_state.json"


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


def pair(state: dict) -> dict:
    code = input("Enter the pairing code shown in your dashboard: ").strip().upper()
    resp = requests.post(
        f"{BACKEND}/api/tally/pair",
        json={"pairing_code": code, "company_names": ["Mock Company Pvt Ltd"]},
        timeout=10,
    )
    if resp.status_code == 200:
        state["connector_token"] = resp.json()["connector_token"]
        save_state(state)
        print("Paired successfully!")
        return state
    else:
        print(f"Pairing failed: {resp.json().get('detail')}")
        exit(1)


def fetch_config(state: dict) -> dict:
    r = requests.get(f"{BACKEND}/api/tally/config", headers=headers(state), timeout=5)
    if r.status_code == 200:
        state["config"] = r.json()
        save_state(state)
    return state.get("config", {})


def heartbeat(state: dict):
    try:
        r = requests.post(
            f"{BACKEND}/api/tally/heartbeat", headers=headers(state), json={}, timeout=5
        )
        if r.status_code == 200 and r.json().get("config_updated"):
            fetch_config(state)
    except Exception:
        pass


def extract_voucher_id(xml: str) -> str:
    m = re.search(r"<LASTVCHID>(\w+)</LASTVCHID>", xml)
    return m.group(1) if m else ""


def _has_error(xml: str) -> bool:
    if "<LINEERROR>" in xml:
        return True
    m = re.search(r"<ERRORS>(\d+)</ERRORS>", xml)
    if m and int(m.group(1)) > 0:
        return True
    return False


def process_action(action: dict, config: dict, state: dict):
    action_id = action["id"]
    inv = action["data"].get("extracted_invoice", {}) or {}
    supplier = inv.get("supplier_name", "Unknown")
    amount = inv.get("total_amount", 0)
    print(f"  Syncing: {supplier} | ₹{amount}")

    xml = build_purchase_voucher_xml(inv, config)
    try:
        r = requests.post(
            TALLY,
            data=xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=15,
        )
        if _has_error(r.text):
            err = r.text[:300]
            print(f"  ✗ Tally error: {err}")
            requests.post(
                f"{BACKEND}/api/tally/actions/{action_id}/sync-failed",
                headers=headers(state),
                json={"error": err},
            )
        else:
            vid = extract_voucher_id(r.text)
            print(f"  ✓ Synced. Voucher: {vid}")
            requests.post(
                f"{BACKEND}/api/tally/actions/{action_id}/sync-complete",
                headers=headers(state),
                json={"voucher_id": vid},
            )
    except requests.ConnectionError:
        err = f"Tally not reachable at {TALLY}"
        print(f"  ✗ {err}")
        requests.post(
            f"{BACKEND}/api/tally/actions/{action_id}/sync-failed",
            headers=headers(state),
            json={"error": err},
        )


def poll_loop(state: dict):
    config = fetch_config(state)
    print(f"Company : {config.get('company_name', 'not set')}")
    print(f"Polling every {POLL}s — Ctrl+C to stop\n")
    while True:
        try:
            heartbeat(state)
            config = state.get("config", {})
            r = requests.get(
                f"{BACKEND}/api/tally/actions/pending-sync",
                headers=headers(state),
                timeout=5,
            )
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


def main():
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
