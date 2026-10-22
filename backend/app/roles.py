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

# Phase 1 Sprint 2 – training (M4)
TRAINING_READ = PROGRAMME_READ                                   # see batches in scope (trainers: their own batches)
TRAINING_ADMIN = ("admin", "programme_manager")                  # courses and training partners
BATCH_WRITE = ("admin", "programme_manager", "coordinator")      # plan batches, nominate, verify external certificates
TRAINING_RUN = BATCH_WRITE + ("trainer",)                        # sessions, attendance, assessment, results
FOLLOWUP_WRITE = ("admin", "programme_manager", "coordinator", "mentor")

# Phase 1 Sprint 3 – DPR & finance (M5, M6)
DPR_READ = PROGRAMME_READ                                        # see DPRs and applications in scope
DPR_WRITE = ("admin", "programme_manager", "dpr_officer")        # prepare DPRs, track applications and repayments
DPR_APPROVE = ("admin", "programme_manager", "dpr_officer")      # review and approve DPRs
MODELS_WRITE = ("admin", "programme_manager", "sector_expert")   # enterprise models (DPR templates)
SCHEMES_WRITE = ("admin", "programme_manager", "dpr_officer")    # scheme library

# Phase 1 Sprint 4 – enterprise set-up and procurement (M7)
SETUP_READ = PROGRAMME_READ                                                  # see units in scope
SETUP_WRITE = ("admin", "programme_manager", "procurement", "coordinator", "dpr_officer")  # registrations, readiness, assets
PROCURE = ("admin", "programme_manager", "procurement")                      # quotations, purchase orders, suppliers
LAUNCH = ("admin", "programme_manager", "coordinator", "procurement")         # mark a unit launched
