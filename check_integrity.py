import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jafan_erp.settings')
django.setup()

from erp.models import *
from decimal import Decimal

print("="*60)
print("JAFAN ERP - DATABASE INTEGRITY CHECK")
print("="*60)

print("\n[1] Customer Balances:")
for c in Customer.objects.all()[:5]:
    print(f"  {c.name}: {c.account_balance:,.2f}")

print("\n[2] Vendor Balances:")
for v in Vendor.objects.all():
    status = "(Internal)" if v.is_internal else ""
    print(f"  {v.name} {status}: {v.account_balance:,.2f}")

print("\n[3] Payment Accounts:")
for a in PaymentAccount.objects.all():
    print(f"  {a.bank_name}: {a.current_balance:,.2f}")

print("\n[4] Block Stock:")
for b in BlockType.objects.all():
    print(f"  {b.name}: {b.current_stock}")

print("\n[5] Material Stock:")
for m in Material.objects.filter(is_inventory_tracked=True):
    print(f"  {m.get_name_display()}: {m.current_stock}")

print("\n[6] VendorPayments (NEW):")
print(f"  Total records: {VendorPayment.objects.count()}")

print("\n" + "="*60)
print("CHECK COMPLETE")
print("="*60)