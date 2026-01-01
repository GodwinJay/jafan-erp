from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from auditlog.registry import auditlog
from decimal import Decimal
from django.db.models import F, Sum
from django.core.exceptions import ValidationError


# ==============================================================================
# Day 2: Authentication
# ==============================================================================

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('GM', 'General Manager'),
        ('SUPPLY', 'Supply Manager'),
        ('SITE', 'Site Manager'),
        ('SALES', 'Sales Representative'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='SALES')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'ADMIN' or self.is_superuser

    @property
    def can_edit(self):
        return self.role in ['ADMIN', 'GM']

    @property
    def can_delete(self):
        return self.role == 'ADMIN'


# ==============================================================================
# Day 3: Materials & Constants
# ==============================================================================

class Material(models.Model):
    """Raw materials inventory tracking."""
    NAME_CHOICES = [
        ('CEMENT', 'Cement (Bags)'),
        ('SHARP_SAND', 'Sharp Sand (Tons)'),
        ('BLACK_SAND', 'Black Sand (Tons)'),
        ('DIESEL', 'Diesel (Liters)'),
        ('STONE_DUST', 'Stone Dust (Tons)'),
    ]
    name = models.CharField(max_length=20, choices=NAME_CHOICES, unique=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Current cost per unit")
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Current quantity available")
    low_stock_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=10.0, help_text="Alert when stock falls below this")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_name_display()} ({self.current_stock})"

    @property
    def is_low_stock(self):
        return self.current_stock <= self.low_stock_threshold


class BlockType(models.Model):
    """Block products, recipes, and inventory."""
    name = models.CharField(max_length=50)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Finished Goods Inventory
    current_stock = models.IntegerField(default=0, help_text="Blocks ready for sale")
    low_stock_threshold = models.IntegerField(default=500, help_text="Alert when stock falls below this")

    # Production Recipe (set to 0 for non-produced items like Half Blocks)
    blocks_per_bag = models.IntegerField(default=0, help_text="Expected blocks from 1 bag of cement (0 for non-produced items)")
    sand_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Tons of sharp sand per batch")
    batch_size = models.IntegerField(default=1350, help_text="Batch size for sand ratio")

    # Variable Costs (per block)
    operator_rate = models.DecimalField(max_digits=10, decimal_places=2, default=35.00)
    loader_rate = models.DecimalField(max_digits=10, decimal_places=2, default=9.00)
    stacking_rate = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    logistics_rate = models.DecimalField(max_digits=10, decimal_places=2, default=65.00)

    # Flag for special block types
    is_half_block = models.BooleanField(default=False, help_text="Is this a half/broken block type?")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.current_stock} in stock)"

    @property
    def total_variable_rate(self):
        return self.operator_rate + self.loader_rate + self.stacking_rate + self.logistics_rate

    @property
    def labor_rate(self):
        return self.operator_rate + self.loader_rate + self.stacking_rate

    @property
    def is_low_stock(self):
        return self.current_stock <= self.low_stock_threshold

    def get_variable_cost(self, quantity):
        return quantity * self.total_variable_rate


class BusinessRules(models.Model):
    """Global overhead costs shared across all production."""
    name = models.CharField(max_length=50, default="Standard Production Rates")
    sand_cost = models.DecimalField(max_digits=12, decimal_places=2, default=330000)
    black_sand_cost = models.DecimalField(max_digits=12, decimal_places=2, default=10000)
    water_base_cost = models.DecimalField(max_digits=12, decimal_places=2, default=28800)
    diesel_power_cost = models.DecimalField(max_digits=12, decimal_places=2, default=18000)
    miscellaneous_cost = models.DecimalField(max_digits=12, decimal_places=2, default=45000)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Business Rules"
        verbose_name_plural = "Business Rules"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def total_batch_overhead(self):
        return self.sand_cost + self.black_sand_cost + self.water_base_cost + self.diesel_power_cost + self.miscellaneous_cost

    def __str__(self):
        return f"{self.name} (Updated: {self.updated_at.strftime('%Y-%m-%d') if self.updated_at else 'Never'})"


class PaymentAccount(models.Model):
    """Bank accounts and cash tracking."""
    bank_name = models.CharField(max_length=50)
    account_number = models.CharField(max_length=20, blank=True, null=True)
    account_name = models.CharField(max_length=100, default="Jafan Standard Block Ind")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


# ==============================================================================
# Day 4: Teams, Machines, Customers, Employees
# ==============================================================================

class Team(models.Model):
    """Production Teams (e.g., Team A, Team B)."""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Machine(models.Model):
    """Block Producing Machines."""
    MACHINE_TYPE_CHOICES = [
        ('BLOCK', 'Block Machine'),
        ('MIXER', 'Mixer'),
        ('GENERATOR', 'Generator'),
        ('OTHER', 'Other'),
    ]

    STATUS_CHOICES = [
        ('OPERATIONAL', 'Operational'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('DOWN', 'Down/Broken'),
    ]

    name = models.CharField(max_length=50, unique=True)
    machine_type = models.CharField(max_length=20, choices=MACHINE_TYPE_CHOICES, default='BLOCK')
    assigned_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="machines")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPERATIONAL')
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_machine_type_display()})"


class Customer(models.Model):
    """Customer database for sales and delivery tracking."""
    CUSTOMER_TYPE_CHOICES = [
        ('ENGINEER', 'Engineer'),
        ('DEVELOPER', 'Developer'),
        ('CONTRACTOR', 'Contractor'),
        ('INDIVIDUAL', 'Individual'),
        ('OTHER', 'Other'),
    ]

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    office_address = models.TextField(blank=True, null=True, help_text="Main office or billing address")
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='INDIVIDUAL')

    account_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Positive = Credit (we owe blocks), Negative = Debit (they owe money)"
    )

    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @property
    def total_blocks_owed(self):
        return self.sites.aggregate(total=Sum('blocks_owed'))['total'] or 0

    @property
    def balance_status(self):
        if self.account_balance > 0:
            return "Credit"
        elif self.account_balance < 0:
            return "Owes"
        return "Settled"


class Site(models.Model):
    """Multiple delivery sites per customer."""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sites')
    name = models.CharField(max_length=100, help_text="e.g., GRA Phase 2, UniAgric Site")
    address = models.TextField(help_text="Full delivery address for driver")
    contact_person = models.CharField(max_length=100, blank=True, null=True, help_text="On-site contact if different")
    contact_phone = models.CharField(max_length=20, blank=True, null=True)

    is_outside_town = models.BooleanField(default=False, help_text="Attracts outside town surcharge?")
    blocks_owed = models.IntegerField(default=0, help_text="Paid but undelivered blocks for this site")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['customer', 'name']

    def __str__(self):
        return f"{self.customer.name} - {self.name}"


class Employee(models.Model):
    """Employee database for production and logistics."""
    ROLE_CHOICES = [
        ('OPERATOR', 'Machine Operator'),
        ('LOADER', 'Loader'),
        ('DRIVER', 'Driver'),
        ('MIXER', 'Mixer'),
        ('STACKER', 'Stacker'),
        ('CARRIER', 'Carrier'),
        ('MANAGER', 'Manager'),
        ('SALES', 'Sales Staff'),
        ('SECURITY', 'Security'),
        ('OTHER', 'Other'),
    ]

    PAY_TYPE_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
    ]

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="members")
    pay_type = models.CharField(max_length=10, choices=PAY_TYPE_CHOICES, default='WEEKLY')

    current_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Negative = owes company (loan), Positive = company owes them"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"


# ==============================================================================
# Day 5: Vendors & Trucks
# ==============================================================================

class Vendor(models.Model):
    """Suppliers for cement, sand, fuel, etc."""
    SUPPLY_TYPE_CHOICES = [
        ('CEMENT', 'Cement'),
        ('SHARP_SAND', 'Sharp Sand'),
        ('BLACK_SAND', 'Black Sand'),
        ('FUEL', 'Fuel/Diesel'),
        ('MAINTENANCE', 'Maintenance/Repairs'),
        ('OTHER', 'Other'),
    ]

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    supply_type = models.CharField(max_length=20, choices=SUPPLY_TYPE_CHOICES, default='OTHER')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_supply_type_display()})"


class Truck(models.Model):
    """Fleet management with fuel benchmarks."""
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('ON_DELIVERY', 'On Delivery'),
        ('MAINTENANCE', 'Under Maintenance'),
    ]

    FUEL_CHOICES = [
        ('DIESEL', 'Diesel'),
        ('PETROL', 'Petrol'),
    ]

    name = models.CharField(max_length=50, unique=True, help_text="e.g., Truck A, Tipper 1")
    plate_number = models.CharField(max_length=20, blank=True, null=True)
    driver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_trucks", limit_choices_to={'role': 'DRIVER'})

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')

    fuel_type = models.CharField(max_length=10, choices=FUEL_CHOICES, default='DIESEL')
    fuel_capacity = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Tank capacity (Liters)")
    
    # Efficiency Benchmarks (Used for Transport Analytics)
    benchmark_fuel = models.DecimalField(max_digits=5, decimal_places=2, default=30.00, help_text="Benchmark liters per cycle")
    expected_trips = models.IntegerField(default=8, help_text="Expected trips per benchmark fuel")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        driver_name = self.driver.name if self.driver else "No Driver"
        return f"{self.name} ({driver_name})"


# ==============================================================================
# Day 9: Expenses Module (MUST BE BEFORE ProcurementLog for Auto-Sync)
# ==============================================================================

class ExpenseCategory(models.Model):
    """Categories for expense tracking - User-defined and flexible."""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Expense Category"
        verbose_name_plural = "Expense Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Expense(models.Model):
    """
    The Unified Cost Ledger - Single Source of Truth for ALL money leaving the company.
    This includes both manual expenses AND auto-synced procurement costs.
    """
    date = models.DateField(default=timezone.now)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    description = models.CharField(max_length=200, help_text="Brief description of expense")
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Payment details
    payment_account = models.ForeignKey(
        PaymentAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Account used for payment"
    )

    # Optional links for specific expense types
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Vendor if applicable"
    )
    truck = models.ForeignKey(
        Truck,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Truck if vehicle-related expense"
    )
    machine = models.ForeignKey(
        Machine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Machine if equipment-related expense"
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Employee if salary/advance/allowance"
    )

    # Documentation
    receipt_number = models.CharField(max_length=50, blank=True, null=True, help_text="Receipt or invoice number")
    notes = models.TextField(blank=True, null=True)

    # Auto-sync flag (to identify auto-created entries)
    is_auto_synced = models.BooleanField(default=False, editable=False, help_text="True if auto-created from Procurement")

    # Approval (optional - for large expenses)
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses',
        limit_choices_to={'role__in': ['ADMIN', 'GM']}
    )

    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name='recorded_expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} | {self.category.name} | ₦{self.amount:,.2f} | {self.description[:30]}"


# ==============================================================================
# Day 5 (continued): Procurement with Auto-Sync to Expense
# ==============================================================================

class ProcurementLog(models.Model):
    """
    Log purchases - auto-updates material stock AND auto-syncs to Expense ledger.
    This is the HYBRID approach: Procurement for stock tracking, Expense for cost tracking.
    """
    date = models.DateField()
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount purchased (bags, tons, liters)")
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total amount paid")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0, help_text="Auto-calculated: total_cost / quantity")

    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.SET_NULL, null=True, blank=True)

    # THE AUTO-SYNC LINK - OneToOne relationship to Expense
    expense_entry = models.OneToOneField(
        Expense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='procurement_source',
        help_text="Auto-created expense entry"
    )

    remark = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    @transaction.atomic
    def save(self, *args, **kwargs):
        # 1. Calculate Unit Price
        if self.quantity > 0:
            self.unit_price = self.total_cost / self.quantity

        # 2. Get old quantity for stock diff calculation
        old_qty = Decimal('0')
        if self.pk:
            try:
                old_log = ProcurementLog.objects.get(pk=self.pk)
                old_qty = old_log.quantity
            except ProcurementLog.DoesNotExist:
                pass

        # 3. AUTO-SYNC WITH EXPENSE LEDGER (The Hybrid Superior Logic)
        raw_material_cat, _ = ExpenseCategory.objects.get_or_create(
            name="Raw Materials",
            defaults={'description': 'Auto-created for procurement sync'}
        )

        vendor_name = self.vendor.name if self.vendor else "Unknown Vendor"
        expense_description = f"Auto-Log: {self.quantity} {self.material.get_name_display()} from {vendor_name}"

        if not self.expense_entry:
            self.expense_entry = Expense.objects.create(
                date=self.date,
                category=raw_material_cat,
                description=expense_description,
                amount=self.total_cost,
                payment_account=self.payment_account,
                vendor=self.vendor,
                is_auto_synced=True,
                recorded_by=self.recorded_by
            )
        else:
            self.expense_entry.date = self.date
            self.expense_entry.amount = self.total_cost
            self.expense_entry.payment_account = self.payment_account
            self.expense_entry.vendor = self.vendor
            self.expense_entry.description = expense_description
            self.expense_entry.save()

        # 4. Save ProcurementLog
        super().save(*args, **kwargs)

        # 5. Update Material Stock using F() - RACE CONDITION SAFE
        diff = self.quantity - old_qty
        if diff != 0:
            Material.objects.filter(pk=self.material.pk).update(
                current_stock=F('current_stock') + diff
            )
            self.material.refresh_from_db()

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse material stock using F()
        Material.objects.filter(pk=self.material.pk).update(
            current_stock=F('current_stock') - self.quantity
        )

        # Delete the linked Expense entry
        if self.expense_entry:
            self.expense_entry.delete()

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.date} - {self.material.name} (+{self.quantity})"


# ==============================================================================
# Day 6: Production Module
# ==============================================================================

class ProductionLog(models.Model):
    """
    Daily production record.
    Manual entry: cement used, black sand used
    Auto-calculates: sharp sand used, labor cost
    Auto-updates: block stock (add), material stock (subtract)
    """
    date = models.DateField()
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, limit_choices_to={'machine_type': 'BLOCK'})
    block_type = models.ForeignKey(BlockType, on_delete=models.PROTECT)
    quantity_produced = models.PositiveIntegerField(help_text="Number of blocks produced")
    breakages = models.PositiveIntegerField(default=0, help_text="Blocks broken during production")

    cement_used = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Bags of cement used")
    black_sand_used = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Tons of black sand used")

    sharp_sand_used = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0, help_text="Auto-calculated from recipe")
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)

    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    @transaction.atomic
    def save(self, *args, **kwargs):
        old_qty = 0
        old_cement = Decimal('0')
        old_black_sand = Decimal('0')
        old_sharp_sand = Decimal('0')

        if self.pk:
            old_log = ProductionLog.objects.get(pk=self.pk)
            old_qty = old_log.quantity_produced
            old_cement = old_log.cement_used
            old_black_sand = old_log.black_sand_used
            old_sharp_sand = old_log.sharp_sand_used

        # Calculate sharp sand from recipe
        if self.block_type.batch_size > 0:
            batches = Decimal(self.quantity_produced) / Decimal(self.block_type.batch_size)
            self.sharp_sand_used = batches * self.block_type.sand_ratio

        # Calculate labor cost
        labor_rate = self.block_type.operator_rate + self.block_type.loader_rate + self.block_type.stacking_rate
        self.labor_cost = Decimal(self.quantity_produced) * labor_rate

        super().save(*args, **kwargs)

        # Update block stock using F() - RACE CONDITION SAFE
        stock_diff = self.quantity_produced - old_qty
        if stock_diff != 0:
            BlockType.objects.filter(pk=self.block_type.pk).update(
                current_stock=F('current_stock') + stock_diff
            )
            self.block_type.refresh_from_db()

        # Update material stocks using F() - RACE CONDITION SAFE
        cement_diff = self.cement_used - old_cement
        if cement_diff != 0:
            Material.objects.filter(name='CEMENT').update(
                current_stock=F('current_stock') - cement_diff
            )

        black_sand_diff = self.black_sand_used - old_black_sand
        if black_sand_diff != 0:
            Material.objects.filter(name='BLACK_SAND').update(
                current_stock=F('current_stock') - black_sand_diff
            )

        sharp_sand_diff = self.sharp_sand_used - old_sharp_sand
        if sharp_sand_diff != 0:
            Material.objects.filter(name='SHARP_SAND').update(
                current_stock=F('current_stock') - sharp_sand_diff
            )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse block stock using F()
        BlockType.objects.filter(pk=self.block_type.pk).update(
            current_stock=F('current_stock') - self.quantity_produced
        )

        # Reverse material stocks using F()
        Material.objects.filter(name='CEMENT').update(
            current_stock=F('current_stock') + self.cement_used
        )
        Material.objects.filter(name='BLACK_SAND').update(
            current_stock=F('current_stock') + self.black_sand_used
        )
        Material.objects.filter(name='SHARP_SAND').update(
            current_stock=F('current_stock') + self.sharp_sand_used
        )

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.date}: {self.block_type.name} (+{self.quantity_produced})"


# ==============================================================================
# Day 7: The Ledger System (Payments, Sales Orders & Supplies)
# ==============================================================================

class Payment(models.Model):
    """
    Money In.
    Action: INCREASES Customer Balance (Credit).
    """
    PAYMENT_METHOD_CHOICES = [
        ('TRANSFER', 'Bank Transfer'),
        ('CASH', 'Cash'),
        ('POS', 'POS Terminal'),
        ('CHEQUE', 'Cheque'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='payments')
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount received")
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='TRANSFER')
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.SET_NULL, null=True, blank=True, help_text="Which account received the money?")
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="Bank Ref / Teller No / Receipt No")

    remark = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_amount = Decimal('0')
        
        if not is_new:
            old_amount = Payment.objects.get(pk=self.pk).amount

        super().save(*args, **kwargs)

        # Credit customer balance using F() - RACE CONDITION SAFE
        diff = self.amount - old_amount
        if diff != 0:
            Customer.objects.filter(pk=self.customer.pk).update(
                account_balance=F('account_balance') + diff
            )
            self.customer.refresh_from_db()

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse customer balance using F()
        Customer.objects.filter(pk=self.customer.pk).update(
            account_balance=F('account_balance') - self.amount
        )
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.date} | {self.customer.name} | +₦{self.amount:,.2f}"


class SalesOrder(models.Model):
    """
    Sales Order / Quotation.

    PRICING:
    - surcharge_per_block: Added to each block price (e.g., outside town delivery)
    - discount_per_block: Deducted from each block price
    - Final price per block = selling_price + surcharge - discount
    """

    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('PARTIAL', 'Partially Supplied'),
        ('COMPLETED', 'Fully Supplied'),
        ('CANCELLED', 'Cancelled'),
    ]

    date = models.DateField(default=timezone.now)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='sales_orders')
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    # Per-block pricing adjustments
    surcharge_per_block = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount added PER BLOCK (e.g., ₦50 for outside town delivery)"
    )
    discount_per_block = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount deducted PER BLOCK (e.g., ₦20 bulk discount)"
    )
    discount_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reason for discount (if any)"
    )

    # Validity for proforma
    valid_until = models.DateField(
        null=True,
        blank=True,
        help_text="Proforma validity date (auto-set to 14 days if empty)"
    )

    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Sales Order"
        verbose_name_plural = "Sales Orders"

    def __str__(self):
        return f"SO-{self.pk:05d} - {self.customer.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Auto-set validity to 14 days if not set
        if not self.valid_until:
            self.valid_until = self.date + timezone.timedelta(days=14)
        super().save(*args, **kwargs)

    @property
    def total_quantity_ordered(self):
        return sum(item.quantity_requested for item in self.items.all())

    @property
    def total_quantity_supplied(self):
        return sum(item.quantity_supplied for item in self.items.all())

    @property
    def supply_progress(self):
        total = self.total_quantity_ordered
        if total == 0:
            return 0
        return int((self.total_quantity_supplied / total) * 100)

    @property
    def total_value(self):
        """Total order value with surcharge and discount applied."""
        return sum(item.line_total for item in self.items.all())

    @property
    def is_valid(self):
        """Check if proforma is still valid."""
        if self.valid_until:
            return timezone.now().date() <= self.valid_until
        return True


class SalesOrderItem(models.Model):
    """
    Individual line item in a Sales Order.

    agreed_price is AUTO-CALCULATED:
    agreed_price = block_type.selling_price + order.surcharge_per_block - order.discount_per_block
    """

    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    block_type = models.ForeignKey(BlockType, on_delete=models.PROTECT)
    quantity_requested = models.PositiveIntegerField()

    # Auto-calculated from block_type price + order surcharge - order discount
    agreed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Auto-calculated: Block price + surcharge - discount"
    )

    # Track how much has been supplied
    quantity_supplied = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Sales Order Item"
        verbose_name_plural = "Sales Order Items"

    def __str__(self):
        return f"{self.quantity_requested} x {self.block_type.name} @ {self.agreed_price}"

    def save(self, *args, **kwargs):
        # Auto-calculate agreed_price from block type + surcharge - discount
        base_price = self.block_type.selling_price
        surcharge = self.order.surcharge_per_block if self.order_id else Decimal('0.00')
        discount = self.order.discount_per_block if self.order_id else Decimal('0.00')
        self.agreed_price = base_price + surcharge - discount

        super().save(*args, **kwargs)

    @property
    def line_total(self):
        """Total value for this line item."""
        return self.quantity_requested * self.agreed_price

    @property
    def quantity_remaining(self):
        """Quantity yet to be supplied."""
        return self.quantity_requested - self.quantity_supplied


class SupplyLog(models.Model):
    """
    Records actual delivery/supply of blocks to customers.
    Links to Sales Orders when applicable.

    unit_price AUTO-POPULATES from:
    1. SalesOrderItem.agreed_price (if linked to order)
    2. BlockType.selling_price (if direct supply without order)
    """

    DELIVERY_TYPE_CHOICES = [
        ('DELIVERED', 'Company Delivery'),
        ('SELF_PICKUP', 'Customer Self-Pickup'),
    ]

    date = models.DateField(default=timezone.now)
    delivery_type = models.CharField(
        max_length=20,
        choices=DELIVERY_TYPE_CHOICES,
        default='DELIVERED'
    )

    # Customer & Location
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='supplies'
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT
    )

    # Link to Sales Order (optional)
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplies'
    )
    order_item = models.ForeignKey(
        SalesOrderItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplies',
        help_text="Link to specific order item (auto-populates unit_price)"
    )

    # Product
    block_type = models.ForeignKey(
        BlockType,
        on_delete=models.PROTECT,
        related_name='supplies'
    )

    # Quantities
    quantity_loaded = models.PositiveIntegerField(
        help_text="Blocks loaded onto truck"
    )
    breakages = models.PositiveIntegerField(
        default=0,
        help_text="Blocks broken during delivery"
    )
    quantity_delivered = models.PositiveIntegerField(
        editable=False,
        default=0,
        help_text="Auto-calculated: loaded - breakages"
    )

    # Pricing - AUTO-POPULATED from order_item.agreed_price or block_type.selling_price
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Auto-populated from Sales Order or Block Type price"
    )
    logistics_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Discount for delivery issues (breakages, delays)"
    )
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        default=Decimal('0.00')
    )
    
    # NEW FIELD FOR TRANSPORT ANALYTICS
    # This snapshots the "Transport Revenue" at the moment of supply.
    # Logic: (Qty * Logistics Rate) + Surcharges
    logistics_income = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'), 
        editable=False,
        help_text="Income attributed to Jafan Transport (Rate + Surcharge)"
    )

    # Logistics (for company delivery)
    truck = models.ForeignKey(
        Truck,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplies'
    )
    driver = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries',
        limit_choices_to={'role': 'DRIVER'}
    )

    # Self-pickup authorization
    pickup_authorized_by = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of person who authorized pickup (for self-pickup)"
    )

    remark = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_supplies'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Supply Log"
        verbose_name_plural = "Supply Logs"

    def __str__(self):
        return f"Supply: {self.quantity_delivered} {self.block_type.name} to {self.customer.name}"

    def clean(self):
        """Validate before saving."""
        # Prevent breakages exceeding loaded quantity
        if self.breakages and self.quantity_loaded:
            if self.breakages > self.quantity_loaded:
                raise ValidationError({
                    'breakages': "Breakages cannot exceed Quantity Loaded."
                })

        # Validate truck/driver for delivered orders
        if self.delivery_type == 'DELIVERED':
            if not self.truck:
                raise ValidationError({
                    'truck': "Truck is required for Company Delivery."
                })

        # Validate pickup authorization
        if self.delivery_type == 'SELF_PICKUP':
            if not self.pickup_authorized_by:
                raise ValidationError({
                    'pickup_authorized_by': "Authorization name required for Self-Pickup."
                })

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # AUTO-POPULATE from Sales Order Item if linked
        if self.order_item:
            self.unit_price = self.order_item.agreed_price
            self.block_type = self.order_item.block_type
            if self.order_item.order:
                self.sales_order = self.order_item.order

        # Fallback to block_type selling price if no order
        if not self.unit_price and self.block_type:
            self.unit_price = self.block_type.selling_price

        # Calculate delivered quantity
        self.quantity_delivered = self.quantity_loaded - self.breakages

        # Calculate total value
        self.total_value = (self.quantity_delivered * self.unit_price) - self.logistics_discount
        
        # CALCULATE LOGISTICS INCOME (SNAPSHOT)
        # Base: Qty * Logistics Rate
        logistics_base = self.quantity_delivered * self.block_type.logistics_rate
        
        # Surcharge: If Sales Order has surcharge, add it
        surcharge_total = Decimal('0.00')
        if self.sales_order and self.sales_order.surcharge_per_block > 0:
            surcharge_total = self.quantity_delivered * self.sales_order.surcharge_per_block
            
        self.logistics_income = logistics_base + surcharge_total

        if is_new:
            # Deduct from block stock using F() - RACE CONDITION SAFE
            BlockType.objects.filter(pk=self.block_type.pk).update(
                current_stock=F('current_stock') - self.quantity_loaded
            )
            self.block_type.refresh_from_db()

            # Debit customer account using F() - RACE CONDITION SAFE
            Customer.objects.filter(pk=self.customer.pk).update(
                account_balance=F('account_balance') - self.total_value
            )
            self.customer.refresh_from_db()

            # Update order item supplied quantity using F()
            if self.order_item:
                SalesOrderItem.objects.filter(pk=self.order_item.pk).update(
                    quantity_supplied=F('quantity_supplied') + self.quantity_delivered
                )
                self.order_item.refresh_from_db()
                self._update_order_status()

        super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse stock using F()
        BlockType.objects.filter(pk=self.block_type.pk).update(
            current_stock=F('current_stock') + self.quantity_loaded
        )

        # Reverse customer balance using F()
        Customer.objects.filter(pk=self.customer.pk).update(
            account_balance=F('account_balance') + self.total_value
        )

        # Reverse order item supplied quantity using F()
        if self.order_item:
            SalesOrderItem.objects.filter(pk=self.order_item.pk).update(
                quantity_supplied=F('quantity_supplied') - self.quantity_delivered
            )
            self.order_item.refresh_from_db()
            self._update_order_status()

        super().delete(*args, **kwargs)

    def _update_order_status(self):
        """Update the parent sales order status based on supply progress."""
        if self.sales_order:
            progress = self.sales_order.supply_progress
            if progress == 0:
                self.sales_order.status = 'PENDING'
            elif progress >= 100:
                self.sales_order.status = 'COMPLETED'
            else:
                self.sales_order.status = 'PARTIAL'
            self.sales_order.save()


# ==============================================================================
# Day 8: Returns & Refunds (Reverse Logistics)
# ==============================================================================

class ReturnLog(models.Model):
    """
    Tracks blocks returned from customers/deliveries.

    IMPORTANT: By default, returns do NOT credit the customer account.
    Only check 'credit_customer' if this is a genuine refund scenario.
    """

    CONDITION_CHOICES = [
        ('GOOD', 'Good/Reusable (Full Block)'),
        ('HALF', 'Broken but Reusable (Half Block)'),
        ('DAMAGED', 'Damaged/Condemned (No Restock)'),
    ]

    date = models.DateField(default=timezone.now)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='returns')
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    original_supply = models.ForeignKey(
        'SupplyLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Link to original supply (optional, for traceability)"
    )

    # Product Info
    block_type = models.ForeignKey(
        BlockType,
        on_delete=models.PROTECT,
        help_text="The block type that was originally supplied"
    )
    quantity_returned = models.PositiveIntegerField()
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='GOOD')

    # Item Transformation (for half blocks)
    restock_as = models.ForeignKey(
        BlockType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restocked_returns',
        help_text="If returned block is now different type (e.g., Whole → Half), select target type here."
    )

    # Credit Customer Toggle
    credit_customer = models.BooleanField(
        default=False,
        help_text="⚠️ Check ONLY if customer should receive account credit."
    )

    # Financials (only applies if credit_customer is True)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Credit per block (only used if 'Credit Customer' is checked)"
    )
    restocking_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Fee deducted from credit"
    )
    credit_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
        help_text="Actual credit applied to customer account"
    )

    reason = models.TextField(help_text="Reason for return")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='approved_returns',
        limit_choices_to={'role__in': ['ADMIN', 'GM']}
    )

    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_returns'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Return Log"
        verbose_name_plural = "Return Logs"

    def __str__(self):
        credit_status = "w/ Credit" if self.credit_customer else "No Credit"
        return f"Return: {self.quantity_returned} {self.block_type.name} from {self.customer.name} ({credit_status})"

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Calculate credit value
        if self.credit_customer:
            self.credit_value = (self.quantity_returned * self.unit_price) - self.restocking_fee
            if self.credit_value < 0:
                self.credit_value = Decimal('0.00')
        else:
            self.credit_value = Decimal('0.00')

        if is_new:
            # Credit customer account ONLY if checkbox is checked using F()
            if self.credit_customer and self.credit_value > 0:
                Customer.objects.filter(pk=self.customer.pk).update(
                    account_balance=F('account_balance') + self.credit_value
                )
                self.customer.refresh_from_db()

            # Update stock (if not damaged) using F()
            if self.condition != 'DAMAGED':
                target_block = self.restock_as if self.restock_as else self.block_type
                BlockType.objects.filter(pk=target_block.pk).update(
                    current_stock=F('current_stock') + self.quantity_returned
                )
                target_block.refresh_from_db()

        super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse customer credit using F()
        if self.credit_customer and self.credit_value > 0:
            Customer.objects.filter(pk=self.customer.pk).update(
                account_balance=F('account_balance') - self.credit_value
            )

        # Reverse stock using F()
        if self.condition != 'DAMAGED':
            target_block = self.restock_as if self.restock_as else self.block_type
            BlockType.objects.filter(pk=target_block.pk).update(
                current_stock=F('current_stock') - self.quantity_returned
            )

        super().delete(*args, **kwargs)


class CashRefund(models.Model):
    """
    Money Out (Refunds).
    Action: DEBITS Customer Balance.
    """
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='refunds')
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_account = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        help_text="Bank account paying the refund"
    )

    reason = models.TextField(help_text="Reason for refund")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='approved_refunds',
        limit_choices_to={'role__in': ['ADMIN', 'GM']},
        help_text="Must be Admin or GM"
    )
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name='recorded_refunds')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_amount = Decimal('0')
        
        if not is_new:
            old_amount = CashRefund.objects.get(pk=self.pk).amount

        super().save(*args, **kwargs)

        # Debit Customer using F() - RACE CONDITION SAFE
        diff = self.amount - old_amount
        if diff != 0:
            Customer.objects.filter(pk=self.customer.pk).update(
                account_balance=F('account_balance') - diff
            )
            self.customer.refresh_from_db()

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse customer balance using F()
        Customer.objects.filter(pk=self.customer.pk).update(
            account_balance=F('account_balance') + self.amount
        )
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Refund: ₦{self.amount:,.2f} to {self.customer.name}"


# ==============================================================================
# Day 14: Breakage Log (On-Site Damage Tracking)
# ==============================================================================

class BreakageLog(models.Model):
    """
    Track blocks damaged on-site (not during delivery).
    Handles conversion of broken full blocks to half blocks.
    """

    REASON_CHOICES = [
        ('STACKING', 'Broken during stacking'),
        ('RAIN', 'Rain/weather damage'),
        ('ACCIDENT', 'Site accident'),
        ('HANDLING', 'Improper handling'),
        ('PRODUCTION', 'Production defect'),
        ('TRANSPORT', 'Internal transport damage'),
        ('OTHER', 'Other'),
    ]

    date = models.DateField(default=timezone.now)

    # What was broken
    block_type = models.ForeignKey(
        BlockType,
        on_delete=models.PROTECT,
        related_name='breakages',
        help_text="The full block type that was damaged"
    )
    quantity_broken = models.PositiveIntegerField(
        help_text="Number of blocks damaged"
    )

    # Reason and details
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        default='HANDLING'
    )
    description = models.TextField(
        blank=True,
        help_text="Additional details about the breakage incident"
    )

    # Half block conversion
    convert_to_half = models.BooleanField(
        default=False,
        help_text="Check if broken blocks can be salvaged as half blocks"
    )
    half_block_type = models.ForeignKey(
        BlockType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salvaged_from_breakages',
        limit_choices_to={'is_half_block': True},
        help_text="Select the half block type to add to stock (only if converting)"
    )
    quantity_salvaged = models.PositiveIntegerField(
        default=0,
        help_text="Number of half blocks salvaged (usually 2x broken if salvageable)"
    )

    # Approval and tracking
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_breakages'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='approved_breakages',
        limit_choices_to={'role__in': ['ADMIN', 'GM']},
        help_text="Manager who approved this breakage write-off"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Breakage Log"
        verbose_name_plural = "Breakage Logs"

    def __str__(self):
        salvage_info = f" → {self.quantity_salvaged} half" if self.convert_to_half else ""
        return f"Breakage: {self.quantity_broken} {self.block_type.name} ({self.get_reason_display()}){salvage_info}"

    def clean(self):
        """Validate conversion settings."""
        if self.convert_to_half:
            if not self.half_block_type:
                raise ValidationError({
                    'half_block_type': 'You must select a half block type when converting.'
                })
            if self.half_block_type and not self.half_block_type.is_half_block:
                raise ValidationError({
                    'half_block_type': 'Selected block type must be a half block.'
                })
            if self.quantity_salvaged <= 0:
                raise ValidationError({
                    'quantity_salvaged': 'Quantity salvaged must be greater than 0 when converting.'
                })

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Auto-suggest salvaged quantity (2 halves per broken block)
        if self.convert_to_half and self.quantity_salvaged == 0:
            self.quantity_salvaged = self.quantity_broken * 2

        if is_new:
            # Deduct broken blocks from full block stock using F()
            BlockType.objects.filter(pk=self.block_type.pk).update(
                current_stock=F('current_stock') - self.quantity_broken
            )
            self.block_type.refresh_from_db()

            # Add salvaged half blocks if converting using F()
            if self.convert_to_half and self.half_block_type and self.quantity_salvaged > 0:
                BlockType.objects.filter(pk=self.half_block_type.pk).update(
                    current_stock=F('current_stock') + self.quantity_salvaged
                )
                self.half_block_type.refresh_from_db()

        super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse stock changes using F()
        BlockType.objects.filter(pk=self.block_type.pk).update(
            current_stock=F('current_stock') + self.quantity_broken
        )

        if self.convert_to_half and self.half_block_type and self.quantity_salvaged > 0:
            BlockType.objects.filter(pk=self.half_block_type.pk).update(
                current_stock=F('current_stock') - self.quantity_salvaged
            )

        super().delete(*args, **kwargs)


# ==============================================================================
# Day 15: Diesel & Transport Management (NEW)
# ==============================================================================

class FuelLog(models.Model):
    """
    Tracks diesel usage.
    Action: Deducts 'DIESEL' stock from Material Inventory.
    """
    DESTINATION_CHOICES = [
        ('TRUCK', 'Truck / Logistics'),
        ('MACHINE', 'Generator / Machine'),
    ]

    date = models.DateField(default=timezone.now)
    destination_type = models.CharField(max_length=10, choices=DESTINATION_CHOICES, default='TRUCK')
    
    # Destination Targets
    truck = models.ForeignKey(Truck, on_delete=models.SET_NULL, null=True, blank=True, related_name='fuel_logs')
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name='fuel_logs')
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Liters dispensed")
    
    # Efficiency Metrics
    current_odometer = models.PositiveIntegerField(null=True, blank=True, help_text="Current KM (for Trucks)")
    engine_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Run hours (for Generators)")
    
    # Financials (Auto-Calculated)
    cost_per_liter = models.DecimalField(max_digits=10, decimal_places=2, editable=False, help_text="Cost at time of dispensing")
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    dispensed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    remark = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Fuel Log"
        verbose_name_plural = "Fuel Logs"

    def __str__(self):
        dest = self.truck.name if self.truck else (self.machine.name if self.machine else "Unknown")
        return f"{self.quantity}L to {dest} ({self.date})"

    def clean(self):
        """Ensure either truck OR machine is selected, matching the type."""
        if self.destination_type == 'TRUCK' and not self.truck:
            raise ValidationError("Please select a Truck.")
        if self.destination_type == 'MACHINE' and not self.machine:
            raise ValidationError("Please select a Machine/Generator.")
        
        # Check stock availability
        diesel = Material.objects.filter(name='DIESEL').first()
        if diesel and self.quantity > diesel.current_stock:
             # Only block if it's a new record (to allow editing old ones without error)
            if self.pk is None:
                raise ValidationError(f"Not enough Diesel! Current Stock: {diesel.current_stock} Liters")

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # 1. Get current Diesel price for cost tracking
        diesel_mat = Material.objects.get(name='DIESEL')
        self.cost_per_liter = diesel_mat.unit_price
        self.total_cost = self.quantity * self.cost_per_liter

        # 2. Handle Inventory Deduction (Reverse old if editing)
        old_qty = Decimal('0')
        if not is_new:
            old_log = FuelLog.objects.get(pk=self.pk)
            old_qty = old_log.quantity
        
        super().save(*args, **kwargs)

        # 3. Update Inventory using F()
        diff = self.quantity - old_qty
        if diff != 0:
            Material.objects.filter(name='DIESEL').update(
                current_stock=F('current_stock') - diff
            )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse inventory deduction
        Material.objects.filter(name='DIESEL').update(
            current_stock=F('current_stock') + self.quantity
        )
        super().delete(*args, **kwargs)


# ==============================================================================
# Audit Registration
# ==============================================================================

auditlog.register(User)
auditlog.register(Material)
auditlog.register(BlockType)
auditlog.register(PaymentAccount)
auditlog.register(BusinessRules)
auditlog.register(Team)
auditlog.register(Machine)
auditlog.register(Customer)
auditlog.register(Site)
auditlog.register(Employee)
auditlog.register(Vendor)
auditlog.register(Truck)
auditlog.register(ExpenseCategory)
auditlog.register(Expense)
auditlog.register(ProcurementLog)
auditlog.register(ProductionLog)
auditlog.register(Payment)
auditlog.register(SalesOrder)
auditlog.register(SalesOrderItem)
auditlog.register(SupplyLog)
auditlog.register(ReturnLog)
auditlog.register(CashRefund)
auditlog.register(BreakageLog)
auditlog.register(FuelLog)