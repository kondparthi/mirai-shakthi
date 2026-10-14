"""SkillsPro – job description templates for common micro-enterprise roles.
Templates are starting points; the owner edits duties, skills, hours and pay before generating."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator

ROLES = {
    "production_worker": {
        "title": "Production helper",
        "purpose": "Helps make products safely and to the agreed quality and quantity each day.",
        "duties": ["Prepare raw material and work area at the start of the shift", "Operate simple tools and machines as trained",
                   "Pack and label finished products", "Keep the work area clean and follow hygiene rules", "Report damaged material or machine problems"],
        "skills": ["Willing to learn", "Can follow instructions", "Basic counting"],
        "qualification": "No formal qualification required; 8th class preferred",
    },
    "sales_executive": {
        "title": "Sales executive",
        "purpose": "Finds new customers, takes orders and collects payments on time.",
        "duties": ["Visit shops, institutions and customers in the assigned area", "Explain products, prices and offers",
                   "Take orders and pass them to the office the same day", "Follow up on payments due", "Keep a daily record of visits and orders"],
        "skills": ["Good communication in Telugu (English is a plus)", "Smartphone and WhatsApp use", "Two-wheeler and licence"],
        "qualification": "10th / 12th pass",
    },
    "accounts_assistant": {
        "title": "Accounts assistant",
        "purpose": "Keeps the daily accounts, bills and payment records up to date.",
        "duties": ["Record daily sales, purchases and expenses", "Prepare bills and invoices", "Track money owed by customers and to suppliers",
                   "Reconcile cash and bank every week", "Share monthly figures with the owner and the CA"],
        "skills": ["Basic accounting", "Excel or accounting software", "Accuracy with numbers"],
        "qualification": "B.Com or equivalent preferred",
    },
    "delivery_person": {
        "title": "Delivery person",
        "purpose": "Delivers orders to customers on time and collects payment where agreed.",
        "duties": ["Load orders and check them against the delivery list", "Deliver safely within the agreed time",
                   "Collect cash or confirm UPI payment and give receipts", "Report returns or complaints", "Keep the vehicle clean and fuelled"],
        "skills": ["Valid driving licence", "Knows local routes", "Honest with cash handling"],
        "qualification": "8th / 10th pass",
    },
    "machine_operator": {
        "title": "Machine operator",
        "purpose": "Runs and maintains machines to produce the daily target safely.",
        "duties": ["Set up and run the machine as per the job card", "Check quality of output at regular intervals",
                   "Do daily cleaning and basic maintenance", "Record output, downtime and material used", "Follow all safety rules and wear protective gear"],
        "skills": ["Experience on similar machines", "Basic measurement", "Safety awareness"],
        "qualification": "ITI or equivalent experience",
    },
    "cook_helper": {
        "title": "Cook / kitchen helper",
        "purpose": "Prepares food items to the standard recipe while keeping the kitchen clean and safe.",
        "duties": ["Prepare ingredients and cook items as per the recipe", "Store food at the right temperature",
                   "Keep the kitchen, utensils and self clean (FSSAI hygiene rules)", "Track stock of ingredients", "Serve or pack orders"],
        "skills": ["Cooking experience", "Hygiene awareness", "Can work in busy hours"],
        "qualification": "No formal qualification required",
    },
    "custom": {"title": "", "purpose": "", "duties": [], "skills": [], "qualification": ""},
}

ONBOARDING = [
    "Give a written appointment letter with role, pay, hours, weekly off and notice period",
    "Collect ID proof, address proof, photo and bank details",
    "Show the workplace, safety rules and who to report to",
    "Train on the main tasks for the first week with an experienced person",
    "Agree how attendance and pay will be recorded",
    "Review progress after 30 days and give feedback",
]


class JdIn(BaseModel):
    role_key: str = "custom"
    title: str = Field(min_length=2, max_length=120)
    purpose: str = Field(min_length=5, max_length=500)
    duties: list[str] = Field(min_length=1, max_length=15)
    skills: list[str] = Field(default=[], max_length=15)
    qualification: Optional[str] = Field(default=None, max_length=200)
    openings: int = Field(default=1, ge=1, le=500)
    employment_type: str = Field(default="Full-time", max_length=40)
    work_hours: Optional[str] = Field(default=None, max_length=120)
    pay: Optional[str] = Field(default=None, max_length=120)
    location: Optional[str] = Field(default=None, max_length=120)
    contact: Optional[str] = Field(default=None, max_length=160)

    @field_validator("duties", "skills")
    @classmethod
    def clean(cls, v):
        return [s.strip() for s in v if s and s.strip()]
