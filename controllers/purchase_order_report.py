# -*- coding: utf-8 -*-

import io
import os
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path
from html import escape

from odoo import http, _
from odoo.http import request


class BisproPurchaseOrderReportController(http.Controller):
    """HTML/PDF/XLSX delivery endpoints for Bispro Purchase Order report."""

    def _get_po(self, po_id):
        po = request.env["purchase.order"].browse(int(po_id)).exists()
        if not po:
            return None
        # Odoo 18+ deprecates check_access_rights/check_access_rule.
        # Keep fallback for compatibility with older/customized builds.
        if hasattr(po, "check_access"):
            po.check_access("read")
        else:
            po.check_access_rights("read")
            po.check_access_rule("read")
        return po

    def _txt(self, value):
        if value in (False, None):
            return ""
        return escape(str(value))

    def _date(self, value):
        if not value:
            return ""
        try:
            return escape(value.strftime("%d/%m/%Y"))
        except Exception:
            return escape(str(value))

    def _money(self, amount, currency):
        symbol = ""
        position = "after"
        if currency:
            symbol = (currency.symbol if "symbol" in currency._fields else "") or (currency.name if "name" in currency._fields else "") or ""
            position = (currency.position if "position" in currency._fields else "after") or "after"
        try:
            text = "{:,.2f}".format(amount or 0.0)
        except Exception:
            text = str(amount or "")
        if position == "before":
            return escape("%s %s" % (symbol, text)).strip()
        return escape("%s %s" % (text, symbol)).strip()

    def _partner_address(self, partner):
        if not partner:
            return ""
        parts = []
        for field_name in ["street", "street2", "city", "state_id", "country_id"]:
            if field_name not in partner._fields:
                continue
            val = partner[field_name]
            if not val:
                continue
            if hasattr(val, "display_name"):
                val = val.display_name
            parts.append(str(val))
        return ", ".join(parts)

    def _field_name(self, record, field_name):
        """Return display/name for an optional field without raising if field is absent."""
        if not record or field_name not in record._fields:
            return ""
        value = record[field_name]
        if hasattr(value, "display_name"):
            return value.display_name or value.name or ""
        return value or ""

    def _line_values(self, line):
        if hasattr(line, "_bispro_line_report_values"):
            return line._bispro_line_report_values()
        return {
            "display_type": getattr(line, "display_type", False),
            "product_code": getattr(getattr(line, "product_id", False), "default_code", "") or "",
            "description": getattr(line, "name", "") or "",
            "uom": "",
            "qty": getattr(line, "product_qty", 0.0) or 0.0,
            "price_unit": getattr(line, "price_unit", 0.0) or 0.0,
            "taxes": ", ".join(line.taxes_id.mapped("name")) if hasattr(line, "taxes_id") else "",
            "subtotal": getattr(line, "price_subtotal", 0.0) or 0.0,
        }

    def _po_values(self, po):
        if hasattr(po, "_bispro_po_report_values"):
            return po._bispro_po_report_values()
        return {
            "name": po.name or "",
            "date_order": po.date_order if "date_order" in po._fields else False,
            "state": po.state if "state" in po._fields else "",
            "buyer": po.user_id.name if "user_id" in po._fields and po.user_id else "",
            "currency": po.currency_id if "currency_id" in po._fields else False,
            "currency_name": po.currency_id.name if "currency_id" in po._fields and po.currency_id else "",
            "payment_term": self._field_name(po, "payment_term_id"),
            "planned_date": po["date_planned"] if "date_planned" in po._fields else False,
            "incoterm": self._field_name(po, "incoterm_id"),
            "supplier_name": po.partner_id.display_name if po.partner_id else "",
            "supplier_address": self._partner_address(po.partner_id),
            "supplier_vat": po.partner_id.vat if po.partner_id else "",
            "supplier_phone": po.partner_id.phone if po.partner_id else "",
            "supplier_email": po.partner_id.email if po.partner_id else "",
            "company_name": po.company_id.name if po.company_id else "",
            "company_address": self._partner_address(po.company_id.partner_id),
            "company_vat": po.company_id.partner_id.vat if po.company_id else "",
            "company_phone": po.company_id.partner_id.phone if po.company_id else "",
            "company_email": po.company_id.partner_id.email if po.company_id else "",
            "amount_untaxed": po.amount_untaxed if "amount_untaxed" in po._fields else 0.0,
            "amount_tax": po.amount_tax if "amount_tax" in po._fields else 0.0,
            "amount_total": po.amount_total if "amount_total" in po._fields else 0.0,
            "notes": po.notes if "notes" in po._fields else "",
        }

    def _build_html(self, po):
        vals = self._po_values(po)
        currency = vals.get("currency") or po.currency_id
        logo_url = vals.get("logo_data_uri") or "/bispro_purchase_order_report/static/src/img/logo.png"
        rows = []
        line_no = 1
        order_lines = po.order_line if "order_line" in po._fields else []
        for line in order_lines:
            lv = self._line_values(line)
            if lv.get("display_type"):
                rows.append('<tr><td colspan="8" class="sub-title">%s</td></tr>' % self._txt(lv.get("description")))
                continue
            rows.append(
                """
                <tr>
                    <td class="center">{line_no}</td>
                    <td>{code}</td>
                    <td>{desc}</td>
                    <td class="center">{uom}</td>
                    <td class="right">{qty}</td>
                    <td class="right">{price}</td>
                    <td>{taxes}</td>
                    <td class="right">{subtotal}</td>
                </tr>
                """.format(
                    line_no=line_no,
                    code=self._txt(lv.get("product_code")),
                    desc=self._txt(lv.get("description")),
                    uom=self._txt(lv.get("uom")),
                    qty=self._txt(lv.get("qty")),
                    price=self._money(lv.get("price_unit"), currency),
                    taxes=self._txt(lv.get("taxes")),
                    subtotal=self._money(lv.get("subtotal"), currency),
                )
            )
            line_no += 1

        notes = vals.get("notes") or _(
            "Please deliver goods/services according to this Purchase Order, agreed commercial terms, applicable tax regulations, quality standards, and delivery schedule."
        )

        html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: #0F172A; font-family: Inter, Roboto, Arial, sans-serif; font-size: 11px; background: #F8FAFC; }}
.page {{ max-width: 980px; margin: 18px auto; padding: 16px; background: #FFF; box-shadow: 0 10px 28px rgba(15, 23, 42, .16); }}
.brand-strip {{ height: 7px; background: linear-gradient(90deg, #0F172A 0%, #1E3A8A 78%, #F59E0B 78%, #F59E0B 100%); }}
.header {{ border: 1px solid #0F172A; border-top: 0; display: table; width: 100%; }}
.header-left, .header-right {{ display: table-cell; vertical-align: middle; padding: 10px 12px; }}
.header-left {{ width: 58%; }}
.header-right {{ width: 42%; border-left: 1px solid #0F172A; text-align: right; }}
.logo {{ max-height: 44px; max-width: 190px; margin-bottom: 5px; }}
.company-title {{ font-family: Montserrat, Inter, Arial, sans-serif; font-weight: 700; font-size: 13px; color: #0F172A; }}
.muted {{ color: #64748B; }}
.doc-title {{ font-family: Montserrat, Inter, Arial, sans-serif; font-size: 24px; font-weight: 800; letter-spacing: 1px; color: #0F172A; margin-bottom: 5px; }}
.doc-no {{ display: inline-block; padding: 4px 9px; background: #1E3A8A; color: #FFF; font-weight: 700; border-radius: 2px; }}
table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
th, td {{ border: 1px solid #0F172A; padding: 5px 6px; vertical-align: top; word-wrap: break-word; }}
.section-title {{ background: #0F172A; color: #FFF; font-weight: 700; text-transform: uppercase; letter-spacing: .35px; }}
.sub-title {{ background: #1E3A8A; color: #FFF; font-weight: 700; text-transform: uppercase; }}
.label {{ width: 24%; background: #E2E8F0; font-weight: 700; color: #0F172A; }}
.value {{ background: #FFF; }}
.mt8 {{ margin-top: 8px; }}
.line-header th {{ background: #1E3A8A; color: #FFF; font-weight: 700; text-align: center; }}
.center {{ text-align: center; }}
.right {{ text-align: right; }}
.total-label {{ background: #E2E8F0; font-weight: 700; text-align: right; }}
.total-value {{ background: #E2E8F0; font-weight: 800; text-align: right; }}
.grand-total td {{ background: #0F172A; color: #FFF; font-size: 12px; font-weight: 800; }}
.gold-note {{ border-left: 5px solid #F59E0B; padding: 7px 9px; background: #fff8eb; border-top: 1px solid #F59E0B; border-right: 1px solid #F59E0B; border-bottom: 1px solid #F59E0B; }}
.signature td {{ height: 78px; text-align: center; font-weight: 700; }}
.sign-space {{ color: #64748B; font-weight: 400; padding-top: 40px; display: block; }}
.footer {{ margin-top: 8px; color: #64748B; text-align: center; font-size: 9px; }}
@media print {{ body {{ background: #FFF; }} .page {{ box-shadow: none; margin: 0; max-width: none; }} }}
</style>
</head>
<body>
<div class="page">
<div class="brand-strip"></div>
<div class="header">
<div class="header-left">
<img class="logo" src="{logo_url}" alt="Bispro.vn"/>
<div class="company-title">{company}</div>
<div class="muted">{company_address}</div>
<div class="muted">Tax ID: {company_vat}</div>
</div>
<div class="header-right">
<div class="doc-title">PURCHASE ORDER</div>
<div class="doc-no">{po_name}</div>
<div style="margin-top:6px;">Order Date: <strong>{order_date}</strong></div>
<div>Status: <strong>{state}</strong></div>
</div>
</div>

<table class="mt8">
<tr><td colspan="4" class="section-title">1. Document Control</td></tr>
<tr><td class="label">PO Number</td><td class="value">{po_name}</td><td class="label">Buyer</td><td class="value">{buyer}</td></tr>
<tr><td class="label">Currency</td><td class="value">{currency}</td><td class="label">Payment Terms</td><td class="value">{payment}</td></tr>
<tr><td class="label">Expected Arrival</td><td class="value">{planned}</td><td class="label">Incoterm</td><td class="value">{incoterm}</td></tr>
</table>

<table class="mt8">
<tr><td colspan="2" class="section-title">2. Supplier Information</td><td colspan="2" class="section-title">3. Ship To / Company Information</td></tr>
<tr><td class="label">Supplier</td><td class="value"><strong>{supplier}</strong></td><td class="label">Company</td><td class="value"><strong>{company}</strong></td></tr>
<tr><td class="label">Address</td><td class="value">{supplier_address}</td><td class="label">Address</td><td class="value">{company_address}</td></tr>
<tr><td class="label">Tax ID</td><td class="value">{supplier_vat}</td><td class="label">Tax ID</td><td class="value">{company_vat}</td></tr>
<tr><td class="label">Phone / Email</td><td class="value">{supplier_phone} / {supplier_email}</td><td class="label">Phone / Email</td><td class="value">{company_phone} / {company_email}</td></tr>
</table>

<table class="mt8">
<thead class="line-header"><tr><th style="width:5%;">No.</th><th style="width:13%;">Product Code</th><th style="width:34%;">Description</th><th style="width:8%;">UoM</th><th style="width:9%;">Qty</th><th style="width:11%;">Unit Price</th><th style="width:9%;">Taxes</th><th style="width:11%;">Subtotal</th></tr></thead>
<tbody>
{line_rows}
<tr><td colspan="7" class="total-label">Untaxed Amount</td><td class="total-value">{untaxed}</td></tr>
<tr><td colspan="7" class="total-label">Taxes</td><td class="total-value">{tax}</td></tr>
<tr class="grand-total"><td colspan="7" class="right">TOTAL</td><td class="right">{total}</td></tr>
</tbody>
</table>

<table class="mt8"><tr><td class="section-title">4. Terms, Conditions &amp; Notes</td></tr><tr><td><div class="gold-note">{notes}</div></td></tr></table>
<table class="mt8 signature"><tr><td>Prepared by<span class="sign-space">Signature / Date</span></td><td>Reviewed by<span class="sign-space">Signature / Date</span></td><td>Approved by<span class="sign-space">Signature / Date</span></td><td>Supplier Confirmation<span class="sign-space">Signature / Date</span></td></tr></table>
<div class="footer">This Purchase Order is system-generated from Bispro.vn. Please verify PO number, supplier, delivery schedule, tax and commercial terms before execution.</div>
</div>
</body>
</html>""".format(
            title=self._txt(vals.get("name") or "Purchase Order"),
            logo_url=logo_url,
            company=self._txt(vals.get("company_name")),
            company_address=self._txt(vals.get("company_address")),
            company_vat=self._txt(vals.get("company_vat")),
            company_phone=self._txt(vals.get("company_phone")),
            company_email=self._txt(vals.get("company_email")),
            po_name=self._txt(vals.get("name")),
            order_date=self._date(vals.get("date_order")),
            state=self._txt(vals.get("state")),
            buyer=self._txt(vals.get("buyer")),
            currency=self._txt(vals.get("currency_name")),
            payment=self._txt(vals.get("payment_term")),
            planned=self._date(vals.get("planned_date")),
            incoterm=self._txt(vals.get("incoterm")),
            supplier=self._txt(vals.get("supplier_name")),
            supplier_address=self._txt(vals.get("supplier_address")),
            supplier_vat=self._txt(vals.get("supplier_vat")),
            supplier_phone=self._txt(vals.get("supplier_phone")),
            supplier_email=self._txt(vals.get("supplier_email")),
            line_rows="".join(rows) if rows else '<tr><td colspan="8" class="center muted">No order lines</td></tr>',
            untaxed=self._money(vals.get("amount_untaxed"), currency),
            tax=self._money(vals.get("amount_tax"), currency),
            total=self._money(vals.get("amount_total"), currency),
            notes=self._txt(notes),
        )
        return html

    @http.route("/bispro/po/<int:po_id>/html", type="http", auth="user", website=False)
    def po_html(self, po_id, **kwargs):
        po = self._get_po(po_id)
        if not po:
            return request.not_found()
        return request.make_response(
            self._build_html(po),
            headers=[("Content-Type", "text/html; charset=utf-8")],
        )

    def _find_wkhtmltopdf(self):
        """Find wkhtmltopdf binary used to generate the direct PDF route.

        Odoo's internal QWeb PDF pipeline on this server renders UTF-8 text as
        mojibake. The direct Bispro PDF route therefore renders the same HTML
        layout through wkhtmltopdf with --encoding utf-8 explicitly.
        """
        candidates = [
            shutil.which("wkhtmltopdf"),
            "/usr/local/bin/wkhtmltopdf",
            "/usr/bin/wkhtmltopdf",
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return False

    @http.route("/bispro/po/<int:po_id>/pdf", type="http", auth="user", website=False)
    def po_pdf(self, po_id, **kwargs):
        po = self._get_po(po_id)
        if not po:
            return request.not_found()

        wkhtmltopdf = self._find_wkhtmltopdf()
        if not wkhtmltopdf:
            return request.make_response(
                _("wkhtmltopdf was not found on the Odoo server. Please install wkhtmltopdf to export this PDF."),
                headers=[("Content-Type", "text/plain; charset=utf-8")],
                status=500,
            )

        html_content = self._build_html(po)
        fd, html_path = tempfile.mkstemp(prefix="bispro_po_", suffix=".html")
        os.close(fd)
        try:
            Path(html_path).write_text(html_content, encoding="utf-8")
            cmd = [
                wkhtmltopdf,
                "--encoding", "utf-8",
                "--page-size", "A4",
                "--orientation", "Portrait",
                "--margin-top", "8mm",
                "--margin-right", "8mm",
                "--margin-bottom", "8mm",
                "--margin-left", "8mm",
                "--disable-smart-shrinking",
                "--print-media-type",
                html_path,
                "-",
            ]
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
            if proc.returncode != 0 or not proc.stdout:
                message = proc.stderr.decode("utf-8", errors="replace") or _("wkhtmltopdf failed to generate PDF.")
                return request.make_response(
                    message,
                    headers=[("Content-Type", "text/plain; charset=utf-8")],
                    status=500,
                )
            filename = "%s.pdf" % (po.name or "purchase_order")
            return request.make_response(
                proc.stdout,
                headers=[
                    ("Content-Type", "application/pdf"),
                    ("Content-Disposition", "inline; filename=%s" % filename),
                ],
            )
        finally:
            try:
                os.unlink(html_path)
            except Exception:
                pass

    @http.route("/bispro/po/<int:po_id>/xlsx", type="http", auth="user", website=False)
    def po_xlsx(self, po_id, **kwargs):
        """Export PO to XLSX using the same structure as the HTML layout.

        This implementation intentionally avoids overlapping merge ranges and
        risky writes inside merged cells, because those are common causes of
        Odoo "Internal Server Error" when xlsxwriter closes the workbook.
        """
        po = self._get_po(po_id)
        if not po:
            return request.not_found()
        try:
            import xlsxwriter
        except ImportError:
            return request.make_response(
                _("Python package xlsxwriter is required. Install it on the Odoo server: pip install xlsxwriter"),
                headers=[("Content-Type", "text/plain; charset=utf-8")],
                status=500,
            )

        try:
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            sheet = workbook.add_worksheet("Purchase Order")

            vals = self._po_values(po)
            currency = vals.get("currency") or (po.currency_id if "currency_id" in po._fields else False)
            symbol = ""
            try:
                symbol = (currency.symbol or currency.name or "") if currency else ""
            except Exception:
                symbol = ""
            safe_symbol = str(symbol).replace('"', '').replace('\\', '')
            money_format = '#,##0.00' + ((' "' + safe_symbol + '"') if safe_symbol else '')

            navy = "#0F172A"
            blue = "#1E3A8A"
            gold = "#F59E0B"
            slate = "#64748B"
            light = "#E2E8F0"
            white = "#FFFFFF"
            pale_note = "#FFFBEB"

            sheet.set_portrait()
            sheet.set_paper(9)
            sheet.fit_to_pages(1, 0)
            sheet.set_margins(0.20, 0.20, 0.22, 0.22)
            sheet.hide_gridlines(2)
            sheet.set_footer('&CThis Purchase Order is system-generated from Bispro.vn. Page &P of &N')

            widths = [6, 16, 40, 10, 10, 15, 14, 17]
            for idx, width in enumerate(widths):
                sheet.set_column(idx, idx, width)

            def add_fmt(props=None):
                base = {
                    "font_name": "Arial",
                    "font_size": 9,
                    "font_color": navy,
                    "border": 1,
                    "border_color": navy,
                    "valign": "vcenter",
                }
                if props:
                    base.update(props)
                return workbook.add_format(base)

            fmt_strip = workbook.add_format({"bg_color": navy})
            fmt_gold = workbook.add_format({"bg_color": gold})
            fmt_plain = workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": navy})
            fmt_company = workbook.add_format({"font_name": "Arial", "bold": True, "font_size": 11, "font_color": navy})
            fmt_muted = workbook.add_format({"font_name": "Arial", "font_size": 8, "font_color": slate})
            fmt_title = workbook.add_format({"font_name": "Arial", "bold": True, "font_size": 22, "font_color": navy, "align": "right", "valign": "vcenter"})
            fmt_doc_no = workbook.add_format({"font_name": "Arial", "bold": True, "font_size": 10, "font_color": white, "bg_color": blue, "align": "center", "valign": "vcenter"})
            fmt_right_text = workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": navy, "align": "right", "valign": "vcenter"})
            fmt_header_box = add_fmt({"bg_color": white, "text_wrap": True, "valign": "top"})
            fmt_section = add_fmt({"bold": True, "font_color": white, "bg_color": navy, "align": "left"})
            fmt_label = add_fmt({"bold": True, "bg_color": light, "text_wrap": True})
            fmt_value = add_fmt({"bg_color": white, "text_wrap": True})
            fmt_value_bold = add_fmt({"bold": True, "bg_color": white, "text_wrap": True})
            fmt_line_header = add_fmt({"bold": True, "font_color": white, "bg_color": blue, "align": "center", "text_wrap": True})
            fmt_center = add_fmt({"align": "center", "valign": "top"})
            fmt_text = add_fmt({"text_wrap": True, "valign": "top"})
            fmt_number = add_fmt({"num_format": "#,##0.00", "align": "right", "valign": "top"})
            fmt_money = add_fmt({"num_format": money_format, "align": "right", "valign": "top"})
            fmt_total_label = add_fmt({"bold": True, "bg_color": light, "align": "right"})
            fmt_total_value = add_fmt({"bold": True, "bg_color": light, "num_format": money_format, "align": "right"})
            fmt_grand_label = add_fmt({"bold": True, "font_color": white, "bg_color": navy, "align": "right", "font_size": 10})
            fmt_grand_total = add_fmt({"bold": True, "font_color": white, "bg_color": navy, "num_format": money_format, "align": "right", "font_size": 10})
            fmt_note = add_fmt({"bg_color": pale_note, "border_color": gold, "text_wrap": True, "valign": "top"})
            fmt_sign_head = add_fmt({"bold": True, "align": "center", "valign": "top"})
            fmt_sign = add_fmt({"font_color": slate, "align": "center", "valign": "bottom"})
            fmt_footer = workbook.add_format({"font_name": "Arial", "font_size": 8, "font_color": slate, "align": "center"})

            def dt(value):
                try:
                    return value.strftime("%d/%m/%Y") if value else ""
                except Exception:
                    return str(value or "")

            def text(value):
                if value in (False, None):
                    return ""
                return str(value)

            # Brand strip
            sheet.set_row(0, 7)
            sheet.merge_range(0, 0, 0, 6, "", fmt_strip)
            sheet.write(0, 7, "", fmt_gold)

            # Header block.
            # Important: xlsxwriter forbids writing or merging inside a previously
            # merged range. Do not create a parent merged header area; format the
            # cells first, then merge only the final visible text ranges.
            row = 1
            for r in range(row, row + 7):
                sheet.set_row(r, 18)
                for c in range(0, 8):
                    sheet.write_blank(r, c, None, fmt_header_box)

            logo_path = str(Path(__file__).resolve().parents[1] / "static" / "src" / "img" / "logo.png")
            if Path(logo_path).is_file():
                try:
                    sheet.insert_image(row, 0, logo_path, {"x_scale": 0.20, "y_scale": 0.20, "x_offset": 8, "y_offset": 5})
                except Exception:
                    pass

            # Left company info. Avoid merge ranges here so image and text never overlap.
            sheet.write(row + 2, 0, text(vals.get("company_name")), fmt_company)
            sheet.write(row + 3, 0, text(vals.get("company_address")), fmt_muted)
            sheet.write(row + 4, 0, "Tax ID: %s" % text(vals.get("company_vat")), fmt_muted)

            # Right PO info: independent merge ranges only.
            sheet.merge_range(row, 4, row, 7, "PURCHASE ORDER", fmt_title)
            sheet.merge_range(row + 1, 6, row + 1, 7, text(vals.get("name")), fmt_doc_no)
            sheet.merge_range(row + 2, 5, row + 2, 7, "Order Date: %s" % dt(vals.get("date_order")), fmt_right_text)
            sheet.merge_range(row + 3, 5, row + 3, 7, "Status: %s" % text(vals.get("state")), fmt_right_text)
            row += 7

            # 1. Document Control
            sheet.merge_range(row, 0, row, 7, "1. DOCUMENT CONTROL", fmt_section); row += 1
            sheet.write(row, 0, "PO Number", fmt_label); sheet.merge_range(row, 1, row, 3, text(vals.get("name")), fmt_value)
            sheet.write(row, 4, "Buyer", fmt_label); sheet.merge_range(row, 5, row, 7, text(vals.get("buyer")), fmt_value); row += 1
            sheet.write(row, 0, "Currency", fmt_label); sheet.merge_range(row, 1, row, 3, text(vals.get("currency_name")), fmt_value)
            sheet.write(row, 4, "Payment Terms", fmt_label); sheet.merge_range(row, 5, row, 7, text(vals.get("payment_term")), fmt_value); row += 1
            sheet.write(row, 0, "Expected Arrival", fmt_label); sheet.merge_range(row, 1, row, 3, dt(vals.get("planned_date")), fmt_value)
            sheet.write(row, 4, "Incoterm", fmt_label); sheet.merge_range(row, 5, row, 7, text(vals.get("incoterm")), fmt_value); row += 2

            # 2/3 Supplier and company
            sheet.merge_range(row, 0, row, 3, "2. SUPPLIER INFORMATION", fmt_section)
            sheet.merge_range(row, 4, row, 7, "3. SHIP TO / COMPANY INFORMATION", fmt_section); row += 1
            sheet.write(row, 0, "Supplier", fmt_label); sheet.merge_range(row, 1, row, 3, text(vals.get("supplier_name")), fmt_value_bold)
            sheet.write(row, 4, "Company", fmt_label); sheet.merge_range(row, 5, row, 7, text(vals.get("company_name")), fmt_value_bold); row += 1
            sheet.write(row, 0, "Address", fmt_label); sheet.merge_range(row, 1, row, 3, text(vals.get("supplier_address")), fmt_value)
            sheet.write(row, 4, "Address", fmt_label); sheet.merge_range(row, 5, row, 7, text(vals.get("company_address")), fmt_value); row += 1
            sheet.write(row, 0, "Tax ID", fmt_label); sheet.merge_range(row, 1, row, 3, text(vals.get("supplier_vat")), fmt_value)
            sheet.write(row, 4, "Tax ID", fmt_label); sheet.merge_range(row, 5, row, 7, text(vals.get("company_vat")), fmt_value); row += 1
            sheet.write(row, 0, "Phone / Email", fmt_label); sheet.merge_range(row, 1, row, 3, "%s / %s" % (text(vals.get("supplier_phone")), text(vals.get("supplier_email"))), fmt_value)
            sheet.write(row, 4, "Phone / Email", fmt_label); sheet.merge_range(row, 5, row, 7, "%s / %s" % (text(vals.get("company_phone")), text(vals.get("company_email"))), fmt_value); row += 2

            headers = ["No.", "Product Code", "Description", "UoM", "Qty", "Unit Price", "Taxes", "Subtotal"]
            for col, header in enumerate(headers):
                sheet.write(row, col, header, fmt_line_header)
            line_header_row = row
            row += 1

            line_no = 1
            order_lines = po.order_line if "order_line" in po._fields else []
            for line in order_lines:
                lv = self._line_values(line)
                if lv.get("display_type"):
                    sheet.merge_range(row, 0, row, 7, text(lv.get("description")), fmt_section)
                    row += 1
                    continue
                sheet.write_number(row, 0, line_no, fmt_center)
                sheet.write(row, 1, text(lv.get("product_code")), fmt_text)
                sheet.write(row, 2, text(lv.get("description")), fmt_text)
                sheet.write(row, 3, text(lv.get("uom")), fmt_center)
                sheet.write_number(row, 4, float(lv.get("qty") or 0.0), fmt_number)
                sheet.write_number(row, 5, float(lv.get("price_unit") or 0.0), fmt_money)
                sheet.write(row, 6, text(lv.get("taxes")), fmt_text)
                sheet.write_number(row, 7, float(lv.get("subtotal") or 0.0), fmt_money)
                sheet.set_row(row, 28)
                line_no += 1
                row += 1
            if line_no == 1:
                sheet.merge_range(row, 0, row, 7, "No order lines", fmt_center)
                row += 1

            sheet.merge_range(row, 0, row, 6, "Untaxed Amount", fmt_total_label)
            sheet.write_number(row, 7, float(vals.get("amount_untaxed") or 0.0), fmt_total_value); row += 1
            sheet.merge_range(row, 0, row, 6, "Taxes", fmt_total_label)
            sheet.write_number(row, 7, float(vals.get("amount_tax") or 0.0), fmt_total_value); row += 1
            sheet.merge_range(row, 0, row, 6, "TOTAL", fmt_grand_label)
            sheet.write_number(row, 7, float(vals.get("amount_total") or 0.0), fmt_grand_total); row += 2

            sheet.merge_range(row, 0, row, 7, "4. TERMS, CONDITIONS & NOTES", fmt_section); row += 1
            notes = vals.get("notes") or "Please deliver goods/services according to this Purchase Order, agreed commercial terms, applicable tax regulations, quality standards, and delivery schedule."
            sheet.merge_range(row, 0, row + 1, 7, text(notes), fmt_note); row += 3

            for start, end, label in [(0, 1, "Prepared by"), (2, 3, "Reviewed by"), (4, 5, "Approved by"), (6, 7, "Supplier Confirmation")]:
                sheet.merge_range(row, start, row, end, label, fmt_sign_head)
                sheet.merge_range(row + 1, start, row + 3, end, "Signature / Date", fmt_sign)
            row += 4
            sheet.merge_range(row, 0, row, 7, "This Purchase Order is system-generated from Bispro.vn. Please verify PO number, supplier, delivery schedule, tax and commercial terms before execution.", fmt_footer)

            sheet.freeze_panes(line_header_row + 1, 0)
            try:
                sheet.repeat_rows(line_header_row, line_header_row)
            except Exception:
                pass
            sheet.print_area(0, 0, row, 7)
            workbook.close()
            output.seek(0)
            filename = "%s.xlsx" % (vals.get("name") or "purchase_order")
            return request.make_response(
                output.read(),
                headers=[
                    ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ("Content-Disposition", "attachment; filename=%s" % filename),
                ],
            )
        except Exception:
            try:
                workbook.close()
            except Exception:
                pass
            return request.make_response(
                "Bispro Excel export failed:\n%s" % traceback.format_exc(),
                headers=[("Content-Type", "text/plain; charset=utf-8")],
                status=500,
            )
