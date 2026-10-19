"""Domain synonym normalisation for the preprocessing pipeline.

TF-IDF only matches shared words, so "erase my account" cannot find "delete my
account" on its own. Each group below maps interchangeable e-commerce vocabulary to
one canonical word. The map is applied to lemmatised tokens on both the FAQ side and
the user side, so the canonical word never needs to appear in either text.

Rules for adding entries:
  * variants must already be lemma forms (a test enforces this)
  * only merge words that are interchangeable *in this domain*
  * never merge words that distinguish two FAQs (e.g. "return" vs "refund")
"""

_GROUPS: dict[str, tuple[str, ...]] = {
    # logistics
    "package": ("parcel", "shipment"),
    "shipping": ("postage",),
    "carrier": ("courier",),
    "international": ("abroad", "overseas", "worldwide", "internationally"),
    "express": ("rush", "expedite", "overnight"),
    "late": ("delay", "overdue"),
    # account and security
    "delete": ("erase", "remove"),
    "lock": ("suspend", "block"),
    "log": ("login",),
    "support": ("service",),
    "wishlist": ("favourite", "favorite", "bookmark"),
    "complaint": ("complain", "grievance"),
    "marketing": ("promotional",),
    # products and stores
    "store": ("showroom", "shop", "outlet", "storefront"),
    "student": ("university", "college", "school"),
    "gift": ("present",),
    "authentic": ("genuine", "original"),
    "defective": ("break", "damage", "faulty"),  # broken -> break
    "warranty": ("guarantee",),
    "bulk": ("wholesale",),
    "app": ("application",),
    "mobile": ("smartphone",),
    "bug": ("crash", "glitch", "error"),
    "launch": ("release",),
    "competitor": ("rival",),
    "eco": ("sustainable", "environmental"),
    "recycle": ("recyclable",),
    "exchange": ("swap",),
    # money
    "promo": ("coupon", "voucher"),
    "buy": ("purchase",),
    "refund": ("reimburse", "reimbursement"),
    "currency": ("pound", "euro", "dollar", "usd", "gbp", "eur", "cad"),
    "tax": ("vat",),
    "twice": ("double", "duplicate"),
    "reward": ("loyalty", "membership"),
    # British / American spelling
    "program": ("programme",),
    "color": ("colour",),
    "installment": ("instalment",),
    "authorize": ("authorise",),
    "personalize": ("personalise",),
}

SYNONYMS: dict[str, str] = {}
for _canonical, _variants in _GROUPS.items():
    for _variant in _variants:
        if _variant in SYNONYMS:
            raise ValueError(f"synonym {_variant!r} is mapped twice")
        SYNONYMS[_variant] = _canonical
