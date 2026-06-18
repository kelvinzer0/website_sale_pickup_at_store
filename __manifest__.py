# -*- coding: utf-8 -*-
{
    'name': 'Website Sale Pickup At Store',
    'version': '17.0.1.0.4',
    'category': 'Website/Website',
    'summary': 'Pickup at store option (Ambil di Tempat) for website checkout, free shipping, dynamic business hours from Evolution API',
    'description': """
Website Sale Pickup At Store
============================

Adds an "Ambil di Tempat" (pickup at store) delivery option to the
website checkout. Customer pays online (QRIS) or cash-on-pickup (COD),
then picks up the order at the store instead of having it delivered.

Key features
------------
* New delivery.carrier "Ambil di Tempat -- Warung Lakku" with `is_pickup=True`.
* Pickup orders are **free of shipping cost** (delivery price = 0).
* Pickup orders automatically set the shipping address to the store
  address (so the sale.order's partner_shipping_id stays as the
  customer's billing address, but a flag `is_pickup_order=True` marks
  it as pickup).
* Dynamic business hours fetched from Evolution API
  (`POST /chat/fetchBusinessProfile/{instance}`) and cached 24h in
  `ir.config_parameter`. Admin can refresh manually via Settings.
* Compatible with the existing WhatsApp notification triggers:
  - `order_ready_for_pickup` (Pesanan Siap Diambil) when admin clicks
    "Mark Ready for Pickup" in the dashboard.
  - `order_done` (Pesanan Selesai) when admin clicks "Mark Picked Up".
* No interference with regular delivery orders -- both flows coexist.

Configuration
-------------
1. Install this module.
2. Go to *Settings > Website > Pickup At Store*.
3. Set the **Pickup Store Address** (default = company address).
4. Click **Refresh Business Hours** to fetch hours from Evolution API
   (uses the same base_url / instance_name / api_key as the WhatsApp
   notification module).
5. The "Ambil di Tempat -- Warung Lakku" carrier is auto-created at
   install time and visible to customers at checkout.

Workflow
--------
new -> cooking -> ready_for_pickup -> done
(skip out_for_delivery for pickup orders)

Trigger mapping (in whatsapp_evolution_notification >= v1.5.0):
* cooking               -> order_cooking
* ready_for_pickup      -> order_ready_for_pickup
* done (via mark_picked_up) -> order_done

Author: kelvinzer0
License: LGPL-3
""",
    'author': 'kelvinzer0',
    'website': 'https://github.com/kelvinzer0',
    'license': 'LGPL-3',
    'depends': [
        'website_sale',
        'website_sale_dashboard',
        'delivery',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/delivery_carrier_data.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/checkout_pickup_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
