"""
Constants for authentication, groups, and roles.
Centralizes all group and role names to avoid magic strings.
"""


# User Groups
class UserGroups:
    """User group constants"""

    B2C_GRP = "B2C-GRP"
    B2C_GUEST = "B2C-GUEST"
    CORP_ADMIN = "CORP-ADMIN"
    CORP_EMP = "CORP-EMP"
    CORPORATE_GRP = "CORPORATE-GRP"
    BUSINESS_GRP = "BUSINESS-GRP"
    BUS_ADMIN = "BUS-ADMIN"
    HTLR_ADMIN = "HTLR-ADMIN"
    FRANCH_ADMIN = "FRANCH-ADMIN"
    HOTELIER_GRP = "HOTELIER-GRP"
    FRANCHISE_GRP = "FRANCHISE-GRP"


# Corporate Groups (for wallet deduction logic)
CORPORATE_GROUPS = (
    UserGroups.CORP_ADMIN,
    UserGroups.CORP_EMP,
    UserGroups.CORPORATE_GRP,
)

# B2C Groups (for wallet deduction logic)
B2C_GROUPS = (
    UserGroups.B2C_GRP,
    UserGroups.B2C_GUEST,
)

# All valid groups
ALL_GROUPS = (
    UserGroups.B2C_GRP,
    UserGroups.B2C_GUEST,
    UserGroups.CORP_ADMIN,
    UserGroups.CORP_EMP,
    UserGroups.CORPORATE_GRP,
    UserGroups.BUSINESS_GRP,
    UserGroups.BUS_ADMIN,
    UserGroups.HTLR_ADMIN,
    UserGroups.FRANCH_ADMIN,
    UserGroups.HOTELIER_GRP,
    UserGroups.FRANCHISE_GRP,
)
