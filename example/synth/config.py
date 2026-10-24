"""Fixed settings for the synthetic Northwind Pharmacy extracts.

Every name, number and rule here is invented. VAT rates, prices and pack
sizes are illustrative only. They are not tax advice and not any real
chain's master data.
"""

from datetime import date, datetime, timedelta

SEED = "20260915"
CHAIN_NAME = "Northwind Pharmacy"

# The nightly extract ran on the morning of the snapshot date, local time
# (Asia/Ho_Chi_Minh, UTC+7). Sales cover six months up to "yesterday".
SNAPSHOT_DATE = date(2026, 9, 15)
EXTRACT_AT = datetime(2026, 9, 15, 6, 0)
UTC_OFFSET = timedelta(hours=7)
SALES_START = date(2026, 3, 15)
SALES_END = date(2026, 9, 14)

# Newly opened stores whose POS sync runs behind the rest of the chain.
NEW_STORE_OPENINGS = (date(2026, 8, 18), date(2026, 9, 1))
POS_SYNC_LAG_DAYS = 3

DISTRICTS = (
    ("D01", "Riverside"),
    ("D02", "Old Quarter"),
    ("D03", "Airport"),
    ("D04", "Industrial Park"),
    ("D05", "New Town"),
)
STORES_PER_DISTRICT = 6
STORES_24H = 3
# Older stores run POS vendor A. The chain moved to vendor B for later
# openings, so the newest stores (including the lagging ones) are on B.
VENDOR_B_STORES = 12

# Pack shapes. A tablet SKU is stocked in boxes and sold by box, strip or
# single tablet. Bottles and pieces are received in cartons or boxes.
FORM_TABLET = "TABLET"
FORM_BOTTLE = "BOTTLE"
FORM_PIECE = "PIECE"
TABLETS_PER_STRIP = 10
BOTTLES_PER_CARTON = 24

# (code, name, VAT percent). Each category keeps the first N products below.
CATEGORIES = (
    ("PAIN", "Pain and fever", 5),
    ("ANTI", "Antibiotics", 5),
    ("RESP", "Cough, cold and allergy", 5),
    ("DIGE", "Digestive health", 5),
    ("VITA", "Vitamins and supplements", 10),
    ("CARE", "Personal care and devices", 10),
)
SKUS_PER_CATEGORY = {"PAIN": 30, "ANTI": 25, "RESP": 25, "DIGE": 20, "VITA": 30, "CARE": 20}

# Price per base unit, VND including VAT.
TABLET_PRICE_RANGE = {
    "PAIN": (300, 2_500),
    "ANTI": (1_500, 12_000),
    "RESP": (600, 5_000),
    "DIGE": (800, 6_000),
    "VITA": (700, 6_500),
}
BOTTLE_PRICE_RANGE = (28_000, 185_000)

# Generic product names only, never a brand. Tablet entries expand into a
# "Box 10x10" and a "Box 3x10" pack, so each one yields two SKUs.
TABLET_PRODUCTS = {
    "PAIN": (
        "Paracetamol 325mg", "Paracetamol 500mg", "Paracetamol 650mg",
        "Ibuprofen 200mg", "Ibuprofen 400mg", "Diclofenac 50mg",
        "Naproxen 250mg", "Naproxen 500mg", "Meloxicam 7.5mg",
        "Meloxicam 15mg", "Aspirin 81mg", "Celecoxib 100mg",
        "Celecoxib 200mg", "Etodolac 200mg", "Piroxicam 20mg",
    ),
    "ANTI": (
        "Amoxicillin 250mg", "Amoxicillin 500mg", "Cefuroxime 250mg",
        "Cefuroxime 500mg", "Azithromycin 250mg", "Azithromycin 500mg",
        "Cefixime 200mg", "Ciprofloxacin 500mg", "Doxycycline 100mg",
        "Clarithromycin 500mg", "Cephalexin 500mg", "Metronidazole 250mg",
        "Levofloxacin 500mg",
    ),
    "RESP": (
        "Cetirizine 10mg", "Loratadine 10mg", "Fexofenadine 180mg",
        "Bromhexine 8mg", "Acetylcysteine 200mg", "Dextromethorphan 15mg",
    ),
    "DIGE": (
        "Omeprazole 20mg", "Omeprazole 40mg", "Esomeprazole 20mg",
        "Esomeprazole 40mg", "Pantoprazole 40mg", "Domperidone 10mg",
        "Loperamide 2mg", "Simethicone 80mg", "Mebeverine 135mg",
        "Famotidine 20mg",
    ),
    "VITA": (
        "Vitamin C 500mg", "Vitamin C 1000mg", "Vitamin D3 1000IU",
        "Vitamin B complex", "Calcium carbonate 500mg", "Zinc 15mg",
        "Iron and folic acid", "Magnesium and B6", "Omega-3 1000mg",
        "Multivitamin adult", "Multivitamin senior", "Vitamin E 400IU",
    ),
}
TABLET_PACKS = (("Box 10x10", 10), ("Box 3x10", 3))  # (label, strips per box)

BOTTLE_PRODUCTS = {
    "RESP": (
        "Ambroxol syrup 60ml", "Ambroxol syrup 100ml", "Guaifenesin syrup 100ml",
        "Guaifenesin syrup 200ml", "Pediatric paracetamol syrup 60ml",
        "Pediatric paracetamol syrup 100ml", "Saline nasal spray 15ml",
        "Saline nasal spray 70ml", "Xylometazoline nasal spray 10ml",
        "Honey lemon cough syrup 125ml", "Carbocisteine syrup 100ml",
        "Chlorpheniramine syrup 60ml", "Dextromethorphan syrup 100ml",
    ),
    "VITA": (
        "Kids multivitamin syrup 100ml", "Vitamin D3 drops 10ml",
        "Fish oil liquid 150ml", "Calcium syrup 100ml", "Lysine syrup 100ml",
        "Multivitamin gummies bottle 60s",
    ),
}

# (name, pieces per box, price per piece in VND including VAT)
PIECE_PRODUCTS = {
    "CARE": (
        ("Digital thermometer", 10, 95_000),
        ("Surgical face mask", 50, 2_000),
        ("Hand sanitizer gel 500ml", 12, 89_000),
        ("Povidone iodine solution 100ml", 20, 32_000),
        ("Elastic bandage roll", 12, 28_000),
        ("Adhesive plaster", 100, 1_000),
        ("Upper arm blood pressure monitor", 4, 890_000),
        ("Blood glucose test strip", 50, 9_500),
        ("Cotton wool 100g", 20, 24_000),
        ("Nitrile examination glove", 100, 2_500),
        ("Pregnancy test cassette", 20, 22_000),
        ("Artificial tears eye drops 10ml", 20, 45_000),
        ("Contact lens solution 120ml", 12, 78_000),
        ("Sunscreen lotion 50ml", 12, 165_000),
        ("Moisturizing cream 100g", 12, 118_000),
        ("Sensitive toothpaste 100g", 24, 52_000),
        ("Antiseptic mouthwash 250ml", 12, 64_000),
        ("Elastic knee support", 10, 135_000),
        ("Compressor nebulizer", 2, 1_250_000),
        ("Weekly pill organizer", 20, 38_000),
    ),
}

# A master data cleanup renamed a few SKUs mid-period. The ERP extract only
# keeps the current name; vendor B receipts print the name valid at the time.
RENAME_ON = date(2026, 6, 1)
RENAMES = {
    "Paracetamol 500mg (Box 10x10)": "Paracetamol 500mg tablet (Box 10x10)",
    "Vitamin C 1000mg (Box 3x10)": "Ascorbic acid 1000mg (Box 3x10)",
    "Saline nasal spray 70ml": "Sodium chloride 0.9% nasal spray 70ml",
}
