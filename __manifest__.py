{
    "name": "Bispro Sale Order Report",
    "summary": "Premium Big 4 style Sale Order HTML/PDF/XLSX report for Bispro.vn",
    "description": """
Bispro Sale Order Report
========================
- Sale Order report layout with full borders and enterprise sections.
- View Sale Order as web HTML.
- View Sale Order directly as PDF.
- Export Sale Order as XLSX with formatted tables.
- Brand-aligned colors and typography for Bispro.vn.
    """,

    "version": "19.0.1.0.11",
    "category": "Sales",
    "author": "Bispro.vn",
    "website": "https://bispro.vn",
    "license": "LGPL-3",

    "depends": [
        "sale",
        "web"
    ],

    "data": [
        "reports/paperformat.xml",
        "reports/sale_order_report_templates.xml",
        "reports/sale_order_report_actions.xml",
        "views/sale_order_views.xml"
    ],

    "assets": {},

    "installable": True,
    "application": False,
    "auto_install": False
}