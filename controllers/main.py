# -*- coding: utf-8 -*-
"""Controller hooks for Pickup At Store.

Override `/shop/address` to handle the `pickup_at_store` flag submitted
from the address form when customer picks "Ambil di Tempat" mode.

When pickup_at_store=1:
  * Pre-fill ALL required billing fields (street, city, zip, state_id,
    country_id, email) with the company's address data so the standard
    address validation passes — the customer only needs to enter name
    and phone.
  * After super().address() saves the partner and order, set the
    order's carrier_id to the pickup carrier (which enforces free
    shipping via the sale_order._get_shipment_rate override).
  * Also force use_same=True so billing = shipping (skip the shipping
    step) — pickup orders don't need a separate shipping address.
"""

import logging

from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class WebsiteSalePickup(WebsiteSale):
    """Inherit WebsiteSale to hook the address flow for pickup mode."""

    @http.route()
    def address(self, **kw):
        """Hook /shop/address to handle pickup_at_store flag.

        Strategy:
          1. If pickup_at_store=1 in POST, pre-fill ALL required billing
             fields with the company's address data so super().address()
             validation passes (the customer only needs name + phone).
             Also force use_same=True to skip the shipping step.
          2. Call super().address() — handles the normal save + redirect.
          3. After super() returns a redirect (i.e. save was successful),
             set order.carrier_id = pickup carrier so the order is
             marked as pickup (which enforces free shipping).
        """
        is_pickup_submit = (
            kw.get('pickup_at_store') == '1'
            and 'submitted' in kw
            and http.request.httprequest.method == "POST"
        )

        if is_pickup_submit:
            # Get company address as the default for missing required fields
            website = http.request.website
            company = website.company_id
            # Build a dict of store address fields from the company
            store_addr = {
                'street': company.street or '',
                'city': company.city or '',
                'zip': company.zip or '',
                'state_id': str(company.state_id.id) if company.state_id else '',
                'country_id': str(company.country_id.id) if company.country_id else '100',
            }
            # Pre-fill any missing required field with the company's value
            for fname, fval in store_addr.items():
                if not kw.get(fname):
                    kw[fname] = fval
            # Email is required for billing but customer may not have one
            # for pickup. Use a placeholder format: pickup+<phone>@warunglakku.com
            if not kw.get('email'):
                phone = (kw.get('phone') or '').replace('+', '').replace('-', '').replace(' ', '')
                kw['email'] = f"pickup+{phone or 'customer'}@warunglakku.com"
            # Force use_same=True so billing = shipping (skip shipping step)
            kw['use_same'] = '1'
            _logger.info(
                "[PICKUP] address submit with pickup_at_store=1; "
                "pre-filled street=%r city=%r state_id=%r country_id=%r email=%r",
                kw.get('street'), kw.get('city'), kw.get('state_id'),
                kw.get('country_id'), kw.get('email'),
            )

        # Call super — handles GET render + POST save + redirect
        response = super().address(**kw)

        # After super, if pickup was submitted AND the response is a
        # redirect (HTTP 303), the save was successful. Set carrier.
        if is_pickup_submit and response is not None:
            status = getattr(response, 'status_code', None)
            is_redirect = status in (301, 302, 303, 307, 308)
            if is_redirect:
                try:
                    order = http.request.website.sale_get_order()
                    if order:
                        pickup_carrier = http.request.env['delivery.carrier'].sudo().search(
                            [('is_pickup', '=', True), ('active', '=', True)],
                            limit=1,
                        )
                        if pickup_carrier:
                            order.sudo().write({
                                'carrier_id': pickup_carrier.id,
                            })
                            # Force recompute delivery price
                            order._compute_delivery_price()
                            _logger.info(
                                "[PICKUP] Order %s carrier set to %s (id=%s)",
                                order.name, pickup_carrier.name, pickup_carrier.id,
                            )
                        else:
                            _logger.warning(
                                "[PICKUP] No pickup carrier found in DB — "
                                "carrier_id not set on order %s",
                                order.name,
                            )
                except Exception as e:
                    _logger.exception(
                        "[PICKUP] Failed to set pickup carrier on order: %s", e)

        return response

    @http.route()
    def shop_payment(self, **post):
        """Hook /shop/payment — info banner already injected via template."""
        return super().shop_payment(**post)
