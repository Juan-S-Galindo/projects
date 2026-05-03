from __future__ import annotations

CHASE_CATEGORY_MAP: dict[str, str] = {
    "Food & Drink": "dining",
    "Groceries": "groceries",
    "Gas": "gas",
    "Travel": "travel",
    "Shopping": "shopping",
    "Entertainment": "entertainment",
    "Health & Wellness": "medical",
    "Personal": "personal_care",
    "Bills & Utilities": "utilities",
    "Education": "education",
    "Automotive": "automotive",
    "Home": "home_improvement",
    "Gifts & Donations": "gifts",
    "Professional Services": "fees",
    "Payment": "transfer",
    "Fees & Adjustments": "fees",
}

# Ordered most-specific first; first match wins
KEYWORD_RULES: list[tuple[list[str], str]] = [
    # Mortgage / HOA (check before generic "transfer")
    (["lakeview ln srv", "mtg pymt", "mortgage"], "mortgage"),
    (["caliterra homeowners", "homeowners", " hoa "], "hoa"),
    # Dining
    (["doordash", "ubereats", "grubhub", "postmates", "instacart",
      "chick-fil-a", "chipotle", "mcdonald", "starbucks", "dunkin",
      "subway", "domino", "pizza", "taco bell", "panera", "wendy",
      "burger king", "olive garden", "applebee", "coffee", "mazama",
      "restaurant", "sushi", "tacos", "bbq", "grill", "diner"], "dining"),
    # Groceries
    (["h-e-b", "heb", "kroger", "whole foods", "costco", "sam's club",
      "aldi", "trader joe", "sprouts", "publix", "randalls", "tom thumb",
      "walmart grocery", "target grocery"], "groceries"),
    # Gas
    (["h-e-b gas", "heb gas", "exxon", "shell", "chevron", "texaco",
      "bp ", "racetrac", "murphy", "buc-ee", "valero", "circle k",
      "gas station", "gas/car wash"], "gas"),
    # Streaming
    (["netflix", "hulu", "spotify", "disney+", "hbo max", "hbo",
      "paramount+", "peacock", "youtube premium", "pandora",
      "apple.com/bill", "apple tv"], "streaming"),
    # Utilities
    (["pedernales", "one gas texas", "centerpoint", "txu energy",
      "atmos", "spectrum", "comcast", "xfinity", "at&t", "verizon",
      "t-mobile", "google fi", "dripping springs water", "city of dripping springs",
      "city of austin", "oncor", "austin energy"], "utilities"),
    # Insurance
    (["state farm", "geico", "progressive", "allstate", "farmers",
      "usaa", "blue cross", "aetna", "cigna", "humana", "oscar health",
      "lemonade insurance"], "insurance"),
    # Medical / pharmacy
    (["cvs", "walgreens", "rite aid", "hospital", "clinic",
      "urgent care", "labcorp", "quest diagnostics", "dentist",
      "optometrist", "pharmacy", "medical"], "medical"),
    # Fitness
    (["golds gym", "gold's gym", "planet fitness", "equinox",
      "la fitness", "24 hour fitness", "anytime fitness", "peloton",
      "ymca", "crunch fitness", "belterra"], "fitness"),
    # Subscriptions (non-streaming software)
    (["adobe", "microsoft 365", "dropbox", "github", "notion",
      "openai", "anthropic", "chatgpt", "google one", "icloud",
      "lastpass", "nordvpn"], "subscriptions"),
    # Automotive
    (["jiffy lube", "autozone", "napa auto", "pep boys", "midas",
      "firestone", "goodyear", "car wash", "carmax", "central garage",
      "cwp domain", "automotive"], "automotive"),
    # Shopping / e-commerce
    (["amazon", "amazon mktpl", "ebay", "etsy", "shein", "wayfair",
      "best buy", "apple store", "target", "walmart", "costco whse",
      "nordstrom", "macy"], "shopping"),
    # Pets
    (["petco", "petsmart", "chewy", "vet", "animal hosp",
      "wildflower animal"], "pets"),
    # Credit card payments
    (["chase credit crd des", "chase credit card payment"], "credit_card_payment"),
    # Transfer / payments (check after mortgage/hoa)
    (["online scheduled transfer", "online banking transfer from",
      "payment thank you", "autopay",
      "applecard gsbank", "zelle to", "venmo to", "transfer to",
      "overdraft protection"], "transfer"),
    # Income (specific deposit types only — generic "deposit" handled below)
    (["payroll", "direct deposit", "ach deposit", "zelle from",
      "venmo from"], "income"),
    # Deposits that are not income (transfers in, reimbursements, etc.)
    (["deposit"], "deposit"),
]

ALL_CATEGORIES = [
    "dining", "groceries", "gas", "utilities", "streaming",
    "subscriptions", "mortgage", "hoa", "rent", "insurance",
    "medical", "shopping", "automotive", "travel", "transportation",
    "entertainment", "fitness", "education", "personal_care",
    "home_improvement", "pets", "gifts", "fees", "income",
    "transfer", "credit_card_payment", "deposit", "uncategorized",
]

CATEGORY_LABELS = {
    "dining": "Dining",
    "groceries": "Groceries",
    "gas": "Gas",
    "utilities": "Utilities",
    "streaming": "Streaming",
    "subscriptions": "Subscriptions",
    "mortgage": "Mortgage",
    "hoa": "HOA",
    "rent": "Rent",
    "insurance": "Insurance",
    "medical": "Medical",
    "shopping": "Shopping",
    "automotive": "Automotive",
    "travel": "Travel",
    "transportation": "Transportation",
    "entertainment": "Entertainment",
    "fitness": "Fitness",
    "education": "Education",
    "personal_care": "Personal Care",
    "home_improvement": "Home Improvement",
    "pets": "Pets",
    "gifts": "Gifts",
    "fees": "Fees",
    "income": "Income",
    "transfer": "Transfer",
    "credit_card_payment": "Credit Card Payment",
    "deposit": "Deposit",
    "uncategorized": "Uncategorized",
}


def auto_categorize(description: str, chase_category: str | None = None) -> str:
    if chase_category:
        mapped = CHASE_CATEGORY_MAP.get(chase_category)
        if mapped:
            return mapped

    lower = description.lower()
    for keywords, category in KEYWORD_RULES:
        if any(kw in lower for kw in keywords):
            return category

    return "uncategorized"
