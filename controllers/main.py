# -*- coding: utf-8 -*-
"""Controller hooks for Pickup At Store.

Hook checkout flow untuk:
- Set shipping address = store address saat pickup dipilih (di backend
  melalui override _get_shipment_rate -> 0; address override dilakukan
  saat order dibuat, see sale_order.py override).

Untuk sekarang controller ini hanya memastikan endpoint checkout
tetap bekerja. Address override dilakukan via override model, bukan
controller (lebih reliable).
"""

from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSalePickup(WebsiteSale):
    """Inherit WebsiteSale untuk hook alur checkout."""

    @http.route()
    def shop_payment(self, **post):
        """Hook /shop/payment untuk inject pickup info ke qweb context.

        Kita tidak perlu modifikasi response — info banner sudah di-inject
        via template inheritance (views/checkout_pickup_templates.xml)
        yang baca langsung dari ir.config_parameter.
        """
        return super().shop_payment(**post)
