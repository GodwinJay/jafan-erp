from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse
from datetime import datetime
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone  # <--- THIS WAS MISSING
from .kpi_service import KPIService
from .exports import ReportExporter
from .models import SupplyLog, Payment, Customer, SalesOrder
from .pdf_generator import (
    InvoiceGenerator,
    WaybillGenerator,
    ReceiptGenerator,
    CustomerStatementGenerator,
    ProformaInvoiceGenerator
)


@staff_member_required
def select_statement_date(request, customer_id):
    """Intermediary page to select dates before generating statement."""
    customer = get_object_or_404(Customer, pk=customer_id)
    
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if not start_date or not end_date:
            messages.error(request, "Please select both start and end dates.")
        else:
            # Redirect to the actual PDF generator with dates in URL
            url = reverse('generate_customer_statement', args=[customer_id])
            return redirect(f"{url}?start_date={start_date}&end_date={end_date}")

    context = {
        'customer': customer,
        'today': timezone.now().date().strftime('%Y-%m-%d'),
        # Default start date: 1st of current month
        'default_start': timezone.now().date().replace(day=1).strftime('%Y-%m-%d'), 
        'site_header': "Jafan ERP",
        'title': f"Generate Statement: {customer.name}"
    }
    return render(request, 'admin/erp/date_picker.html', context)


@staff_member_required
def dashboard_view(request):
    service = KPIService()
    
    context = {
        "stats": service.get_summary_stats(),
        "debtors": service.get_top_debtors(),
        "alerts": service.get_inventory_alerts(),
        "activity": service.get_recent_activity(),
        "title": "Executive Dashboard",
        "site_header": "Jafan ERP",
    }
    
    return render(request, "admin/erp/dashboard.html", context)


def parse_dates(request):
    """Helper to parse date filters from request."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    return start_date, end_date


@staff_member_required
def export_sales_csv(request):
    start_date, end_date = parse_dates(request)
    exporter = ReportExporter(start_date, end_date)
    return exporter.export_sales_csv()


@staff_member_required
def export_sales_excel(request):
    start_date, end_date = parse_dates(request)
    exporter = ReportExporter(start_date, end_date)
    return exporter.export_sales_excel()


@staff_member_required
def export_expenses_csv(request):
    start_date, end_date = parse_dates(request)
    exporter = ReportExporter(start_date, end_date)
    return exporter.export_expenses_csv()


@staff_member_required
def export_expenses_excel(request):
    start_date, end_date = parse_dates(request)
    exporter = ReportExporter(start_date, end_date)
    return exporter.export_expenses_excel()


@staff_member_required
def export_production_csv(request):
    start_date, end_date = parse_dates(request)
    exporter = ReportExporter(start_date, end_date)
    return exporter.export_production_csv()


@staff_member_required
def export_production_excel(request):
    start_date, end_date = parse_dates(request)
    exporter = ReportExporter(start_date, end_date)
    return exporter.export_production_excel()


@staff_member_required
def export_customer_ledger(request):
    start_date, end_date = parse_dates(request)
    customer_id = request.GET.get('customer_id')
    exporter = ReportExporter(start_date, end_date)
    return exporter.export_customer_ledger_excel(customer_id)


@staff_member_required
def export_inventory(request):
    exporter = ReportExporter()
    return exporter.export_inventory_excel()


# ==================== PDF GENERATION VIEWS ====================

@staff_member_required
def generate_invoice(request, supply_id):
    """Generate Invoice PDF for a SupplyLog."""
    supply = get_object_or_404(SupplyLog, pk=supply_id)
    generator = InvoiceGenerator()
    return generator.generate(supply)


@staff_member_required
def generate_waybill(request, supply_id):
    """Generate Waybill PDF for a SupplyLog."""
    supply = get_object_or_404(SupplyLog, pk=supply_id)
    generator = WaybillGenerator()
    return generator.generate(supply)


@staff_member_required
def generate_receipt(request, payment_id):
    """Generate Receipt PDF for a Payment."""
    payment = get_object_or_404(Payment, pk=payment_id)
    generator = ReceiptGenerator()
    return generator.generate(payment)


@staff_member_required
def generate_customer_statement(request, customer_id):
    """Generate Customer Statement PDF."""
    customer = get_object_or_404(Customer, pk=customer_id)
    start_date, end_date = parse_dates(request)
    generator = CustomerStatementGenerator()
    return generator.generate(customer, start_date, end_date)


@staff_member_required
def generate_proforma(request, order_id):
    """Generate Proforma Invoice PDF for a Sales Order."""
    order = get_object_or_404(SalesOrder, pk=order_id)
    generator = ProformaInvoiceGenerator()
    return generator.generate(order)