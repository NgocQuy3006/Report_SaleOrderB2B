# -*- coding: utf-8 -*-

import io
from html import escape
from pathlib import Path

from odoo import http, _
from odoo.http import request


class BisproSaleOrderController(http.Controller):

    def _get_so(self, so_id):
        so = request.env["sale.order"].browse(int(so_id)).exists()
        if not so:
            return None
        if hasattr(so, "check_access"):
            so.check_access("read")
        else:
            so.check_access_rights("read")
            so.check_access_rule("read")
        return so

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

    @http.route(['/bispro/so/<int:order_id>/html'], type='http', auth='user')
    def bispro_so_html(self, order_id, **kwargs):
        order = request.env['sale.order'].browse(order_id)
        if not order.exists():
            return request.not_found()

        try:
            html_content, _content_type = request.env['ir.actions.report']._render_qweb_html(
                'saleorder_report.action_report_bispro_sale_order',
                res_ids=order.ids
            )
            return request.make_response(
                html_content,
                headers=[('Content-Type', 'text/html; charset=utf-8')]
            )
        except Exception as e:
            return request.make_response(f"Lỗi hệ thống khi render HTML: {str(e)}", status=500)

    @http.route(['/bispro/so/<int:order_id>/pdf'], type='http', auth='user')
    def bispro_so_pdf(self, order_id, **kwargs):
        order = request.env['sale.order'].browse(order_id)
        if not order.exists():
            return request.not_found()

        try:
            pdf_content, _content_type = request.env['ir.actions.report']._render_qweb_pdf(
                'saleorder_report.action_report_bispro_sale_order',
                res_ids=order.ids
            )
            return request.make_response(
                pdf_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', 'inline; filename=SaleOrder.pdf')
                ]
            )
        except Exception as e:
            return request.make_response(f"Lỗi xuất PDF: {str(e)}", status=500)

    # =========================================================================
    # ROUTE XUẤT EXCEL CHUẨN ĐỊNH DẠNG - ĐÃ FIX DỨT ĐIỂM LỖI PRODUCT_UOM
    # =========================================================================
    @http.route(['/bispro/so/<int:order_id>/xlsx'], type='http', auth='user')
    def bispro_so_xlsx(self, order_id, **kwargs):
        so = self._get_so(order_id)
        if not so:
            return request.not_found()

        try:
            import xlsxwriter
        except ImportError:
            return request.make_response(
                "Python package xlsxwriter is required. Install it on the Odoo server: pip install xlsxwriter",
                headers=[("Content-Type", "text/plain; charset=utf-8")],
                status=500,
            )

        try:
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            sheet = workbook.add_worksheet("Sale Order")

            # Thiết lập hiển thị trang in
            sheet.set_portrait()
            sheet.set_paper(9)  # Khổ A4
            sheet.fit_to_pages(1, 0)
            sheet.set_margins(0.20, 0.20, 0.22, 0.22)
            sheet.hide_gridlines(2)
            sheet.set_footer('&CThis Sale Order is system-generated from Bispro.vn. Page &P of &N')

            # Cố định độ rộng cột để không bị dồn chữ làm mất nhãn
            widths = [8, 18, 38, 12, 12, 15, 14, 18]
            for idx, width in enumerate(widths):
                sheet.set_column(idx, idx, width)

            # Bảng màu thương hiệu chuyên nghiệp
            navy = "#0F172A"
            blue = "#1E3A8A"
            gold = "#F59E0B"
            slate = "#64748B"
            light = "#E2E8F0"
            white = "#FFFFFF"
            pale_note = "#FFFBEB"

            # Thiết lập định dạng (Styles)
            def add_fmt(props=None):
                base = {"font_name": "Arial", "font_size": 9, "font_color": navy, "border": 1, "border_color": navy,
                        "valign": "vcenter"}
                if props: base.update(props)
                return workbook.add_format(base)

            fmt_strip = workbook.add_format({"bg_color": navy})
            fmt_gold = workbook.add_format({"bg_color": gold})
            fmt_company = workbook.add_format({"font_name": "Arial", "bold": True, "font_size": 11, "font_color": navy})
            fmt_muted = workbook.add_format({"font_name": "Arial", "font_size": 8, "font_color": slate})
            fmt_title = workbook.add_format(
                {"font_name": "Arial", "bold": True, "font_size": 22, "font_color": navy, "align": "right",
                 "valign": "vcenter"})
            fmt_doc_no = workbook.add_format(
                {"font_name": "Arial", "bold": True, "font_size": 10, "font_color": white, "bg_color": blue,
                 "align": "center", "valign": "vcenter"})
            fmt_right_text = workbook.add_format(
                {"font_name": "Arial", "font_size": 9, "font_color": navy, "align": "right", "valign": "vcenter"})
            fmt_header_box = add_fmt({"bg_color": white, "text_wrap": True, "valign": "top"})
            fmt_section = add_fmt({"bold": True, "font_color": white, "bg_color": navy, "align": "left"})
            fmt_label = add_fmt({"bold": True, "bg_color": light, "text_wrap": True, "align": "left"})
            fmt_value = add_fmt({"bg_color": white, "text_wrap": True})
            fmt_value_bold = add_fmt({"bold": True, "bg_color": white, "text_wrap": True})
            fmt_line_header = add_fmt(
                {"bold": True, "font_color": white, "bg_color": blue, "align": "center", "text_wrap": True})
            fmt_center = add_fmt({"align": "center", "valign": "top"})
            fmt_text = add_fmt({"text_wrap": True, "valign": "top"})
            fmt_number = add_fmt({"num_format": "#,##0.00", "align": "right", "valign": "top"})

            currency_name = so.currency_id.name if (hasattr(so, 'currency_id') and so.currency_id) else "VND"
            money_format = '#,##0.00' + (f' "{currency_name}"' if currency_name else '')
            fmt_money = add_fmt({"num_format": money_format, "align": "right", "valign": "top"})
            fmt_total_label = add_fmt({"bold": True, "bg_color": light, "align": "right"})
            fmt_total_value = add_fmt({"bold": True, "bg_color": light, "num_format": money_format, "align": "right"})
            fmt_grand_label = add_fmt(
                {"bold": True, "font_color": white, "bg_color": navy, "align": "right", "font_size": 10})
            fmt_grand_total = add_fmt(
                {"bold": True, "font_color": white, "bg_color": navy, "num_format": money_format, "align": "right",
                 "font_size": 10})
            fmt_note = add_fmt({"bg_color": pale_note, "border_color": gold, "text_wrap": True, "valign": "top"})
            fmt_sign_head = add_fmt({"bold": True, "align": "center", "valign": "top"})
            fmt_sign = add_fmt({"font_color": slate, "align": "center", "valign": "bottom"})
            fmt_footer = workbook.add_format(
                {"font_name": "Arial", "font_size": 8, "font_color": slate, "align": "center"})

            # Top Ribbon
            sheet.set_row(0, 7)
            sheet.merge_range(0, 0, 0, 6, "", fmt_strip)
            sheet.write(0, 7, "", fmt_gold)

            # Khung trắng header chống đè ô
            row = 1
            for r in range(row, row + 7):
                sheet.set_row(r, 22)
                for c in range(0, 8):
                    sheet.write_blank(r, c, None, fmt_header_box)

            logo_path = str(Path(__file__).resolve().parents[1] / "static" / "src" / "img" / "logo.png")
            if Path(logo_path).is_file():
                try:
                    sheet.insert_image(row, 0, logo_path,
                                       {"x_scale": 0.20, "y_scale": 0.20, "x_offset": 8, "y_offset": 5})
                except Exception:
                    pass

            sheet.write(row + 2, 0, so.company_id.name or "", fmt_company)
            sheet.write(row + 3, 0, self._partner_address(so.company_id.partner_id), fmt_muted)
            sheet.write(row + 4, 0, "Tax ID: %s" % (so.company_id.partner_id.vat or ""), fmt_muted)

            sheet.merge_range(row, 4, row, 7, "SALE ORDER", fmt_title)
            sheet.merge_range(row + 1, 6, row + 1, 7, so.name or "", fmt_doc_no)
            date_str = so.date_order.strftime("%d/%m/%Y") if so.date_order else ""
            sheet.merge_range(row + 2, 5, row + 2, 7, "Order Date: %s" % date_str, fmt_right_text)
            sheet.merge_range(row + 3, 5, row + 3, 7, "Status: Sales Order", fmt_right_text)
            row += 7

            # --- 1. DOCUMENT CONTROL ---
            sheet.merge_range(row, 0, row, 7, "1. DOCUMENT CONTROL", fmt_section)
            sheet.set_row(row, 20)
            row += 1

            sheet.set_row(row, 24)
            sheet.write(row, 0, "SO Number", fmt_label)
            sheet.merge_range(row, 1, row, 3, so.name or "", fmt_value)
            sheet.write(row, 4, "Salesperson", fmt_label)
            sheet.merge_range(row, 5, row, 7, so.user_id.name or "", fmt_value)
            row += 1

            sheet.set_row(row, 24)
            sheet.write(row, 0, "Currency", fmt_label)
            sheet.merge_range(row, 1, row, 3, currency_name, fmt_value)
            payment_term = so.payment_term_id.name if so.payment_term_id else ""
            sheet.write(row, 4, "Payment Terms", fmt_label)
            sheet.merge_range(row, 5, row, 7, payment_term, fmt_value)
            row += 1

            sheet.set_row(row, 24)
            commit_str = so.commitment_date.strftime("%d/%m/%Y") if hasattr(so, 'commitment_date') and so.commitment_date else ""
            sheet.write(row, 0, "Commitment Date", fmt_label)
            sheet.merge_range(row, 1, row, 3, commit_str, fmt_value)
            sheet.write(row, 4, "", fmt_label)
            sheet.merge_range(row, 5, row, 7, "", fmt_value)
            row += 2

            # --- 2 & 3. CUSTOMER & COMPANY INFO ---
            sheet.merge_range(row, 0, row, 3, "2. CUSTOMER INFORMATION", fmt_section)
            sheet.merge_range(row, 4, row, 7, "3. SHIP TO / COMPANY INFORMATION", fmt_section)
            sheet.set_row(row, 20)
            row += 1

            sheet.set_row(row, 24)
            sheet.write(row, 0, "Customer", fmt_label)
            sheet.merge_range(row, 1, row, 3, so.partner_id.display_name or "", fmt_value_bold)
            sheet.write(row, 4, "Company", fmt_label)
            sheet.merge_range(row, 5, row, 7, so.company_id.name or "", fmt_value_bold)
            row += 1

            sheet.set_row(row, 24)
            sheet.write(row, 0, "Address", fmt_label)
            sheet.merge_range(row, 1, row, 3, self._partner_address(so.partner_id), fmt_value)
            sheet.write(row, 4, "Address", fmt_label)
            sheet.merge_range(row, 5, row, 7, self._partner_address(so.company_id.partner_id), fmt_value)
            row += 1

            sheet.set_row(row, 24)
            sheet.write(row, 0, "Tax ID", fmt_label)
            sheet.merge_range(row, 1, row, 3, so.partner_id.vat or "", fmt_value)
            sheet.write(row, 4, "Tax ID", fmt_label)
            sheet.merge_range(row, 5, row, 7, so.company_id.partner_id.vat or "", fmt_value)
            row += 1

            sheet.set_row(row, 24)
            cust_contact = f"{so.partner_id.phone or ''} / {so.partner_id.email or ''}"
            comp_contact = f"{so.company_id.partner_id.phone or ''} / {so.company_id.partner_id.email or ''}"
            sheet.write(row, 0, "Phone / Email", fmt_label)
            sheet.merge_range(row, 1, row, 3, cust_contact, fmt_value)
            sheet.write(row, 4, "Phone / Email", fmt_label)
            sheet.merge_range(row, 5, row, 7, comp_contact, fmt_value)
            row += 2

            # --- BẢNG CHI TIẾT SẢN PHẨM ---
            headers = ["No.", "Product Code", "Description", "UoM", "Qty", "Unit Price", "Taxes", "Subtotal"]
            sheet.set_row(row, 26)
            for col, header in enumerate(headers):
                sheet.write(row, col, header, fmt_line_header)
            line_header_row = row
            row += 1

            line_no = 1
            for line in so.order_line:
                if getattr(line, "display_type", False):
                    sheet.set_row(row, 22)
                    sheet.merge_range(row, 0, row, 7, line.name or "", fmt_section)
                    row += 1
                    continue

                # Xử lý lấy Tên Đơn vị tính (UoM) tương thích ngược mọi phiên bản Odoo
                uom_name = ""
                if hasattr(line, 'product_uom_id') and line.product_uom_id:
                    uom_name = line.product_uom_id.name
                elif hasattr(line, 'product_uom') and line.product_uom:
                    uom_name = line.product_uom.name

                sheet.write_number(row, 0, line_no, fmt_center)
                sheet.write(row, 1, line.product_id.default_code or "", fmt_text)
                sheet.write(row, 2, line.name or "", fmt_text)
                sheet.write(row, 3, uom_name or "", fmt_center)
                sheet.write_number(row, 4, float(line.product_uom_qty or 0.0), fmt_number)
                sheet.write_number(row, 5, float(line.price_unit or 0.0), fmt_money)
                taxes_str = ", ".join(line.tax_id.mapped("name")) if hasattr(line, "tax_id") else ""
                sheet.write(row, 6, taxes_str, fmt_text)
                sheet.write_number(row, 7, float(line.price_subtotal or 0.0), fmt_money)
                sheet.set_row(row, 26)
                line_no += 1
                row += 1

            if line_no == 1:
                sheet.set_row(row, 24)
                sheet.merge_range(row, 0, row, 7, "No order lines", fmt_center)
                row += 1

            # Khối Tổng cộng (Totals)
            sheet.set_row(row, 22)
            sheet.merge_range(row, 0, row, 6, "Untaxed Amount", fmt_total_label)
            sheet.write_number(row, 7, float(so.amount_untaxed or 0.0), fmt_total_value)
            row += 1

            sheet.set_row(row, 22)
            sheet.merge_range(row, 0, row, 6, "Taxes", fmt_total_label)
            sheet.write_number(row, 7, float(so.amount_tax or 0.0), fmt_total_value)
            row += 1

            sheet.set_row(row, 24)
            sheet.merge_range(row, 0, row, 6, "TOTAL", fmt_grand_label)
            sheet.write_number(row, 7, float(so.amount_total or 0.0), fmt_grand_total)
            row += 2

            # Ghi chú & Điều khoản
            sheet.set_row(row, 20)
            sheet.merge_range(row, 0, row, 7, "4. TERMS, CONDITIONS & NOTES", fmt_section)
            row += 1
            sheet.set_row(row, 20)
            sheet.set_row(row + 1, 20)
            notes = so.note or "Please supply goods/services according to this Sales Order, agreed commercial terms, applicable tax regulations, quality standards, and delivery schedule."
            sheet.merge_range(row, 0, row + 1, 7, notes, fmt_note)
            row += 3

            # Khối Chữ ký
            sheet.set_row(row, 22)
            for start, end, label in [(0, 1, "Prepared by"), (2, 3, "Reviewed by"), (4, 5, "Approved by"),
                                      (6, 7, "Customer Confirmation")]:
                sheet.merge_range(row, start, row, end, label, fmt_sign_head)

            sheet.set_row(row + 1, 20)
            sheet.set_row(row + 2, 20)
            sheet.set_row(row + 3, 20)
            for start, end, label in [(0, 1, "Prepared by"), (2, 3, "Reviewed by"), (4, 5, "Approved by"),
                                      (6, 7, "Customer Confirmation")]:
                sheet.merge_range(row + 1, start, row + 3, end, "Signature / Date", fmt_sign)
            row += 4

            sheet.set_row(row, 20)
            sheet.merge_range(row, 0, row, 7,
                              "This Sales Order is system-generated from Bispro.vn. Please verify SO number, customer, delivery schedule, tax and commercial terms before execution.",
                              fmt_footer)

            sheet.freeze_panes(line_header_row + 1, 0)
            sheet.print_area(0, 0, row, 7)

            workbook.close()
            output.seek(0)
            filename = f"{so.name or 'sale_order'}.xlsx"

            # Trả về gói tin Excel chuẩn cho trình duyệt
            return request.make_response(
                output.read(),
                headers=[
                    ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ("Content-Disposition", f"attachment; filename={filename}"),
                ],
            )
        except Exception as e:
            try:
                workbook.close()
            except Exception:
                pass
            return request.make_response(f"Lỗi hệ thống khi tạo file Excel thực tế: {str(e)}", status=500)