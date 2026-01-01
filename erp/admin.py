from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponse
from unfold.admin import ModelAdmin
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from .models import (
    User, Material, BlockType, PaymentAccount, BusinessRules,
    Team, Machine, Customer, Site, Employee,
    Vendor, ProcurementLog, Truck, ProductionLog,
    Payment, SalesOrder, SalesOrderItem, SupplyLog,
    ReturnLog, CashRefund,
    ExpenseCategory, Expense, BreakageLog, FuelLog
)


# ==================== RESTRICTED ADMIN MIXIN ====================
class RestrictedAdmin(ModelAdmin):
    """
    Base admin class with hardcoded permissions.
    Only superusers can edit or delete records.
    All staff can create and view.
    """

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return True

    def has_view_permission(self, request, obj=None):
        return True


# ==================== BULK EXPORT ACTIONS ====================

def export_to_excel(modeladmin, request, queryset):
    """Generic export action for any model."""
    model = queryset.model
    model_name = model._meta.verbose_name_plural.title().replace(" ", "_")

    wb = Workbook()
    ws = wb.active
    ws.title = model_name[:30]

    exclude_fields = ['id', 'created_at', 'updated_at']
    fields = [f for f in model._meta.fields if f.name not in exclude_fields]

    headers = [f.verbose_name.title() for f in fields]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    for obj in queryset:
        row = []
        for field in fields:
            value = getattr(obj, field.name)
            if hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, type(None))):
                value = str(value)
            if hasattr(value, 'quantize'):
                value = float(value)
            if hasattr(value, 'strftime'):
                value = value.strftime('%Y-%m-%d') if hasattr(value, 'day') else str(value)
            display_method = f'get_{field.name}_display'
            if hasattr(obj, display_method) and callable(getattr(obj, display_method)):
                try:
                    value = getattr(obj, display_method)()
                except:
                    pass
            row.append(value)
        ws.append(row)

    for column_cells in ws.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{model_name}_{timezone.now().date()}.xlsx"'
    wb.save(response)
    return response

export_to_excel.short_description = "📊 Export selected to Excel"


def export_supplies_detailed(modeladmin, request, queryset):
    """Detailed export for Supply Logs."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Supply_Log_Export"

    headers = [
        'Date', 'Customer', 'Phone', 'Site', 'Block Type',
        'Qty Loaded', 'Breakages', 'Qty Delivered', 'Unit Price (₦)',
        'Logistics Discount (₦)', 'Total Value (₦)', 'Delivery Type',
        'Truck', 'Driver', 'Pickup Auth By', 'Remark'
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    total_value = 0
    total_delivered = 0

    for log in queryset.select_related('customer', 'site', 'block_type', 'truck', 'driver'):
        ws.append([
            log.date.strftime('%Y-%m-%d'),
            log.customer.name,
            log.customer.phone,
            log.site.name,
            log.block_type.name,
            log.quantity_loaded,
            log.breakages,
            log.quantity_delivered,
            float(log.unit_price),
            float(log.logistics_discount),
            float(log.total_value),
            log.get_delivery_type_display(),
            log.truck.name if log.truck else 'N/A',
            log.driver.name if log.driver else 'N/A',
            log.pickup_authorized_by or 'N/A',
            log.remark or ''
        ])
        total_value += float(log.total_value)
        total_delivered += log.quantity_delivered

    summary_row = ws.max_row + 2
    ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=summary_row, column=8, value=total_delivered).font = Font(bold=True)
    ws.cell(row=summary_row, column=11, value=total_value).font = Font(bold=True)

    for column_cells in ws.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Supply_Log_Detailed_{timezone.now().date()}.xlsx"'
    wb.save(response)
    return response

export_supplies_detailed.short_description = "📊 Export selected (Detailed) to Excel"


def export_expenses_detailed(modeladmin, request, queryset):
    """Detailed export for Expenses."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Expense_Export"

    headers = [
        'Date', 'Category', 'Description', 'Amount (₦)',
        'Payment Account', 'Vendor', 'Truck', 'Machine',
        'Employee', 'Receipt No', 'Auto-Synced', 'Notes'
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="C62828", end_color="C62828", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    total = 0

    for exp in queryset.select_related('category', 'payment_account', 'vendor', 'truck', 'machine', 'employee'):
        ws.append([
            exp.date.strftime('%Y-%m-%d'),
            exp.category.name,
            exp.description,
            float(exp.amount),
            exp.payment_account.bank_name if exp.payment_account else 'N/A',
            exp.vendor.name if exp.vendor else 'N/A',
            exp.truck.name if exp.truck else 'N/A',
            exp.machine.name if exp.machine else 'N/A',
            exp.employee.name if exp.employee else 'N/A',
            exp.receipt_number or 'N/A',
            'Yes' if exp.is_auto_synced else 'No',
            exp.notes or ''
        ])
        total += float(exp.amount)

    summary_row = ws.max_row + 2
    ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=summary_row, column=4, value=total).font = Font(bold=True)

    for column_cells in ws.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Expenses_Detailed_{timezone.now().date()}.xlsx"'
    wb.save(response)
    return response

export_expenses_detailed.short_description = "📊 Export selected (Detailed) to Excel"


def export_customers_with_balance(modeladmin, request, queryset):
    """Export customers with their balance status."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Customer_Export"

    headers = [
        'Name', 'Phone', 'Email', 'Type', 'Office Address',
        'Account Balance (₦)', 'Status', 'Blocks Owed', 'Active'
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="6A1B9A", end_color="6A1B9A", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for cust in queryset:
        ws.append([
            cust.name,
            cust.phone,
            cust.email or 'N/A',
            cust.get_customer_type_display(),
            cust.office_address or 'N/A',
            float(cust.account_balance),
            cust.balance_status,
            cust.total_blocks_owed,
            'Yes' if cust.is_active else 'No'
        ])

    for column_cells in ws.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Customers_{timezone.now().date()}.xlsx"'
    wb.save(response)
    return response

export_customers_with_balance.short_description = "📊 Export selected to Excel"


def export_production_detailed(modeladmin, request, queryset):
    """Detailed export for Production Logs."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Production_Export"

    headers = [
        'Date', 'Team', 'Machine', 'Block Type', 'Qty Produced',
        'Breakages', 'Cement Used', 'Sharp Sand Used', 'Black Sand Used',
        'Labor Cost (₦)', 'Notes'
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="F57C00", end_color="F57C00", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    total_produced = 0
    total_labor = 0

    for log in queryset.select_related('team', 'machine', 'block_type'):
        ws.append([
            log.date.strftime('%Y-%m-%d'),
            log.team.name,
            log.machine.name,
            log.block_type.name,
            log.quantity_produced,
            log.breakages,
            float(log.cement_used),
            float(log.sharp_sand_used),
            float(log.black_sand_used),
            float(log.labor_cost),
            log.notes or ''
        ])
        total_produced += log.quantity_produced
        total_labor += float(log.labor_cost)

    summary_row = ws.max_row + 2
    ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=summary_row, column=5, value=total_produced).font = Font(bold=True)
    ws.cell(row=summary_row, column=10, value=total_labor).font = Font(bold=True)

    for column_cells in ws.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Production_Detailed_{timezone.now().date()}.xlsx"'
    wb.save(response)
    return response

export_production_detailed.short_description = "📊 Export selected (Detailed) to Excel"


def export_payments_detailed(modeladmin, request, queryset):
    """Detailed export for Payments."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Payment_Export"

    headers = [
        'Date', 'Customer', 'Phone', 'Amount (₦)', 'Method',
        'Payment Account', 'Reference', 'Remark'
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    total = 0

    for pmt in queryset.select_related('customer', 'payment_account'):
        ws.append([
            pmt.date.strftime('%Y-%m-%d'),
            pmt.customer.name,
            pmt.customer.phone,
            float(pmt.amount),
            pmt.get_method_display(),
            pmt.payment_account.bank_name if pmt.payment_account else 'N/A',
            pmt.reference or 'N/A',
            pmt.remark or ''
        ])
        total += float(pmt.amount)

    summary_row = ws.max_row + 2
    ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=summary_row, column=4, value=total).font = Font(bold=True)

    for column_cells in ws.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Payments_{timezone.now().date()}.xlsx"'
    wb.save(response)
    return response

export_payments_detailed.short_description = "📊 Export selected to Excel"


def export_procurement_detailed(modeladmin, request, queryset):
    """Detailed export for Procurement Logs."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Procurement_Export"

    headers = [
        'Date', 'Material', 'Vendor', 'Quantity', 'Unit Price (₦)',
        'Total Cost (₦)', 'Payment Account', 'Remark'
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="00695C", end_color="00695C", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    total = 0

    for log in queryset.select_related('material', 'vendor', 'payment_account'):
        ws.append([
            log.date.strftime('%Y-%m-%d'),
            log.material.get_name_display(),
            log.vendor.name if log.vendor else 'N/A',
            float(log.quantity),
            float(log.unit_price),
            float(log.total_cost),
            log.payment_account.bank_name if log.payment_account else 'N/A',
            log.remark or ''
        ])
        total += float(log.total_cost)

    summary_row = ws.max_row + 2
    ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=summary_row, column=6, value=total).font = Font(bold=True)

    for column_cells in ws.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Procurement_{timezone.now().date()}.xlsx"'
    wb.save(response)
    return response

export_procurement_detailed.short_description = "📊 Export selected to Excel"


def export_returns_detailed(modeladmin, request, queryset):
    """Detailed export for Return Logs with transformation info."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Returns_Export"

    headers = [
        'Date', 'Customer', 'Site', 'Original Block', 'Qty Returned',
        'Condition', 'Restocked As', 'Credit Customer', 'Unit Price (₦)',
        'Restocking Fee (₦)', 'Credit Value (₦)', 'Reason', 'Approved By'
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="7B1FA2", end_color="7B1FA2", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    total_credit = 0
    total_qty = 0

    for ret in queryset.select_related('customer', 'site', 'block_type', 'restock_as', 'approved_by'):
        restock_target = ret.restock_as.name if ret.restock_as else ret.block_type.name
        ws.append([
            ret.date.strftime('%Y-%m-%d'),
            ret.customer.name,
            ret.site.name,
            ret.block_type.name,
            ret.quantity_returned,
            ret.get_condition_display(),
            restock_target,
            'Yes' if ret.credit_customer else 'No',
            float(ret.unit_price),
            float(ret.restocking_fee),
            float(ret.credit_value),
            ret.reason[:50] + '...' if len(ret.reason) > 50 else ret.reason,
            ret.approved_by.username if ret.approved_by else 'N/A'
        ])
        total_credit += float(ret.credit_value)
        total_qty += ret.quantity_returned

    summary_row = ws.max_row + 2
    ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=summary_row, column=5, value=total_qty).font = Font(bold=True)
    ws.cell(row=summary_row, column=11, value=total_credit).font = Font(bold=True)

    for column_cells in ws.columns:
        length = max(len(str(cell.value or "")) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Returns_Detailed_{timezone.now().date()}.xlsx"'
    wb.save(response)
    return response

export_returns_detailed.short_description = "📊 Export selected (Detailed) to Excel"


# ==================== ADMIN CLASSES ====================

# --- Day 2: Authentication ---
@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Role Information", {"fields": ("role",)}),
    )
    list_display = ["username", "email", "role", "is_active", "is_staff", "date_joined"]
    list_filter = ["role", "is_active", "is_staff", "date_joined"]
    search_fields = ["username", "email", "first_name", "last_name"]
    date_hierarchy = "date_joined"


# --- Day 3: Materials & Constants ---
@admin.register(Material)
class MaterialAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["name", "current_stock", "unit_price", "low_stock_threshold", "is_low_stock", "is_active"]
    list_filter = ["name", "is_active"]
    search_fields = ["name"]
    ordering = ["name"]

    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = "Low Stock?"


@admin.register(BlockType)
class BlockTypeAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["name", "current_stock", "selling_price", "blocks_per_bag", "is_half_block", "is_low_stock", "is_active"]
    list_filter = ["is_active", "is_half_block"]
    list_editable = ["selling_price"]
    search_fields = ["name"]
    ordering = ["name"]

    fieldsets = (
        ("Inventory", {"fields": ("name", "current_stock", "low_stock_threshold", "selling_price", "is_active")}),
        ("Block Type", {"fields": ("is_half_block",), "description": "Check this if this is a half/broken block type"}),
        ("Production Recipe", {"fields": ("blocks_per_bag", "sand_ratio", "batch_size"), "description": "Set to 0 for non-produced items like Half Blocks"}),
        ("Variable Costs (Per Block)", {"fields": ("operator_rate", "loader_rate", "stacking_rate", "logistics_rate")}),
    )

    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = "Low Stock?"

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return False


@admin.register(PaymentAccount)
class PaymentAccountAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["bank_name", "account_name", "account_number", "is_active"]
    list_filter = ["bank_name", "is_active"]
    search_fields = ["bank_name", "account_name", "account_number"]
    ordering = ["bank_name"]


@admin.register(BusinessRules)
class BusinessRulesAdmin(RestrictedAdmin):
    list_display = ["name", "sand_cost", "diesel_power_cost", "miscellaneous_cost", "updated_at"]

    fieldsets = (
        ("Material Costs (Per Batch)", {"fields": ("name", "sand_cost", "black_sand_cost", "water_base_cost")}),
        ("Overhead Costs (Per Batch)", {"fields": ("diesel_power_cost", "miscellaneous_cost")}),
    )

    def has_add_permission(self, request):
        return not BusinessRules.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# --- Day 4: Teams, Machines, Customers, Employees ---

@admin.register(Team)
class TeamAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["name", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["name"]


@admin.register(Machine)
class MachineAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["name", "machine_type", "assigned_team", "status", "is_active"]
    list_filter = ["machine_type", "status", "assigned_team", "is_active"]
    search_fields = ["name", "notes"]
    ordering = ["name"]

    fieldsets = (
        ("Machine Info", {"fields": ("name", "machine_type", "status", "is_active")}),
        ("Assignment", {"fields": ("assigned_team",)}),
        ("Notes", {"fields": ("notes",)}),
    )


class SiteInline(admin.TabularInline):
    model = Site
    extra = 1
    fields = ["name", "address", "contact_person", "contact_phone", "is_outside_town", "blocks_owed", "is_active"]


@admin.register(Customer)
class CustomerAdmin(RestrictedAdmin):
    actions = [export_customers_with_balance]
    list_display = ["name", "phone", "customer_type", "account_balance", "balance_status", "total_blocks_owed", "is_active", "pdf_actions"]
    list_filter = ["customer_type", "is_active", "created_at"]
    search_fields = ["name", "phone", "email", "office_address"]
    ordering = ["name"]
    date_hierarchy = "created_at"
    inlines = [SiteInline]

    fieldsets = (
        ("Basic Info", {"fields": ("name", "phone", "email", "customer_type", "is_active")}),
        ("Address", {"fields": ("office_address",)}),
        ("Financial", {"fields": ("account_balance",)}),
        ("Notes", {"fields": ("notes",)}),
    )

    def balance_status(self, obj):
        return obj.balance_status
    balance_status.short_description = "Status"

    def total_blocks_owed(self, obj):
        return obj.total_blocks_owed
    total_blocks_owed.short_description = "Blocks Owed"

    def pdf_actions(self, obj):
        statement_url = reverse('select_statement_date', args=[obj.pk])
        return format_html(
            '<a href="{}" style="padding:3px 8px; background:#6A1B9A; color:white; border-radius:4px; text-decoration:none; font-size:11px;">📊 Statement</a>',
            statement_url
        )
    pdf_actions.short_description = "PDF"


@admin.register(Site)
class SiteAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["customer", "name", "is_outside_town", "blocks_owed", "is_active"]
    list_filter = ["customer", "is_outside_town", "is_active"]
    search_fields = ["name", "address", "customer__name", "contact_person", "contact_phone"]
    ordering = ["customer__name", "name"]
    autocomplete_fields = ["customer"]


@admin.register(Employee)
class EmployeeAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["name", "role", "team", "pay_type", "current_balance", "is_active"]
    list_filter = ["role", "team", "pay_type", "is_active"]
    search_fields = ["name", "phone"]
    ordering = ["name"]

    fieldsets = (
        ("Basic Info", {"fields": ("name", "phone", "role", "is_active")}),
        ("Assignment", {"fields": ("team", "pay_type")}),
        ("Financial", {"fields": ("current_balance",)}),
    )


# --- Day 5: Vendors, Procurement & Trucks ---

@admin.register(Vendor)
class VendorAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["name", "supply_type", "phone", "is_active"]
    list_filter = ["supply_type", "is_active"]
    search_fields = ["name", "phone", "address"]
    ordering = ["name"]


@admin.register(ProcurementLog)
class ProcurementLogAdmin(RestrictedAdmin):
    actions = [export_procurement_detailed]
    list_display = ["date", "material", "quantity", "total_cost", "unit_price", "vendor", "payment_account", "expense_synced", "recorded_by"]
    list_filter = ["date", "material", "vendor", "payment_account"]
    search_fields = ["material__name", "vendor__name", "remark"]
    date_hierarchy = "date"
    readonly_fields = ["unit_price", "expense_entry"]
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["vendor"]

    fieldsets = (
        ("Purchase Info", {"fields": ("date", "vendor", "material")}),
        ("Quantity & Cost", {"fields": ("quantity", "total_cost", "unit_price")}),
        ("Payment", {"fields": ("payment_account", "remark")}),
        ("Auto-Sync Info (Read Only)", {"fields": ("expense_entry",), "classes": ("collapse",)}),
    )

    def expense_synced(self, obj):
        return obj.expense_entry is not None
    expense_synced.boolean = True
    expense_synced.short_description = "Synced to Expense?"

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


@admin.register(Truck)
class TruckAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["name", "plate_number", "driver", "status", "fuel_type", "benchmark_fuel", "expected_trips", "is_active"]
    list_filter = ["status", "fuel_type", "is_active"]
    search_fields = ["name", "plate_number", "driver__name"]
    ordering = ["name"]
    autocomplete_fields = ["driver"]

    fieldsets = (
        ("Vehicle Info", {"fields": ("name", "plate_number", "driver", "status", "is_active")}),
        ("Fuel Benchmarks", {"fields": ("fuel_type", "fuel_capacity", "benchmark_fuel", "expected_trips")}),
    )


# --- Day 6: Production Module ---

@admin.register(ProductionLog)
class ProductionLogAdmin(RestrictedAdmin):
    actions = [export_production_detailed]
    list_display = ["date", "team", "machine", "block_type", "quantity_produced", "breakages", "cement_used", "sharp_sand_used", "labor_cost", "recorded_by"]
    list_filter = ["date", "team", "machine", "block_type"]
    search_fields = ["team__name", "machine__name", "block_type__name", "notes"]
    date_hierarchy = "date"
    readonly_fields = ["sharp_sand_used", "labor_cost"]
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["team", "machine", "block_type"]

    fieldsets = (
        ("Production Details", {"fields": ("date", "team", "machine", "block_type")}),
        ("Output", {"fields": ("quantity_produced", "breakages")}),
        ("Materials Used (Manual)", {"fields": ("cement_used", "black_sand_used")}),
        ("Auto-Calculated", {"fields": ("sharp_sand_used", "labor_cost")}),
        ("Notes", {"fields": ("notes",)}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


# --- Day 7: Ledger System (Payments, Orders, Supplies) ---

@admin.register(Payment)
class PaymentAdmin(RestrictedAdmin):
    actions = [export_payments_detailed]
    list_display = ["date", "customer", "amount", "method", "payment_account", "reference", "recorded_by", "pdf_actions"]
    list_filter = ["date", "method", "payment_account", "customer"]
    search_fields = ["customer__name", "customer__phone", "reference", "remark"]
    date_hierarchy = "date"
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["customer", "payment_account"]

    fieldsets = (
        ("Payment Info", {"fields": ("date", "customer", "amount")}),
        ("Payment Details", {"fields": ("method", "payment_account", "reference")}),
        ("Notes", {"fields": ("remark",)}),
    )

    def pdf_actions(self, obj):
        receipt_url = reverse('generate_receipt', args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank" style="padding:3px 8px; background:#2E7D32; color:white; border-radius:4px; text-decoration:none; font-size:11px;">🧾 Receipt</a>',
            receipt_url
        )
    pdf_actions.short_description = "PDF"

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 1
    fields = ["block_type", "quantity_requested", "agreed_price", "quantity_supplied", "line_total_display"]
    readonly_fields = ["agreed_price", "quantity_supplied", "line_total_display"]
    autocomplete_fields = ["block_type"]

    def line_total_display(self, obj):
        if obj.pk:
            return f"₦{obj.line_total:,.2f}"
        return "-"
    line_total_display.short_description = "Line Total"


@admin.register(SalesOrder)
class SalesOrderAdmin(RestrictedAdmin):
    list_display = [
        "__str__", "date", "customer", "site", "status",
        "total_quantity_ordered", "total_quantity_supplied",
        "supply_progress_display", "total_value_display",
        "valid_until", "is_valid_display", "pdf_actions"
    ]
    list_filter = ["date", "status", "customer"]
    search_fields = ["customer__name", "customer__phone", "site__name", "notes"]
    date_hierarchy = "date"
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["customer", "site"]
    inlines = [SalesOrderItemInline]
    readonly_fields = ["valid_until"]

    fieldsets = (
        ("Order Info", {
            "fields": ("date", "customer", "site", "status")
        }),
        ("Pricing Adjustments (Per Block)", {
            "fields": ("surcharge_per_block", "discount_per_block", "discount_reason"),
            "description": "These amounts are added/subtracted PER BLOCK to calculate the agreed price for each item."
        }),
        ("Validity", {
            "fields": ("valid_until",),
            "description": "Auto-set to 14 days from order date."
        }),
        ("Notes", {
            "fields": ("notes",)
        }),
    )

    def total_quantity_ordered(self, obj):
        return obj.total_quantity_ordered
    total_quantity_ordered.short_description = "Qty Ordered"

    def total_quantity_supplied(self, obj):
        return obj.total_quantity_supplied
    total_quantity_supplied.short_description = "Qty Supplied"

    def supply_progress_display(self, obj):
        progress = obj.supply_progress
        if progress == 100:
            return format_html('<span style="color: green; font-weight: bold;">{}%</span>', progress)
        elif progress > 0:
            return format_html('<span style="color: orange; font-weight: bold;">{}%</span>', progress)
        return f"{progress}%"
    supply_progress_display.short_description = "Progress"

    def total_value_display(self, obj):
        return f"₦{obj.total_value:,.2f}"
    total_value_display.short_description = "Total Value"

    def is_valid_display(self, obj):
        return obj.is_valid
    is_valid_display.boolean = True
    is_valid_display.short_description = "Valid?"

    def pdf_actions(self, obj):
        proforma_url = reverse('generate_proforma', args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank" style="padding:3px 8px; background:#D4AF37; color:#254451; border-radius:4px; text-decoration:none; font-size:11px; font-weight:bold;">📋 Proforma</a>',
            proforma_url
        )
    pdf_actions.short_description = "PDF"

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SalesOrderItem)
class SalesOrderItemAdmin(RestrictedAdmin):
    list_display = ["order", "block_type", "quantity_requested", "agreed_price", "quantity_supplied"]
    list_filter = ["block_type", "order__customer"]
    search_fields = ["order__customer__name", "block_type__name"]
    autocomplete_fields = ["order", "block_type"]

    def has_module_permission(self, request):
        return False


@admin.register(SupplyLog)
class SupplyLogAdmin(RestrictedAdmin):
    list_display = [
        "date", "delivery_type", "customer", "site", "block_type",
        "quantity_loaded", "breakages", "quantity_delivered",
        "unit_price", "logistics_discount", "total_value",
        "logistics_income",  # <--- NEW: Transport Income
        "order_link", "truck", "pdf_actions"
    ]
    list_filter = [
        "date", "delivery_type", "customer", "site",
        "block_type", "truck", "sales_order"
    ]
    search_fields = [
        "customer__name", "customer__phone",
        "site__name", "pickup_authorized_by",
        "remark", "driver__name"
    ]
    date_hierarchy = "date"
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["customer", "site", "truck", "driver", "sales_order", "order_item", "block_type"]
    readonly_fields = ["quantity_delivered", "total_value", "unit_price", "logistics_income"]

    fieldsets = (
        ("Delivery Info", {
            "fields": ("date", "delivery_type")
        }),
        ("Customer & Site", {
            "fields": ("customer", "site")
        }),
        ("Link to Sales Order (Optional)", {
            "fields": ("sales_order", "order_item"),
            "description": "If linked to an order, unit_price auto-populates from the agreed price."
        }),
        ("Product (Auto-filled if linked to order)", {
            "fields": ("block_type",)
        }),
        ("Quantities", {
            "fields": ("quantity_loaded", "breakages", "quantity_delivered")
        }),
        ("Pricing (Auto-calculated)", {
            "fields": ("unit_price", "logistics_discount", "total_value"),
            "description": "Unit price is auto-populated from Sales Order or Block Type selling price."
        }),
        ("Transport Income (Internal)", {  # <--- NEW SECTION
            "fields": ("logistics_income",),
            "description": "Revenue attributed to Jafan Transport (based on logistics rate + surcharges)."
        }),
        ("Logistics (For Company Delivery)", {
            "fields": ("truck", "driver"),
            "description": "Required when Delivery Type is 'Company Delivery'"
        }),
        ("Self-Pickup Info", {
            "fields": ("pickup_authorized_by",),
            "description": "Required when Delivery Type is 'Customer Self-Pickup'"
        }),
        ("Notes", {
            "fields": ("remark",)
        }),
    )

    def order_link(self, obj):
        if obj.sales_order:
            return format_html(
                '<a href="/admin/erp/salesorder/{}/change/">SO-{}</a>',
                obj.sales_order.pk,
                f'{obj.sales_order.pk:05d}'
            )
        return "-"
    order_link.short_description = "Order"

    def pdf_actions(self, obj):
        invoice_url = reverse('generate_invoice', args=[obj.pk])
        waybill_url = reverse('generate_waybill', args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank" style="padding:3px 8px; background:#2E7D32; color:white; border-radius:4px; text-decoration:none; font-size:11px; margin-right:4px;">📄 Invoice</a>'
            '<a href="{}" target="_blank" style="padding:3px 8px; background:#1565C0; color:white; border-radius:4px; text-decoration:none; font-size:11px;">🚚 Waybill</a>',
            invoice_url, waybill_url
        )
    pdf_actions.short_description = "PDF"

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


# --- Day 8: Returns & Refunds ---

@admin.register(ReturnLog)
class ReturnLogAdmin(RestrictedAdmin):
    actions = [export_returns_detailed]
    list_display = [
        "date", "customer", "site", "block_type", "quantity_returned",
        "condition", "restock_target", "credit_customer", "credit_value",
        "approved_by"
    ]
    list_filter = ["date", "condition", "credit_customer", "block_type", "customer", "restock_as"]
    search_fields = ["customer__name", "customer__phone", "site__name", "reason"]
    date_hierarchy = "date"
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["customer", "site", "original_supply", "block_type", "approved_by", "restock_as"]
    readonly_fields = ["credit_value"]

    fieldsets = (
        ("Return Details", {"fields": ("date", "customer", "site", "original_supply")}),
        ("Product Info", {"fields": ("block_type", "quantity_returned", "condition")}),
        ("Inventory Transformation", {
            "fields": ("restock_as",),
            "description": "Select ONLY if the returned block is now a different type (e.g., Whole → Half). Leave empty to restock as original type."
        }),
        ("Customer Credit", {
            "fields": ("credit_customer", "unit_price", "restocking_fee", "credit_value"),
            "description": "⚠️ IMPORTANT: Only check 'Credit Customer' if this is a genuine refund. "
                          "For excess blocks from delivery or breakage conversions, leave unchecked."
        }),
        ("Approval", {"fields": ("reason", "approved_by")}),
    )

    def restock_target(self, obj):
        if obj.condition == 'DAMAGED':
            return "❌ No Restock"
        target = obj.restock_as if obj.restock_as else obj.block_type
        return f"→ {target.name}"
    restock_target.short_description = "Restocked To"

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


@admin.register(CashRefund)
class CashRefundAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["date", "customer", "amount", "payment_account", "approved_by", "recorded_by"]
    list_filter = ["date", "payment_account", "customer"]
    search_fields = ["customer__name", "customer__phone", "reason"]
    date_hierarchy = "date"
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["customer", "payment_account", "approved_by"]

    fieldsets = (
        ("Refund Details", {"fields": ("date", "customer", "amount")}),
        ("Payment", {"fields": ("payment_account",)}),
        ("Approval", {"fields": ("reason", "approved_by")}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


# --- Day 9: Expenses Module ---

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(RestrictedAdmin):
    actions = [export_to_excel]
    list_display = ["name", "description", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    ordering = ["name"]


@admin.register(Expense)
class ExpenseAdmin(RestrictedAdmin):
    actions = [export_expenses_detailed]
    list_display = ["date", "category", "description", "amount", "payment_account", "is_auto_synced", "vendor", "truck", "employee", "recorded_by"]
    list_filter = ["date", "category", "payment_account", "is_auto_synced", "vendor", "truck", "requires_approval"]
    search_fields = ["description", "category__name", "vendor__name", "employee__name", "receipt_number", "notes"]
    date_hierarchy = "date"
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["category", "payment_account", "vendor", "truck", "machine", "employee", "approved_by"]
    readonly_fields = ["is_auto_synced"]

    fieldsets = (
        ("Expense Details", {"fields": ("date", "category", "description", "amount")}),
        ("Payment", {"fields": ("payment_account", "receipt_number")}),
        ("Related To (Optional)", {
            "fields": ("vendor", "truck", "machine", "employee"),
            "description": "Link expense to vendor, vehicle, machine, or employee if applicable"
        }),
        ("Approval (For Large Expenses)", {
            "fields": ("requires_approval", "approved_by"),
            "classes": ("collapse",)
        }),
        ("System Info", {
            "fields": ("is_auto_synced",),
            "classes": ("collapse",),
            "description": "Auto-synced expenses are created automatically from Procurement"
        }),
        ("Notes", {"fields": ("notes",)}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


@admin.register(BreakageLog)
class BreakageLogAdmin(RestrictedAdmin):
    list_display = [
        "date", "block_type", "quantity_broken", "reason",
        "convert_to_half", "half_block_type", "quantity_salvaged",
        "approved_by", "recorded_by"
    ]
    list_filter = ["date", "reason", "convert_to_half", "block_type", "approved_by"]
    search_fields = ["block_type__name", "description"]
    date_hierarchy = "date"
    ordering = ["-date", "-created_at"]
    autocomplete_fields = ["block_type", "half_block_type", "approved_by"]
    readonly_fields = ["recorded_by"]

    fieldsets = (
        ("Breakage Details", {
            "fields": ("date", "block_type", "quantity_broken")
        }),
        ("Reason", {
            "fields": ("reason", "description")
        }),
        ("Half Block Conversion", {
            "fields": ("convert_to_half", "half_block_type", "quantity_salvaged"),
            "description": "If broken blocks can be salvaged as half blocks, check 'Convert to half' and select the target half block type. Quantity salvaged is auto-suggested as 2x broken quantity."
        }),
        ("Approval", {
            "fields": ("approved_by",)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()


# --- Day 15: Diesel & Transport Management (NEW) ---

@admin.register(FuelLog)
class FuelLogAdmin(RestrictedAdmin):
    list_display = ["date", "destination_display", "quantity", "total_cost", "dispensed_by"]
    list_filter = ["date", "destination_type", "truck", "machine"]
    search_fields = ["truck__name", "machine__name", "remark"]
    date_hierarchy = "date"
    autocomplete_fields = ["truck", "machine"]
    readonly_fields = ["cost_per_liter", "total_cost", "dispensed_by"]

    fieldsets = (
        ("Dispense Details", {
            "fields": ("date", "destination_type", "truck", "machine")
        }),
        ("Volume & Cost", {
            "fields": ("quantity", "cost_per_liter", "total_cost")
        }),
        ("Metrics (Optional)", {
            "fields": ("engine_hours",)
        }),
        ("Notes", {
            "fields": ("remark", "dispensed_by")
        }),
    )

    def destination_display(self, obj):
        if obj.truck:
            return f"🚛 {obj.truck.name}"
        if obj.machine:
            return f"⚙️ {obj.machine.name}"
        return "-"
    destination_display.short_description = "Destination"

    def save_model(self, request, obj, form, change):
        if not obj.dispensed_by:
            obj.dispensed_by = request.user
        super().save_model(request, obj, form, change)