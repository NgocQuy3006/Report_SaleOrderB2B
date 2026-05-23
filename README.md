# Bispro Purchase Order Report for Odoo 19CE

Version: 19.0.1.0.7

This module provides a synchronized Purchase Order document layout across:
- Web HTML preview
- Inline PDF preview
- XLSX export

Version 1.0.7 standardizes PDF and Excel to follow the approved HTML layout: same section order, labels, table structure, Bispro.vn color palette, border style, totals, notes and signature blocks.

## Dependency

For Excel export:

```bash
pip install xlsxwriter
```

## Update

```bash
cd /opt/odoo19ce/custom-addons
sudo rm -rf bispro_purchase_order_report
sudo unzip bispro_purchase_order_report_v19_1_0_6_html_aligned_pdf_excel.zip
sudo chown -R odoo19ce:odoo19ce bispro_purchase_order_report
sudo systemctl restart odoo19ce
```

Then upgrade the app in Odoo.


## 19.0.1.0.9
- Fix Vietnamese font/encoding in QWeb PDF by rendering dynamic PDF text as ASCII-safe numeric HTML entities.
- Force UTF-8 meta and DejaVu Sans font stack for wkhtmltopdf.
- Keep HTML-aligned PDF/Excel layout and Odoo 19CE field-safe logic.


## 19.0.1.0.9
- Force PDF template to use Arial/Helvetica only for Vietnamese rendering.
- Keep numeric HTML entity rendering for dynamic PDF text.
- Excel already uses Arial.
