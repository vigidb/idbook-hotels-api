"""Central source of truth for Idbook company/legal details.

Update only this file when company info (legal name, address, CIN/PAN/TAN,
contact details) changes. It is exposed to Django templates via the
``company_context`` context processor registered in ``IDBOOKAPI.settings``.
"""

COMPANY = {
    "brand_name": "Idbook",
    "brand_display": "Idbook\u2122",
    "legal_name": "Idbook Private Limited",
    "legal_name_short": "Idbook Private Ltd",
    "address": {
        "hq": {
            "label": "HQ - Haryana",
            "line": (
                "Ground floor, DLF Cyber City, WeWork Forum, "
                "DLF Phase 3, Gurugram, Haryana 122002"
            ),
        },
        "sales_ops": {
            "label": "Sales & Operations - Mumbai",
            "line": (
                "No 2, 1 Mohan Gokhale Rd, 1st & 20th Floor, "
                "Aarey Milk Colony, Mumbai, Maharashtra 400063"
            ),
        },
        "tech": {
            "label": "Tech Office - Bengaluru",
            "line": (
                "XMXQ+66H, B Narayanapura, Mahadevapura, "
                "Bengaluru, Karnataka 560016"
            ),
        },
    },
    "registration": {
        "cin": "U79110HR2025PTC136158",
        "pan": "AAICI4115P",
        "tan": "RTKI06022C",
        "gstin": "06AAICI4115P1ZB",
    },
    "contact": {
        "website": "www.idbookhotels.com",
        "support_phone": "+918645663143",
        "booking_email": "Booking@idbookhotels.com",
        "partner_email": "partner.b2b@idbookhotels.com",
        "support_email": "support@idbookhotels.com",
    },
    # Hotelier PDF service agreement. Service Provider name: ``legal_name`` in the template.
    # Registered office / footer / notification addresses are synced from ``address.hq.line`` below.
    "service_agreement": {
        "head_office_footer": "Head Office: Gurugram, Haryana",
        "dispute_jurisdiction": "GURGAON,HARYANA COURT",
        "services_location": "Gurugram",
        "minimum_term": "1 year",
        "default_commission_percent": "20",
        "logo_url": (
            "https://idbookhotels.s3.eu-north-1.amazonaws.com/logo/idbook+logo.png"
        ),
        # Optional image URL for a graphic common seal. If empty, the PDF uses a text seal
        # with ``legal_name`` (avoids embedding the wrong company name in a raster image).
        "stamp_url": "https://idbookhotels.s3.eu-north-1.amazonaws.com/media/code/Idbook-stamp-seal-and-sign.png",
    },
}


def _sync_service_agreement_addresses_from_hq():
    """Single source of truth: agreement uses ``address.hq.line`` for all office/notification text."""
    hq = " ".join(
        COMPANY["address"]["hq"]["line"].replace("\n", " ").split()
    ).strip()
    sa = COMPANY["service_agreement"]
    sa["contract_party_registered_office"] = hq.upper()
    parts = [p.strip() for p in hq.split(",") if p.strip()]
    if len(parts) <= 1:
        sa["footer_lines"] = (hq,)
    else:
        mid = (len(parts) + 1) // 2
        sa["footer_lines"] = (
            ", ".join(parts[:mid]) + ",",
            ", ".join(parts[mid:]),
        )
    sa["notification_address_line"] = ", ".join(p.lower() for p in parts)


_sync_service_agreement_addresses_from_hq()


def company_context(request=None):
    """Template context processor that exposes COMPANY as ``company``."""
    return {"company": COMPANY}
