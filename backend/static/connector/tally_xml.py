def _esc(s) -> str:
    """Escape a value for safe inclusion in Tally XML."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _ledger_names(inv: dict, config: dict) -> dict:
    """Resolve the ledger names this voucher will reference."""
    items  = inv.get("line_items") or []
    cgst_r = int(float((items[0].get("cgst_rate") or 0))) if items else 0
    igst_r = int(float((items[0].get("igst_rate") or 0))) if items else 0
    return {
        "supplier": inv.get("supplier_name") or "Unknown Supplier",
        "purchase": config.get("purchase_ledger", "Purchases"),
        "cgst": config.get("cgst_ledger_format", "CGST @ {rate}%").replace("{rate}", str(cgst_r)),
        "sgst": config.get("sgst_ledger_format", "SGST @ {rate}%").replace("{rate}", str(cgst_r)),
        "igst": config.get("igst_ledger_format", "IGST @ {rate}%").replace("{rate}", str(igst_r)),
    }


def build_list_companies_xml() -> str:
    """Request the list of companies known to Tally (Export → Collection)."""
    return (
        "<ENVELOPE>"
        "<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>"
        "<TYPE>Collection</TYPE><ID>List of Companies</ID></HEADER>"
        "<BODY><DESC><STATICVARIABLES>"
        "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
        "</STATICVARIABLES><TDL><TDLMESSAGE>"
        '<COLLECTION NAME="List of Companies" ISMODIFY="No">'
        "<TYPE>Company</TYPE><NATIVEMETHOD>Name</NATIVEMETHOD>"
        "</COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"
    )


def build_ledger_masters_xml(inv: dict, config: dict) -> str:
    """Create the ledgers this voucher needs, if they don't already exist.

    Best-effort: Tally returns an error for ledgers that already exist; the
    connector ignores master-creation errors and proceeds to the voucher.
    Tax ledgers are created as plain ledgers under "Duties & Taxes" — for full
    GST classification, pre-create them in Tally with the correct tax setup.
    """
    company = config.get("company_name", "")
    total_igst = float(inv.get("total_igst") or 0)
    names = _ledger_names(inv, config)

    masters = [
        (names["supplier"], "Sundry Creditors"),
        (names["purchase"], "Purchase Accounts"),
    ]
    if total_igst > 0:
        masters.append((names["igst"], "Duties & Taxes"))
    else:
        masters.append((names["cgst"], "Duties & Taxes"))
        masters.append((names["sgst"], "Duties & Taxes"))

    ledger_msgs = "".join(
        f'<LEDGER NAME="{_esc(name)}" ACTION="Create">'
        f"<NAME>{_esc(name)}</NAME>"
        f"<PARENT>{_esc(parent)}</PARENT>"
        f"</LEDGER>"
        for name, parent in masters
    )
    return (
        "<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
        "<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>All Masters</REPORTNAME>"
        f"<STATICVARIABLES><SVCURRENTCOMPANY>{_esc(company)}</SVCURRENTCOMPANY></STATICVARIABLES>"
        '</REQUESTDESC><REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f"{ledger_msgs}"
        "</TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
    )


def build_purchase_voucher_xml(inv: dict, config: dict) -> str:
    date    = (inv.get("invoice_date") or "").replace("-", "")
    sup     = inv.get("supplier_name") or "Unknown Supplier"
    inv_no  = inv.get("invoice_number") or ""
    total   = float(inv.get("total_amount") or 0)
    taxable = float(inv.get("total_taxable_amount") or 0)
    cgst    = float(inv.get("total_cgst") or 0)
    sgst    = float(inv.get("total_sgst") or 0)
    igst    = float(inv.get("total_igst") or 0)
    names   = _ledger_names(inv, config)

    entries = [
        {"name": names["purchase"], "amount": -taxable, "pos": "No"}
    ]
    if cgst > 0:
        entries.append({"name": names["cgst"], "amount": -cgst, "pos": "No"})
        entries.append({"name": names["sgst"], "amount": -sgst, "pos": "No"})
    if igst > 0:
        entries.append({"name": names["igst"], "amount": -igst, "pos": "No"})
    entries.append({"name": sup, "amount": total, "pos": "Yes"})

    ledger_xml = "".join(
        f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{_esc(e['name'])}</LEDGERNAME>"
        f"<ISDEEMEDPOSITIVE>{e['pos']}</ISDEEMEDPOSITIVE><AMOUNT>{e['amount']:.2f}</AMOUNT>"
        f"</ALLLEDGERENTRIES.LIST>"
        for e in entries
    )
    return (
        f"<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
        f"<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>"
        f"<STATICVARIABLES><SVCURRENTCOMPANY>{_esc(config.get('company_name', ''))}</SVCURRENTCOMPANY></STATICVARIABLES>"
        f"</REQUESTDESC><REQUESTDATA><TALLYMESSAGE xmlns:UDF=\"TallyUDF\">"
        f"<VOUCHER VCHTYPE=\"Purchase\" ACTION=\"Create\">"
        f"<DATE>{date}</DATE>"
        f"<NARRATION>Purchase from {_esc(sup)} | Invoice: {_esc(inv_no)}</NARRATION>"
        f"<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>"
        f"<PARTYLEDGERNAME>{_esc(sup)}</PARTYLEDGERNAME>"
        f"<ISINVOICE>Yes</ISINVOICE>{ledger_xml}"
        f"</VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
    )
