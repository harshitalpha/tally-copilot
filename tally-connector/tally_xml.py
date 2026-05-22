def build_purchase_voucher_xml(inv: dict, config: dict) -> str:
    date    = (inv.get("invoice_date") or "").replace("-", "")
    sup     = inv.get("supplier_name") or "Unknown Supplier"
    inv_no  = inv.get("invoice_number") or ""
    total   = float(inv.get("total_amount") or 0)
    taxable = float(inv.get("total_taxable_amount") or 0)
    cgst    = float(inv.get("total_cgst") or 0)
    sgst    = float(inv.get("total_sgst") or 0)
    igst    = float(inv.get("total_igst") or 0)
    items   = inv.get("line_items") or []
    cgst_r  = float((items[0].get("cgst_rate") or 0)) if items else 0
    igst_r  = float((items[0].get("igst_rate") or 0)) if items else 0

    entries = [
        {"name": config.get("purchase_ledger", "Purchases"), "amount": -taxable, "pos": "No"}
    ]
    if cgst > 0:
        r = int(cgst_r)
        entries.append({
            "name": config.get("cgst_ledger_format", "CGST @ {rate}%").replace("{rate}", str(r)),
            "amount": -cgst,
            "pos": "No",
        })
        entries.append({
            "name": config.get("sgst_ledger_format", "SGST @ {rate}%").replace("{rate}", str(r)),
            "amount": -sgst,
            "pos": "No",
        })
    if igst > 0:
        r = int(igst_r)
        entries.append({
            "name": config.get("igst_ledger_format", "IGST @ {rate}%").replace("{rate}", str(r)),
            "amount": -igst,
            "pos": "No",
        })
    entries.append({"name": sup, "amount": total, "pos": "Yes"})

    ledger_xml = "".join(
        f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{e['name']}</LEDGERNAME>"
        f"<ISDEEMEDPOSITIVE>{e['pos']}</ISDEEMEDPOSITIVE><AMOUNT>{e['amount']:.2f}</AMOUNT>"
        f"</ALLLEDGERENTRIES.LIST>"
        for e in entries
    )
    return (
        f"<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
        f"<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>"
        f"<STATICVARIABLES><SVCURRENTCOMPANY>{config.get('company_name', '')}</SVCURRENTCOMPANY></STATICVARIABLES>"
        f"</REQUESTDESC><REQUESTDATA><TALLYMESSAGE xmlns:UDF=\"TallyUDF\">"
        f"<VOUCHER VCHTYPE=\"Purchase\" ACTION=\"Create\">"
        f"<DATE>{date}</DATE>"
        f"<NARRATION>Purchase from {sup} | Invoice: {inv_no}</NARRATION>"
        f"<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>"
        f"<PARTYLEDGERNAME>{sup}</PARTYLEDGERNAME>"
        f"<ISINVOICE>Yes</ISINVOICE>{ledger_xml}"
        f"</VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
    )
