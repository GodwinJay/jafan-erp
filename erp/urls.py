from django.urls import path
from . import views

urlpatterns = [
    # ==================== DASHBOARDS ====================
    path('dashboard/', views.dashboard_view, name='erp_dashboard'),
    path('transport-dashboard/', views.transport_dashboard_view, name='transport_dashboard'),
    
    # ==================== FINANCIAL REPORTS (NEW) ====================
    path('cash-flow/', views.cash_flow_view, name='cash_flow'),
    path('pl-report/', views.pl_report_view, name='pl_report'),
    
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
    
    # P&L and Cash Flow Excel (NEW)
    path('export/pl-excel/', views.export_pl_excel, name='export_pl_excel'),
    path('export/cashflow-excel/', views.export_cashflow_excel, name='export_cashflow_excel'),
    
    # ==================== PDF GENERATION ====================
    
    # Invoice (from SupplyLog)
    path('pdf/invoice/<int:supply_id>/', views.generate_invoice, name='generate_invoice'),
    
    # Waybill (from SupplyLog)
    path('pdf/waybill/<int:supply_id>/', views.generate_waybill, name='generate_waybill'),
    
    # Receipt (from Payment)
    path('pdf/receipt/<int:payment_id>/', views.generate_receipt, name='generate_receipt'),
    
    # Proforma Invoice (from SalesOrder)
    path('pdf/proforma/<int:order_id>/', views.generate_proforma, name='generate_proforma'),
    
    # P&L and Cash Flow PDF (NEW)
    path('pdf/pl/', views.generate_pl_pdf, name='generate_pl_pdf'),
    path('pdf/cashflow/', views.generate_cashflow_pdf, name='generate_cashflow_pdf'),
    
    # ==================== CUSTOMER STATEMENT ====================
    path('pdf/statement-select/<int:customer_id>/', views.select_statement_date, name='select_statement_date'),
    path('pdf/statement/<int:customer_id>/', views.generate_customer_statement, name='generate_customer_statement'),
    
    # ==================== VENDOR STATEMENT ====================
    path('pdf/vendor-statement-select/<int:vendor_id>/', views.select_vendor_statement_date, name='select_vendor_statement_date'),
    path('pdf/vendor-statement/<int:vendor_id>/', views.generate_vendor_statement, name='generate_vendor_statement'),
    
    # ==================== ACCOUNT STATEMENT ====================
    path('pdf/account-statement-select/<int:account_id>/', views.select_account_statement_date, name='select_account_statement_date'),
    path('pdf/account-statement/<int:account_id>/', views.generate_account_statement, name='generate_account_statement'),
    
    # ==================== AJAX ENDPOINTS (for chained dropdowns) ====================
    path('ajax/customer-sites/', views.get_customer_sites, name='ajax_customer_sites'),
    path('ajax/customer-orders/', views.get_customer_orders, name='ajax_customer_orders'),
    path('ajax/order-items/', views.get_order_items, name='ajax_order_items'),
    path('ajax/vendor-materials/', views.get_vendor_materials, name='ajax_vendor_materials'),

    # Sand Sale Receipt
    path('pdf/sand-receipt/<int:sale_id>/', views.generate_sand_receipt, name='generate_sand_receipt'),

    # ==================== LOAN STATEMENTS ====================
    path('pdf/loan-statement/<int:loan_id>/', views.generate_loan_statement, name='generate_loan_statement'),
    path('loans/report/', views.loan_report_view, name='loan_report'),
    path('export/loans/pdf/', views.export_loans_pdf, name='export_loans_pdf'),
    path('export/loans/excel/', views.export_loans_excel, name='export_loans_excel'),
]