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
    },
}


def company_context(request=None):
    """Template context processor that exposes COMPANY as ``company``."""
    return {"company": COMPANY}
