# -*- coding: utf-8 -*-
"""delivery.carrier extension: add is_pickup flag.

Carrier dengan is_pickup=True dianggap sebagai metode "Ambil di Tempat".
Modul lain (sale_order, whatsapp, dashboard) cek field ini untuk:
- Force delivery price = 0 (gratis ongkir)
- Skip shipping address (shipping = store address)
- Trigger flow pickup (ready_for_pickup -> done) bukan delivery flow
"""

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    is_pickup = fields.Boolean(
        string='Pickup at Store',
        default=False,
        help="Jika True, carrier ini dianggap metode 'Ambil di Tempat'. "
             "Ongkir otomatis gratis (0) dan shipping address diset ke "
             "alamat toko saat checkout.",
    )
