# -*- coding: utf-8 -*-

import base64
import html
from pathlib import Path

from markupsafe import Markup

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # -------------------------------------------------------------------------
    # Safe field helpers for Odoo 19CE/custom builds
    # -------------------------------------------------------------------------
    def _bispro_has_field(self, field_name):
        self.ensure_one()
        return field_name in self._fields

    def _bispro_field_value(self, field_names, default=False):
        """Read the first existing field from a candidate list safely."""
        self.ensure_one()
        if isinstance(field_names, str):
            field_names = [field_names]
        for field_name in field_names:
            if field_name in self._fields:
                return self[field_name]
        return default

    def _bispro_name(self, value):
        if not value:
            return ""
        if hasattr(value, "display_name"):
            return value.display_name or ""
        return str(value)



    def _bispro_pdf_text(self, value):
        """Return ASCII-only HTML-safe text for wkhtmltopdf.

        Some wkhtmltopdf builds used with Odoo 19 can mis-detect UTF-8 as
        Latin-1 when rendering QWeb PDF. The PDF template now forces Arial and
        this helper keeps dynamic text as numeric HTML entities so Vietnamese
        text is preserved in the final PDF.
        """
        if value in (None, False):
            return Markup("")
        text = html.escape(str(value), quote=True)
        safe = []
        for ch in text:
            if ord(ch) > 127:
                safe.append("&#%d;" % ord(ch))
            else:
                safe.append(ch)
        return Markup("".join(safe))

    def _bispro_money_display(self, amount, currency=False):
        symbol = ""
        position = "after"
        if currency:
            try:
                symbol = currency.symbol or currency.name or ""
                position = currency.position or "after"
            except Exception:
                symbol = ""
        try:
            amount_text = "{:,.2f}".format(amount or 0.0)
        except Exception:
            amount_text = str(amount or "")
        if symbol and position == "before":
            return "%s %s" % (symbol, amount_text)
        if symbol:
            return "%s %s" % (amount_text, symbol)
        return amount_text

    def _bispro_partner_address(self, partner):
        if not partner:
            return ""
        parts = []
        for field_name in ["street", "street2", "city", "state_id", "country_id"]:
            if field_name not in partner._fields:
                continue
            value = partner[field_name]
            if not value:
                continue
            if hasattr(value, "display_name"):
                value = value.display_name
            parts.append(str(value))
        return ", ".join(parts)


    def _bispro_logo_data_uri(self):
        """Return embedded logo data URI for wkhtmltopdf-safe PDF rendering."""
        try:
            logo_path = Path(__file__).resolve().parents[1] / "static" / "src" / "img" / "logo.png"
            if logo_path.exists():
                encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
                return "data:image/png;base64,%s" % encoded
        except Exception:
            pass
        return ""

    def _bispro_po_report_values(self):
        """Return safe values for HTML/PDF/XLSX PO report.

        This avoids hard failures when an Odoo 19CE/customized build renames or
        removes optional fields such as product_uom/product_uom_id,
        date_planned, incoterm_id, payment_term_id, notes, etc.
        """
        self.ensure_one()
        po = self
        company_partner = po.company_id.partner_id if po.company_id else False
        supplier = po.partner_id
        state_label = po.state or ""
        if "state" in po._fields and getattr(po._fields["state"], "selection", None):
            try:
                state_label = dict(po._fields["state"].selection).get(po.state, po.state or "")
            except Exception:
                state_label = po.state or ""

        payment_term = po._bispro_field_value(["payment_term_id", "payment_term"], False)
        planned = po._bispro_field_value(["date_planned", "effective_date", "date_approve"], False)
        incoterm = po._bispro_field_value(["incoterm_id", "incoterm"], False)
        notes = po._bispro_field_value(["notes", "note"], "") or ""

        return {
            "logo_data_uri": po._bispro_logo_data_uri(),
            "name": po.name or "",
            "date_order": po.date_order if "date_order" in po._fields else False,
            "state": state_label,
            "buyer": po.user_id.name if "user_id" in po._fields and po.user_id else "",
            "currency": po.currency_id if "currency_id" in po._fields else False,
            "currency_name": po.currency_id.name if "currency_id" in po._fields and po.currency_id else "",
            "payment_term": po._bispro_name(payment_term),
            "planned_date": planned,
            "incoterm": po._bispro_name(incoterm),
            "supplier_name": supplier.display_name if supplier else "",
            "supplier_address": po._bispro_partner_address(supplier),
            "supplier_vat": supplier.vat if supplier and "vat" in supplier._fields else "",
            "supplier_phone": supplier.phone if supplier and "phone" in supplier._fields else "",
            "supplier_email": supplier.email if supplier and "email" in supplier._fields else "",
            "company_name": po.company_id.name if po.company_id else "",
            "company_address": po._bispro_partner_address(company_partner),
            "company_vat": company_partner.vat if company_partner and "vat" in company_partner._fields else "",
            "company_phone": company_partner.phone if company_partner and "phone" in company_partner._fields else "",
            "company_email": (
                po.company_id.email if po.company_id and "email" in po.company_id._fields and po.company_id.email
                else company_partner.email if company_partner and "email" in company_partner._fields else ""
            ),
            "amount_untaxed": po.amount_untaxed if "amount_untaxed" in po._fields else 0.0,
            "amount_tax": po.amount_tax if "amount_tax" in po._fields else 0.0,
            "amount_total": po.amount_total if "amount_total" in po._fields else 0.0,
            "amount_untaxed_display": po._bispro_money_display(po.amount_untaxed if "amount_untaxed" in po._fields else 0.0, po.currency_id if "currency_id" in po._fields else False),
            "amount_tax_display": po._bispro_money_display(po.amount_tax if "amount_tax" in po._fields else 0.0, po.currency_id if "currency_id" in po._fields else False),
            "amount_total_display": po._bispro_money_display(po.amount_total if "amount_total" in po._fields else 0.0, po.currency_id if "currency_id" in po._fields else False),
            "notes": notes,
        }

    def action_bispro_po_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "bispro_purchase_order_report.action_report_bispro_purchase_order"
        ).report_action(self)

    def action_bispro_po_view_html(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/bispro/po/%s/html" % self.id,
            "target": "new",
        }

    def action_bispro_po_view_pdf(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/bispro/po/%s/pdf" % self.id,
            "target": "new",
        }

    def action_bispro_po_export_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/bispro/po/%s/xlsx" % self.id,
            "target": "self",
        }


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _bispro_line_field_value(self, field_names, default=False):
        self.ensure_one()
        if isinstance(field_names, str):
            field_names = [field_names]
        for field_name in field_names:
            if field_name in self._fields:
                return self[field_name]
        return default

    def _bispro_line_money_display(self, amount):
        self.ensure_one()
        currency = False
        try:
            currency = self.order_id.currency_id
        except Exception:
            currency = False
        symbol = ""
        position = "after"
        if currency:
            try:
                symbol = currency.symbol or currency.name or ""
                position = currency.position or "after"
            except Exception:
                symbol = ""
        try:
            amount_text = "{:,.2f}".format(amount or 0.0)
        except Exception:
            amount_text = str(amount or "")
        if symbol and position == "before":
            return "%s %s" % (symbol, amount_text)
        if symbol:
            return "%s %s" % (amount_text, symbol)
        return amount_text

    def _bispro_line_report_values(self):
        self.ensure_one()
        line = self
        product = line.product_id if "product_id" in line._fields else False
        uom = line._bispro_line_field_value(["product_uom_id", "product_uom", "product_uom_category_id"], False)
        taxes = line._bispro_line_field_value(["taxes_id", "tax_id"], False)
        qty = line._bispro_line_field_value(["product_qty", "product_uom_qty", "quantity", "qty"], 0.0)
        price_unit = line._bispro_line_field_value(["price_unit"], 0.0)
        subtotal = line._bispro_line_field_value(["price_subtotal", "price_total"], 0.0)
        display_type = line._bispro_line_field_value(["display_type"], False)

        return {
            "display_type": display_type,
            "product_code": product.default_code if product and "default_code" in product._fields else "",
            "description": line.name if "name" in line._fields else "",
            "uom": uom.name if uom and hasattr(uom, "name") else "",
            "qty": qty or 0.0,
            "price_unit": price_unit or 0.0,
            "price_unit_display": line._bispro_line_money_display(price_unit or 0.0),
            "taxes": ", ".join(taxes.mapped("name")) if taxes else "",
            "subtotal": subtotal or 0.0,
            "subtotal_display": line._bispro_line_money_display(subtotal or 0.0),
        }
