{
    "name": "Bispro Purchase Order Report",
    "summary": "Premium Big 4 style Purchase Order HTML/PDF/XLSX report for Bispro.vn",
    "description": """
Bispro Purchase Order Report
============================
- Purchase Order report layout with full borders and enterprise sections.
- View Purchase Order as web HTML.
- View Purchase Order directly as PDF.
- Export Purchase Order as XLSX with formatted tables.
- Brand-aligned colors and typography for Bispro.vn.
    """,
    "version": "19.0.1.0.11",
    "category": "Purchase",
    "author": "Bispro.vn",
    "website": "https://bispro.vn",
    "license": "LGPL-3",
    "depends": ["purchase", "web"],
    "data": [
        "report/paperformat.xml",
        "report/purchase_order_report_templates.xml",
        "report/purchase_order_report_actions.xml",
        "views/purchase_order_views.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
