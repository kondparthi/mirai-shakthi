"""Phase 1 roles (spec Section 3) and what each may do. Staff log in to the web portal with email + password;
entrepreneurs (role "msme") use mobile + OTP."""

ROLE_LABELS = {
    "admin": "Super Admin",
    "programme_manager": "Programme Manager",
    "coordinator": "District Coordinator / Field Navigator",
    "trainer": "Trainer",
    "dpr_officer": "DPR & Credit Officer",
    "procurement": "Procurement Officer",
    "mentor": "Mentor",
    "sector_expert": "Sector Expert",
    "federation_staff": "SHG Federation Staff",
    "partner_viewer": "Partner Viewer (Bank / CSR / Govt)",
    "reviewer": "Content Reviewer",
}
STAFF_ROLES = tuple(ROLE_LABELS)

# Who can see entrepreneur and group records (within their data scope).
PROGRAMME_READ = ("admin", "programme_manager", "coordinator", "trainer", "dpr_officer", "procurement", "mentor",
                  "sector_expert", "federation_staff")
# Who can enrol and edit entrepreneurs and groups.
PROGRAMME_WRITE = ("admin", "programme_manager", "coordinator", "federation_staff")
# Who can record a readiness assessment.
READINESS_WRITE = ("admin", "programme_manager", "coordinator", "mentor")
# Who sees every district and sector regardless of scope.
ALL_SCOPE = ("admin", "programme_manager")
# Master data, users and access.
MASTERS_WRITE = ("admin", "programme_manager")
ACCESS_ADMIN = ("admin",)
