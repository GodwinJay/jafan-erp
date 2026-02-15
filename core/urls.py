from django.contrib import admin
from django.urls import path, include
from erp.admin import get_customer_sites, get_customer_orders, get_order_items, get_vendor_materials

urlpatterns = [    
    # Admin
    path('admin/', admin.site.urls),
    
    # ERP app URLs
    path('erp/', include('erp.urls')),
]