from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_view, name='erp_dashboard'),
    
    # ==================== EXPORTS (Excel/CSV) ====================
    
    # Sales Exports
    path('export/sales/csv/', views.export_sales_csv, name='export_sales_csv'),
    path('export/sales/excel/', views.export_sales_excel, name='export_sales_excel'),
    
    # Expenses Exports
    path('export/expenses/csv/', views.export_expenses_csv, name='export_expenses_csv'),
    path('export/expenses/excel/', views.export_expenses_excel, name='export_expenses_excel'),
    
    # Production Exports
    path('export/production/csv/', views.export_production_csv, name='export_production_csv'),
    path('export/production/excel/', views.export_production_excel, name='export_production_excel'),
    
    # Customer Ledger
    path('export/customers/', views.export_customer_ledger, name='export_customer_ledger'),
    
    # Inventory
    path('export/inventory/', views.export_inventory, name='export_inventory'),
    
    # ==================== PDF GENERATION ====================
    
    # Invoice (from SupplyLog)
    path('pdf/invoice/<int:supply_id>/', views.generate_invoice, name='generate_invoice'),
    
    # Waybill (from SupplyLog)
    path('pdf/waybill/<int:supply_id>/', views.generate_waybill, name='generate_waybill'),
    
    # Receipt (from Payment)
    path('pdf/receipt/<int:payment_id>/', views.generate_receipt, name='generate_receipt'),
    
    # Customer Statement
    path('pdf/statement/<int:customer_id>/', views.generate_customer_statement, name='generate_customer_statement'),

    #Proforma Invoice
    path('pdf/proforma/<int:order_id>/', views.generate_proforma, name='generate_proforma'),  # NEW

    # Date Picker for Statement (NEW)
    path('pdf/statement-select/<int:customer_id>/', views.select_statement_date, name='select_statement_date'),
    
    # The actual PDF generator (Existing)
    path('pdf/statement/<int:customer_id>/', views.generate_customer_statement, name='generate_customer_statement'),

]