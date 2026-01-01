from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from decimal import Decimal
from .models import SupplyLog, Expense, ProductionLog, Customer, Material, BlockType, FuelLog, Truck

class KPIService:
    def __init__(self):
        self.today = timezone.now().date()
        # Calculate stats for the current month (e.g., Dec 1st to Now)
        self.month_start = self.today.replace(day=1)

    def get_summary_stats(self):
        """Financial High-Level Overview (Current Month)"""
        
        # 1. Revenue (From Supply Logs)
        revenue = SupplyLog.objects.filter(date__gte=self.month_start).aggregate(
            total=Sum('total_value')
        )['total'] or 0

        # 2. Expenses (From Unified Expense Ledger)
        expenses = Expense.objects.filter(date__gte=self.month_start).aggregate(
            total=Sum('amount')
        )['total'] or 0

        # 3. Production (Blocks Produced)
        production = ProductionLog.objects.filter(date__gte=self.month_start).aggregate(
            total=Sum('quantity_produced')
        )['total'] or 0

        return {
            "revenue": revenue,
            "expenses": expenses,
            "net_profit": revenue - expenses,
            "production_count": production,
            "month_name": self.today.strftime('%B'),
            "year": self.today.year
        }

    def get_top_debtors(self):
        """Top 5 Customers who owe us money (Negative Balance)"""
        return Customer.objects.filter(account_balance__lt=0).order_by('account_balance')[:5]

    def get_inventory_alerts(self):
        """Items below low_stock_threshold"""
        low_materials = [
            m for m in Material.objects.filter(is_active=True) 
            if m.current_stock <= m.low_stock_threshold
        ]
        low_blocks = [
            b for b in BlockType.objects.filter(is_active=True) 
            if b.current_stock <= b.low_stock_threshold
        ]
        return {"materials": low_materials, "blocks": low_blocks}

    def get_recent_activity(self):
        """Latest 5 Supplies"""
        return SupplyLog.objects.select_related('customer', 'block_type').order_by('-date', '-created_at')[:5]

    def get_transport_analytics(self):
        """
        Calculates Profit/Loss for 'Jafan Transport' (Internal Profit Center).
        
        Logic:
        - Income: (Blocks Delivered * Logistics Rate) + (Order Surcharges)
        - Expense: Fuel Used + Maintenance + Driver Salaries
        - Efficiency Audit: Compares Expected Diesel (based on Local Trips) vs Actual.
        """
        
        # 1. Transport Revenue
        # We need to iterate because logistics_rate is on the Foreign Key (BlockType)
        # and surcharge is on the SalesOrder
        
        transport_income = Decimal('0.00')
        supplies = SupplyLog.objects.filter(
            date__gte=self.month_start, 
            delivery_type='DELIVERED'
        ).select_related('block_type', 'sales_order')
        
        total_trips = supplies.count()
        outside_town_trips = 0
        
        for log in supplies:
            # Base Income: Blocks * Logistics Rate (e.g. 65 Naira)
            rate = log.block_type.logistics_rate
            income = (log.quantity_delivered * rate)
            
            # Surcharge Income: Added if order has surcharge per block
            surcharge = Decimal('0.00')
            if log.sales_order and log.sales_order.surcharge_per_block > 0:
                surcharge = log.sales_order.surcharge_per_block * log.quantity_delivered
            
            transport_income += (income + surcharge)
            
            if log.site.is_outside_town:
                outside_town_trips += 1

        # 2. Transport Expenses
        
        # Fuel Costs (Sum of FuelLogs for TRUCKS only)
        fuel_cost = FuelLog.objects.filter(
            date__gte=self.month_start, 
            destination_type='TRUCK'
        ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0.00')
        
        actual_fuel_liters = FuelLog.objects.filter(
            date__gte=self.month_start, 
            destination_type='TRUCK'
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0.00')
        
        # Maintenance & Salaries (Expenses linked to Trucks)
        # Assuming you link Expenses to a Truck
        maintenance_cost = Expense.objects.filter(
            date__gte=self.month_start,
            truck__isnull=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        total_expense = fuel_cost + maintenance_cost
        
        # 3. Efficiency Audit (The "Theft Check")
        # Calculate Expected Diesel based on Trips
        # Formula: Expected = Sum(Trips * (Benchmark / Expected_Trips))
        
        expected_fuel_liters = Decimal('0.00')
        
        # Get list of active trucks to calculate individually
        trucks = Truck.objects.filter(is_active=True)
        
        for truck in trucks:
            truck_trips = supplies.filter(truck=truck).count()
            if truck.expected_trips > 0:
                consumption_rate = truck.benchmark_fuel / truck.expected_trips
                expected_fuel_liters += (Decimal(truck_trips) * consumption_rate)
        
        variance_liters = actual_fuel_liters - expected_fuel_liters
        
        return {
            "revenue": transport_income,
            "expenses": total_expense,
            "net_profit": transport_income - total_expense,
            "fuel_audit": {
                "actual_liters": actual_fuel_liters,
                "expected_liters": expected_fuel_liters,
                "variance": variance_liters, # Positive = Used more than expected
                "outside_trips": outside_town_trips, # Explain variance
                "standard_trips": total_trips - outside_town_trips
            }
        }