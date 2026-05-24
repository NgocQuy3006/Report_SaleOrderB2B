# -*- coding: utf-8 -*-

import base64
import html
from pathlib import Path

from markupsafe import Markup

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # -------------------------------------------------------------------------
    # Safe field helpers for Odoo 19CE/custom builds
    # -------------------------------------------------------------------------

    def _bispro_has_field(self, field_name):

        self.ensure_one()

        return field_name in self._fields

    def _bispro_field_value(
        self,
        field_names,
        default=False
    ):

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

        if value in (None, False):
            return Markup("")

        text = html.escape(
            str(value),
            quote=True
        )

        safe = []

        for ch in text:

            if ord(ch) > 127:
                safe.append(
                    "&#%d;" % ord(ch)
                )
            else:
                safe.append(ch)

        return Markup("".join(safe))

    def _bispro_money_display(
        self,
        amount,
        currency=False
    ):

        symbol = ""
        position = "after"

        if currency:

            try:
                symbol = (
                    currency.symbol
                    or currency.name
                    or ""
                )

                position = (
                    currency.position
                    or "after"
                )

            except Exception:
                symbol = ""

        try:
            amount_text = "{:,.2f}".format(
                amount or 0.0
            )

        except Exception:
            amount_text = str(amount or "")

        if symbol and position == "before":
            return "%s %s" % (
                symbol,
                amount_text
            )

        if symbol:
            return "%s %s" % (
                amount_text,
                symbol
            )

        return amount_text

    def _bispro_partner_address(
        self,
        partner
    ):

        if not partner:
            return ""

        parts = []

        for field_name in [
            "street",
            "street2",
            "city",
            "state_id",
            "country_id",
        ]:

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

        try:

            logo_path = (
                Path(__file__).resolve().parents[1]
                / "static"
                / "src"
                / "img"
                / "logo.png"
            )

            if logo_path.exists():

                encoded = base64.b64encode(
                    logo_path.read_bytes()
                ).decode("ascii")

                return (
                    "data:image/png;base64,%s"
                    % encoded
                )

        except Exception:
            pass

        return ""

    def _bispro_so_report_values(self):

        self.ensure_one()

        so = self

        company_partner = (
            so.company_id.partner_id
            if so.company_id
            else False
        )

        customer = so.partner_id

        state_label = so.state or ""

        if (
            "state" in so._fields
            and getattr(
                so._fields["state"],
                "selection",
                None
            )
        ):

            try:
                state_label = dict(
                    so._fields["state"].selection
                ).get(
                    so.state,
                    so.state or ""
                )

            except Exception:
                state_label = so.state or ""

        payment_term = so._bispro_field_value(
            [
                "payment_term_id",
                "payment_term",
            ],
            False
        )

        commitment_date = so._bispro_field_value(
            [
                "commitment_date",
                "expected_date",
            ],
            False
        )

        notes = (
            so._bispro_field_value(
                [
                    "note",
                    "notes",
                ],
                ""
            )
            or ""
        )

        return {

            "logo_data_uri":
                so._bispro_logo_data_uri(),

            "name":
                so.name or "",

            "date_order":
                so.date_order
                if "date_order"
                in so._fields
                else False,

            "state":
                state_label,

            "salesperson":
                so.user_id.name
                if "user_id"
                in so._fields
                and so.user_id
                else "",

            "currency":
                so.currency_id
                if "currency_id"
                in so._fields
                else False,

            "currency_name":
                so.currency_id.name
                if "currency_id"
                in so._fields
                and so.currency_id
                else "",

            "payment_term":
                so._bispro_name(
                    payment_term
                ),

            "commitment_date":
                commitment_date,

            "customer_name":
                customer.display_name
                if customer
                else "",

            "customer_address":
                so._bispro_partner_address(
                    customer
                ),

            "customer_vat":
                customer.vat
                if customer
                and "vat"
                in customer._fields
                else "",

            "customer_phone":
                customer.phone
                if customer
                and "phone"
                in customer._fields
                else "",

            "customer_email":
                customer.email
                if customer
                and "email"
                in customer._fields
                else "",

            "company_name":
                so.company_id.name
                if so.company_id
                else "",

            "company_address":
                so._bispro_partner_address(
                    company_partner
                ),

            "company_vat":
                company_partner.vat
                if company_partner
                and "vat"
                in company_partner._fields
                else "",

            "company_phone":
                company_partner.phone
                if company_partner
                and "phone"
                in company_partner._fields
                else "",

            "company_email":
                (
                    so.company_id.email
                    if so.company_id
                    and "email"
                    in so.company_id._fields
                    and so.company_id.email
                    else (
                        company_partner.email
                        if company_partner
                        and "email"
                        in company_partner._fields
                        else ""
                    )
                ),

            "amount_untaxed":
                so.amount_untaxed
                if "amount_untaxed"
                in so._fields
                else 0.0,

            "amount_tax":
                so.amount_tax
                if "amount_tax"
                in so._fields
                else 0.0,

            "amount_total":
                so.amount_total
                if "amount_total"
                in so._fields
                else 0.0,

            "amount_untaxed_display":
                so._bispro_money_display(
                    (
                        so.amount_untaxed
                        if "amount_untaxed"
                        in so._fields
                        else 0.0
                    ),
                    (
                        so.currency_id
                        if "currency_id"
                        in so._fields
                        else False
                    )
                ),

            "amount_tax_display":
                so._bispro_money_display(
                    (
                        so.amount_tax
                        if "amount_tax"
                        in so._fields
                        else 0.0
                    ),
                    (
                        so.currency_id
                        if "currency_id"
                        in so._fields
                        else False
                    )
                ),

            "amount_total_display":
                so._bispro_money_display(
                    (
                        so.amount_total
                        if "amount_total"
                        in so._fields
                        else 0.0
                    ),
                    (
                        so.currency_id
                        if "currency_id"
                        in so._fields
                        else False
                    )
                ),

            "notes":
                notes,
        }

    def action_bispro_so_print_pdf(self):

        self.ensure_one()

        return self.env.ref(
            "saleorder_report.action_report_bispro_sale_order"
        ).report_action(self)

    def action_bispro_so_view_html(self):

        self.ensure_one()

        return {
            "type": "ir.actions.act_url",
            "url": "/report/html/saleorder_report.report_sale_order_big4/%s" % self.id,
            "target": "new",
        }

    def action_bispro_so_view_pdf(self):

        self.ensure_one()

        return {
            "type": "ir.actions.act_url",
            "url": "/report/pdf/saleorder_report.report_sale_order_big4/%s" % self.id,
            "target": "new",
        }

    def action_bispro_so_export_xlsx(self):
        self.ensure_one()
        # Gọi chính xác đến đường dẫn Controller xử lý Excel riêng biệt
        return {
            "type": "ir.actions.act_url",
            "url": "/bispro/so/%s/xlsx" % self.id,
            "target": "self",
        }
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _bispro_line_field_value(
        self,
        field_names,
        default=False
    ):

        self.ensure_one()

        if isinstance(field_names, str):
            field_names = [field_names]

        for field_name in field_names:

            if field_name in self._fields:
                return self[field_name]

        return default

    def _bispro_line_money_display(
        self,
        amount
    ):

        self.ensure_one()

        currency = False

        try:
            currency = (
                self.order_id.currency_id
            )

        except Exception:
            currency = False

        symbol = ""
        position = "after"

        if currency:

            try:
                symbol = (
                    currency.symbol
                    or currency.name
                    or ""
                )

                position = (
                    currency.position
                    or "after"
                )

            except Exception:
                symbol = ""

        try:
            amount_text = "{:,.2f}".format(
                amount or 0.0
            )

        except Exception:
            amount_text = str(amount or "")

        if symbol and position == "before":
            return "%s %s" % (
                symbol,
                amount_text
            )

        if symbol:
            return "%s %s" % (
                amount_text,
                symbol
            )

        return amount_text

    def _bispro_line_report_values(self):

        self.ensure_one()

        line = self

        product = (
            line.product_id
            if "product_id"
            in line._fields
            else False
        )

        uom = line._bispro_line_field_value(
            [
                "product_uom",
                "product_uom_id",
            ],
            False
        )

        taxes = line._bispro_line_field_value(
            [
                "tax_id",
                "taxes_id",
            ],
            False
        )

        qty = line._bispro_line_field_value(
            [
                "product_uom_qty",
                "product_qty",
                "quantity",
                "qty",
            ],
            0.0
        )

        price_unit = (
            line._bispro_line_field_value(
                ["price_unit"],
                0.0
            )
        )

        subtotal = (
            line._bispro_line_field_value(
                [
                    "price_subtotal",
                    "price_total",
                ],
                0.0
            )
        )

        display_type = (
            line._bispro_line_field_value(
                ["display_type"],
                False
            )
        )

        return {

            "display_type":
                display_type,

            "product_code":
                (
                    product.default_code
                    if product
                    and "default_code"
                    in product._fields
                    else ""
                ),

            "description":
                line.name
                if "name"
                in line._fields
                else "",

            "uom":
                (
                    uom.name
                    if uom
                    and hasattr(uom, "name")
                    else ""
                ),

            "qty":
                qty or 0.0,

            "price_unit":
                price_unit or 0.0,

            "price_unit_display":
                line._bispro_line_money_display(
                    price_unit or 0.0
                ),

            "taxes":
                (
                    ", ".join(
                        taxes.mapped("name")
                    )
                    if taxes
                    else ""
                ),

            "subtotal":
                subtotal or 0.0,

            "subtotal_display":
                line._bispro_line_money_display(
                    subtotal or 0.0
                ),
        }