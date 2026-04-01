# erp/services.py
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone


class BlockIndustryPLService:
    """
    Accurate Profit & Loss calculation for Block Industry.
    Uses industry-standard accrual accounting with proper COGS calculation.
    
    Revenue = Sales (from SupplyLog + QuickSale)
    COGS = Cost of Goods Sold (frozen WAC × qty at time of sale)
    Gross Profit = Revenue - COGS
    Operating Expenses = All expenses EXCLUDING raw materials (already in COGS)
    Net Profit = Gross Profit - Operating Expenses
    """
    
    def __init__(self, start_date, end_date, business_unit='BLOCK'):
        self.start_date = start_date
        self.end_date = end_date
        self.business_unit = business_unit
    
    def get_full_pl(self):
        """Returns complete P&L breakdown"""
        
        revenue = self._calculate_revenue()
        cogs = self._calculate_cogs()
        gross_profit = revenue['total'] - cogs['total']
        gross_margin = (gross_profit / revenue['total'] * 100) if revenue['total'] > 0 else Decimal('0')
        
        expenses = self._calculate_operating_expenses()
        
        net_profit = gross_profit - expenses['total']
        net_margin = (net_profit / revenue['total'] * 100) if revenue['total'] > 0 else Decimal('0')
        
        return {
            'period': {
                'start': self.start_date,
                'end': self.end_date,
            },
            'revenue': revenue,
            'cogs': cogs,
            'gross_profit': gross_profit,
            'gross_margin_percent': round(gross_margin, 2),
            'operating_expenses': expenses,
            'net_profit': net_profit,
            'net_margin_percent': round(net_margin, 2),
        }
    
    def _calculate_revenue(self):
        """Calculate all revenue streams from actual sales"""
        from .models import SupplyLog, QuickSale
        
        supplies = SupplyLog.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        )
        
        # Block Sales Revenue from SupplyLog
        sales_data = supplies.aggregate(
            block_sales=Sum('total_value'),
            total_quantity=Sum('quantity_delivered'),
            logistics=Sum('logistics_income')
        )
        
        block_sales = sales_data['block_sales'] or Decimal('0')
        logistics_income = sales_data['logistics'] or Decimal('0')
        total_quantity = sales_data['total_quantity'] or 0
        
        # Quick Sales Revenue (walk-in cash sales)
        quick_sales = QuickSale.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        )
        quick_sales_data = quick_sales.aggregate(
            total=Sum('total_amount'),
            quantity=Sum('quantity')
        )
        quick_sales_revenue = quick_sales_data['total'] or Decimal('0')
        quick_sales_quantity = quick_sales_data['quantity'] or 0
        
        # Combined block sales
        total_block_sales = block_sales + quick_sales_revenue
        total_blocks_sold = total_quantity + quick_sales_quantity
        
        # Breakdown by block type (SupplyLog)
        by_block_type = list(supplies.values('block_type__name').annotate(
            revenue=Sum('total_value'),
            quantity=Sum('quantity_delivered'),
            cogs=Sum('cost_of_goods_sold'),
            profit=Sum('gross_profit_on_sale')
        ).order_by('-revenue'))
        
        # Add QuickSale breakdown
        quick_by_block = quick_sales.values('block_type__name').annotate(
            revenue=Sum('total_amount'),
            quantity=Sum('quantity')
        )
        
        # Merge QuickSale into by_block_type
        for qs_item in quick_by_block:
            found = False
            for bt_item in by_block_type:
                if bt_item['block_type__name'] == qs_item['block_type__name']:
                    bt_item['revenue'] = (bt_item['revenue'] or Decimal('0')) + (qs_item['revenue'] or Decimal('0'))
                    bt_item['quantity'] = (bt_item['quantity'] or 0) + (qs_item['quantity'] or 0)
                    found = True
                    break
            if not found:
                by_block_type.append({
                    'block_type__name': qs_item['block_type__name'],
                    'revenue': qs_item['revenue'],
                    'quantity': qs_item['quantity'],
                    'cogs': None,  # QuickSale doesn't track COGS directly
                    'profit': None
                })
        
        return {
            'block_sales': total_block_sales,
            'supply_log_sales': block_sales,
            'quick_sales': quick_sales_revenue,
            'logistics_income': logistics_income,
            'total': total_block_sales,  # Logistics goes to Transport, not Block P&L
            'total_quantity_sold': total_blocks_sold,
            'by_block_type': by_block_type,
        }
    
    def _calculate_cogs(self):
        """
        Calculate Cost of Goods Sold.
        Uses the frozen cost_of_goods_sold from SupplyLog (WAC at time of sale).
        For QuickSale, we estimate COGS using current WAC from BlockType.
        """
        from .models import SupplyLog, QuickSale
        
        supplies = SupplyLog.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        )
        
        cogs_data = supplies.aggregate(
            total_cogs=Sum('cost_of_goods_sold'),
            total_gross_profit=Sum('gross_profit_on_sale')
        )
        
        supply_cogs = cogs_data['total_cogs'] or Decimal('0')
        
        # QuickSale COGS (estimate using current WAC)
        quick_sales = QuickSale.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('block_type')
        
        quick_sale_cogs = Decimal('0')
        for qs in quick_sales:
            # Use WAC from block type
            wac = qs.block_type.weighted_average_cost or Decimal('0')
            quick_sale_cogs += wac * qs.quantity
        
        total_cogs = supply_cogs + quick_sale_cogs
        
        # Breakdown by block type
        by_block_type = list(supplies.values('block_type__name').annotate(
            quantity=Sum('quantity_delivered'),
            cogs=Sum('cost_of_goods_sold')
        ).order_by('-cogs'))
        
        return {
            'total': total_cogs,
            'supply_log_cogs': supply_cogs,
            'quick_sale_cogs': quick_sale_cogs,
            'by_block_type': by_block_type,
        }
    
    def _calculate_operating_expenses(self):
        """
        Calculate operating expenses EXCLUDING raw materials.
        Raw materials are already accounted for in COGS via production cost.
        """
        from .models import Expense, BankCharge, ExpenseCategory
        
        # Get raw materials category to exclude
        raw_material_categories = ExpenseCategory.objects.filter(
            Q(name__icontains='raw material') |
            Q(name__icontains='materials') |
            Q(name__icontains='cement') |
            Q(name__icontains='sand')
        ).values_list('pk', flat=True)
        
        # Get all expenses EXCLUDING raw materials
        expenses = Expense.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date,
            business_unit=self.business_unit
        ).exclude(
            category__pk__in=raw_material_categories
        ).exclude(
            is_auto_synced=True  # Exclude any remaining auto-synced entries
        )
        
        # Group by category
        by_category = expenses.values('category__name').annotate(
            total=Sum('amount')
        ).order_by('-total')
        
        expenses_total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Bank Charges (separate model)
        bank_charges = BankCharge.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date,
            account__business_unit=self.business_unit
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Build breakdown dict
        breakdown = {item['category__name']: item['total'] for item in by_category}
        if bank_charges > 0:
            breakdown['Bank Charges'] = bank_charges
        
        total = expenses_total + bank_charges
        
        return {
            'total': total,
            'breakdown': breakdown,
            'expenses_subtotal': expenses_total,
            'bank_charges': bank_charges,
        }
    
    def get_summary(self):
        """Returns simplified summary for dashboard cards"""
        pl = self.get_full_pl()
        return {
            'revenue': pl['revenue']['total'],
            'cogs': pl['cogs']['total'],
            'gross_profit': pl['gross_profit'],
            'gross_margin': pl['gross_margin_percent'],
            'expenses': pl['operating_expenses']['total'],
            'net_profit': pl['net_profit'],
            'net_margin': pl['net_margin_percent'],
        }


class CashFlowService:
    """
    Cash Flow Statement - tracks actual money movement.
    Different from P&L which uses accrual accounting.
    
    Cash In = Customer Payments + Sand Sales + Quick Sales + Loan Repayments + Transfers In
    Cash Out = Procurements (paid) + Expenses (paid) + Vendor Payments + Team Payments + Loans Given + Refunds + Bank Charges + Transfers Out
    """
    
    def __init__(self, start_date, end_date, account=None, business_unit=None):
        self.start_date = start_date
        self.end_date = end_date
        self.account = account  # Filter by specific account (optional)
        self.business_unit = business_unit  # Filter by business unit (optional)
    
    def get_all_transactions(self):
        """Get all cash transactions sorted by date"""
        transactions = []
        
        # Gather all transaction types
        transactions.extend(self._get_customer_payments())
        transactions.extend(self._get_sand_sales())
        transactions.extend(self._get_quick_sales())       # NEW
        transactions.extend(self._get_loan_repayments())
        transactions.extend(self._get_procurement_payments())
        transactions.extend(self._get_expense_payments())
        transactions.extend(self._get_vendor_payments())
        transactions.extend(self._get_team_payments())
        transactions.extend(self._get_loans_given())
        transactions.extend(self._get_cash_refunds())
        transactions.extend(self._get_bank_charges())
        transactions.extend(self._get_transfers_in())
        transactions.extend(self._get_transfers_out())
        transactions.extend(self._get_intercompany_collections())
        transactions.extend(self._get_intercompany_repayments())
        
        # Sort by date, then by created_at if available
        transactions.sort(key=lambda x: (x['date'], x.get('created_at', x['date'])))
        
        return transactions
    
    def get_cash_flow_statement(self):
        """Returns complete cash flow statement with summary"""
        transactions = self.get_all_transactions()
        
        # Calculate totals for THIS period
        total_inflow = sum(t['inflow'] or Decimal('0') for t in transactions)
        total_outflow = sum(t['outflow'] or Decimal('0') for t in transactions)
        net_cash_flow = total_inflow - total_outflow
        
        # Get ACCURATE opening balance (historical calculation)
        opening_balance = self._get_opening_balance()
        closing_balance = opening_balance + net_cash_flow
        
        # Group by category
        inflow_by_category = {}
        outflow_by_category = {}
        
        for t in transactions:
            cat = t['category']
            if t['inflow']:
                inflow_by_category[cat] = inflow_by_category.get(cat, Decimal('0')) + t['inflow']
            if t['outflow']:
                outflow_by_category[cat] = outflow_by_category.get(cat, Decimal('0')) + t['outflow']
        
        return {
            'period': {
                'start': self.start_date,
                'end': self.end_date,
            },
            'opening_balance': opening_balance,
            'transactions': transactions,
            'inflow_by_category': inflow_by_category,
            'outflow_by_category': outflow_by_category,
            'total_inflow': total_inflow,
            'total_outflow': total_outflow,
            'net_cash_flow': net_cash_flow,
            'closing_balance': closing_balance,
        }
    
    def _get_opening_balance(self):
        """
        Calculate opening balance accurately by summing 
        net cash flow of all transactions BEFORE start_date.
        
        Opening Balance = All Inflows before start_date - All Outflows before start_date
        """
        from .models import (
            Payment, ProcurementLog, Expense, VendorPayment,
            CashRefund, BankCharge, AccountTransfer, TeamPayment, 
            SandSale, Loan, LoanRepayment, QuickSale,
            CashCollection, CashRepayment
        )
        
        # ============================================================
        # INFLOWS (before start_date)
        # ============================================================
        
        # Customer Payments
        payments_filter = {'date__lt': self.start_date}
        if self.account:
            payments_filter['payment_account'] = self.account
        payments_in = Payment.objects.filter(
            **payments_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Transfers IN
        transfers_in_filter = {'date__lt': self.start_date}
        if self.account:
            transfers_in_filter['to_account'] = self.account
        transfers_in = AccountTransfer.objects.filter(
            **transfers_in_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Sand Sales
        sand_filter = {'date__lt': self.start_date}
        if self.account:
            sand_filter['payment_account'] = self.account
        sand_sales_in = SandSale.objects.filter(
            **sand_filter
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Quick Sales (NEW)
        quick_filter = {'date__lt': self.start_date}
        if self.account:
            quick_filter['payment_account'] = self.account
        quick_sales_in = QuickSale.objects.filter(
            **quick_filter
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Loan Repayments
        loan_rep_filter = {'date__lt': self.start_date}
        if self.account:
            loan_rep_filter['payment_account'] = self.account
        loan_repayments_in = LoanRepayment.objects.filter(
            **loan_rep_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Inter-Company Collections (money IN from C&C)
        icc_filter = {'date__lt': self.start_date}
        if self.account:
            icc_filter['receiving_account'] = self.account
        intercompany_collections_in = CashCollection.objects.filter(
            **icc_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total_inflows = payments_in + transfers_in + sand_sales_in + quick_sales_in + loan_repayments_in + intercompany_collections_in
        
        # ============================================================
        # OUTFLOWS (before start_date)
        # ============================================================
        
        # Paid Procurements
        proc_filter = {'date__lt': self.start_date, 'is_paid': True}
        if self.account:
            proc_filter['payment_account'] = self.account
        procurements_out = ProcurementLog.objects.filter(
            **proc_filter
        ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
        
        # Paid Expenses
        exp_filter = {'date__lt': self.start_date, 'is_paid': True}
        if self.account:
            exp_filter['payment_account'] = self.account
        if self.business_unit:
            exp_filter['business_unit'] = self.business_unit
        expenses_out = Expense.objects.filter(
            **exp_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Vendor Payments
        vp_filter = {'date__lt': self.start_date}
        if self.account:
            vp_filter['payment_account'] = self.account
        vendor_payments_out = VendorPayment.objects.filter(
            **vp_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Team Payments
        tp_filter = {'date__lt': self.start_date}
        if self.account:
            tp_filter['payment_account'] = self.account
        team_payments_out = TeamPayment.objects.filter(
            **tp_filter
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        
        # Cash Refunds
        refund_filter = {'date__lt': self.start_date}
        if self.account:
            refund_filter['payment_account'] = self.account
        refunds_out = CashRefund.objects.filter(
            **refund_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Bank Charges
        bc_filter = {'date__lt': self.start_date}
        if self.account:
            bc_filter['account'] = self.account
        if self.business_unit:
            bc_filter['account__business_unit'] = self.business_unit
        bank_charges_out = BankCharge.objects.filter(
            **bc_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Loans Given
        loans_filter = {'date__lt': self.start_date}
        if self.account:
            loans_filter['payment_account'] = self.account
        loans_given_out = Loan.objects.filter(
            **loans_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Transfers OUT
        transfers_out_filter = {'date__lt': self.start_date}
        if self.account:
            transfers_out_filter['from_account'] = self.account
        transfers_out = AccountTransfer.objects.filter(
            **transfers_out_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Inter-Company Repayments (money OUT to C&C)
        icr_filter = {'date__lt': self.start_date}
        if self.account:
            icr_filter['source_account'] = self.account
        intercompany_repayments_out = CashRepayment.objects.filter(
            **icr_filter
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total_outflows = (
            procurements_out + 
            expenses_out + 
            vendor_payments_out + 
            team_payments_out +
            loans_given_out +
            refunds_out + 
            bank_charges_out + 
            transfers_out +
            intercompany_repayments_out
        )
        
        # ============================================================
        # OPENING BALANCE
        # ============================================================
        opening_balance = total_inflows - total_outflows
        
        return opening_balance
    
    def _get_customer_payments(self):
        """Customer payments = Cash IN"""
        from .models import Payment
        
        payments = Payment.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('customer', 'payment_account')
        
        if self.account:
            payments = payments.filter(payment_account=self.account)
        
        return [{
            'date': p.date,
            'type': 'Payment',
            'description': f"Payment from {p.customer.name}",
            'category': 'Customer Payments',
            'reference': p.reference or '',
            'inflow': p.amount,
            'outflow': None,
            'account': p.payment_account.bank_name if p.payment_account else '',
            'created_at': p.created_at,
        } for p in payments]
    
    def _get_sand_sales(self):
        """Sand sales = Cash IN"""
        from .models import SandSale
        
        sales = SandSale.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('vehicle_type', 'payment_account')
        
        if self.account:
            sales = sales.filter(payment_account=self.account)
        
        results = []
        for s in sales:
            desc = f"Sand Sale: {s.quantity}x {s.vehicle_type.name}"
            if s.customer_name:
                desc += f" ({s.customer_name})"
            
            results.append({
                'date': s.date,
                'type': 'Sand Sale',
                'description': desc,
                'category': 'Sand Sales',
                'reference': f'SND-{s.pk:05d}',
                'inflow': s.total_amount,
                'outflow': None,
                'account': s.payment_account.bank_name if s.payment_account else '',
                'created_at': s.created_at,
            })
        return results
    
    def _get_quick_sales(self):
        """Quick sales (walk-in cash) = Cash IN"""
        from .models import QuickSale
        
        sales = QuickSale.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('block_type', 'payment_account')
        
        if self.account:
            sales = sales.filter(payment_account=self.account)
        
        results = []
        for s in sales:
            desc = f"Quick Sale: {s.quantity}x {s.block_type.name}"
            if s.buyer_name:
                desc += f" ({s.buyer_name})"
            
            results.append({
                'date': s.date,
                'type': 'Quick Sale',
                'description': desc,
                'category': 'Quick Sales',
                'reference': f'QS-{s.pk:05d}',
                'inflow': s.total_amount,
                'outflow': None,
                'account': s.payment_account.bank_name if s.payment_account else '',
                'created_at': s.created_at,
            })
        return results
    
    def _get_loan_repayments(self):
        """Loan repayments received = Cash IN"""
        from .models import LoanRepayment
        
        repayments = LoanRepayment.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('loan__debtor', 'payment_account')
        
        if self.account:
            repayments = repayments.filter(payment_account=self.account)
        
        return [{
            'date': r.date,
            'type': 'Loan Repayment',
            'description': f"Repayment from {r.loan.debtor.name}",
            'category': 'Loan Repayments',
            'reference': r.reference or f'LOAN-{r.loan.pk:05d}',
            'inflow': r.amount,
            'outflow': None,
            'account': r.payment_account.bank_name if r.payment_account else '',
            'created_at': r.created_at,
        } for r in repayments]
    
    def _get_procurement_payments(self):
        """Paid procurements = Cash OUT"""
        from .models import ProcurementLog
        
        procurements = ProcurementLog.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date,
            is_paid=True
        ).select_related('vendor', 'material', 'payment_account')
        
        if self.account:
            procurements = procurements.filter(payment_account=self.account)
        
        return [{
            'date': p.date,
            'type': 'Procurement',
            'description': f"{p.quantity} {p.material.get_name_display()} from {p.vendor.name if p.vendor else 'Unknown'}",
            'category': 'Raw Materials',
            'reference': '',
            'inflow': None,
            'outflow': p.total_cost,
            'account': p.payment_account.bank_name if p.payment_account else '',
            'created_at': p.created_at,
        } for p in procurements]
    
    def _get_expense_payments(self):
        """Paid expenses = Cash OUT"""
        from .models import Expense
        
        expenses = Expense.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date,
            is_paid=True
        ).select_related('category', 'payment_account', 'vendor')
        
        if self.account:
            expenses = expenses.filter(payment_account=self.account)
        if self.business_unit:
            expenses = expenses.filter(business_unit=self.business_unit)
        
        return [{
            'date': e.payment_date or e.date,
            'type': 'Expense',
            'description': f"{e.category.name}: {e.description[:30]}",
            'category': e.category.name,
            'reference': e.receipt_number or '',
            'inflow': None,
            'outflow': e.amount,
            'account': e.payment_account.bank_name if e.payment_account else '',
            'created_at': e.created_at,
        } for e in expenses]
    
    def _get_vendor_payments(self):
        """Payments to vendors = Cash OUT"""
        from .models import VendorPayment
        
        payments = VendorPayment.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('vendor', 'payment_account')
        
        if self.account:
            payments = payments.filter(payment_account=self.account)
        
        return [{
            'date': p.date,
            'type': 'Vendor Payment',
            'description': f"Payment to {p.vendor.name}",
            'category': 'Vendor Payments',
            'reference': p.reference or '',
            'inflow': None,
            'outflow': p.amount,
            'account': p.payment_account.bank_name if p.payment_account else '',
            'created_at': p.created_at,
        } for p in payments]
    
    def _get_team_payments(self):
        """Payments to production teams = Cash OUT (NOT in P&L expenses)"""
        from .models import TeamPayment
        
        payments = TeamPayment.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('team', 'employee', 'payment_account')
        
        if self.account:
            payments = payments.filter(payment_account=self.account)
        
        results = []
        for p in payments:
            if p.team:
                desc = f"{p.get_payment_type_display()} - {p.team.name}"
            elif p.employee:
                desc = f"{p.get_payment_type_display()} - {p.employee.name}"
            else:
                desc = p.get_payment_type_display()
            
            results.append({
                'date': p.date,
                'type': 'Team Payment',
                'description': desc,
                'category': 'Team/Labor Payments',
                'reference': p.reference or '',
                'inflow': None,
                'outflow': p.amount_paid,
                'account': p.payment_account.bank_name if p.payment_account else '',
                'created_at': p.created_at,
            })
        return results
    
    def _get_loans_given(self):
        """Loans given to debtors = Cash OUT"""
        from .models import Loan
        
        loans = Loan.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('debtor', 'payment_account')
        
        if self.account:
            loans = loans.filter(payment_account=self.account)
        
        return [{
            'date': loan.date,
            'type': 'Loan Given',
            'description': f"Loan to {loan.debtor.name}",
            'category': 'Loans Given',
            'reference': f'LOAN-{loan.pk:05d}',
            'inflow': None,
            'outflow': loan.amount,
            'account': loan.payment_account.bank_name if loan.payment_account else '',
            'created_at': loan.created_at,
        } for loan in loans]
    
    def _get_cash_refunds(self):
        """Refunds to customers = Cash OUT"""
        from .models import CashRefund
        
        refunds = CashRefund.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('customer', 'payment_account')
        
        if self.account:
            refunds = refunds.filter(payment_account=self.account)
        
        return [{
            'date': r.date,
            'type': 'Refund',
            'description': f"Refund to {r.customer.name}",
            'category': 'Customer Refunds',
            'reference': '',
            'inflow': None,
            'outflow': r.amount,
            'account': r.payment_account.bank_name if r.payment_account else '',
            'created_at': r.created_at,
        } for r in refunds]
    
    def _get_bank_charges(self):
        """Bank charges = Cash OUT"""
        from .models import BankCharge
        
        charges = BankCharge.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('account')
        
        if self.account:
            charges = charges.filter(account=self.account)
        if self.business_unit:
            charges = charges.filter(account__business_unit=self.business_unit)
        
        return [{
            'date': c.date,
            'type': 'Bank Charge',
            'description': f"{c.charge_type}: {c.description or ''}",
            'category': 'Bank Charges',
            'reference': c.reference or '',
            'inflow': None,
            'outflow': c.amount,
            'account': c.account.bank_name,
            'created_at': c.created_at,
        } for c in charges]
    
    def _get_transfers_in(self):
        """Transfers received = Cash IN"""
        from .models import AccountTransfer
        
        transfers = AccountTransfer.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('from_account', 'to_account')
        
        if self.account:
            transfers = transfers.filter(to_account=self.account)
        
        results = []
        for t in transfers:
            desc = f"Transfer from {t.from_account.bank_name}"
            if t.is_transport_settlement:
                desc = f"Settlement from {t.from_account.bank_name}"
            
            results.append({
                'date': t.date,
                'type': 'Transfer In',
                'description': desc,
                'category': 'Transfers',
                'reference': t.reference or '',
                'inflow': t.amount,
                'outflow': None,
                'account': t.to_account.bank_name,
                'created_at': t.created_at,
            })
        return results
    
    def _get_transfers_out(self):
        """Transfers sent = Cash OUT"""
        from .models import AccountTransfer
        
        transfers = AccountTransfer.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('from_account', 'to_account')
        
        if self.account:
            transfers = transfers.filter(from_account=self.account)
        
        results = []
        for t in transfers:
            desc = f"Transfer to {t.to_account.bank_name}"
            if t.is_transport_settlement:
                desc = f"Settlement to {t.to_account.bank_name}"
            
            results.append({
                'date': t.date,
                'type': 'Transfer Out',
                'description': desc,
                'category': 'Transfers',
                'reference': t.reference or '',
                'inflow': None,
                'outflow': t.amount,
                'account': t.from_account.bank_name,
                'created_at': t.created_at,
            })
        return results

    def _get_intercompany_collections(self):
        """Inter-Company Collections = Cash IN (from C&C Frozen Food)"""
        from .models import CashCollection

        collections = CashCollection.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('receiving_account', 'employee', 'inter_company_account')

        if self.account:
            collections = collections.filter(receiving_account=self.account)

        results = []
        for cc in collections:
            desc = f"C&C Collection: {cc.get_purpose_display()}"
            if cc.employee:
                desc += f" ({cc.employee.name})"

            results.append({
                'date': cc.date,
                'type': 'Inter-Company Collection',
                'description': desc,
                'category': 'Inter-Company (C&C)',
                'reference': cc.reference or f'ICC-{cc.pk:05d}',
                'inflow': cc.amount,
                'outflow': None,
                'account': cc.receiving_account.bank_name if cc.receiving_account else '',
                'created_at': cc.created_at,
            })
        return results

    def _get_intercompany_repayments(self):
        """Inter-Company Repayments = Cash OUT (to C&C Frozen Food)"""
        from .models import CashRepayment

        repayments = CashRepayment.objects.filter(
            date__gte=self.start_date,
            date__lte=self.end_date
        ).select_related('source_account', 'inter_company_account')

        if self.account:
            repayments = repayments.filter(source_account=self.account)

        results = []
        for cr in repayments:
            results.append({
                'date': cr.date,
                'type': 'Inter-Company Repayment',
                'description': f"C&C Repayment: {cr.get_repayment_method_display()}",
                'category': 'Inter-Company (C&C)',
                'reference': cr.reference or f'ICR-{cr.pk:05d}',
                'inflow': None,
                'outflow': cr.amount,
                'account': cr.source_account.bank_name if cr.source_account else '',
                'created_at': cr.created_at,
            })
        return results
    
    def get_summary(self):
        """Returns simplified summary for dashboard"""
        cf = self.get_cash_flow_statement()
        return {
            'total_inflow': cf['total_inflow'],
            'total_outflow': cf['total_outflow'],
            'net_cash_flow': cf['net_cash_flow'],
            'inflow_by_category': cf['inflow_by_category'],
            'outflow_by_category': cf['outflow_by_category'],
        }