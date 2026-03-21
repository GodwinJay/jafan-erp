from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from auditlog.registry import auditlog
from decimal import Decimal
from django.db.models import F, Sum
from django.core.exceptions import ValidationError


# ==============================================================================
# 1. Authentication
# ==============================================================================

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('GM', 'General Manager'),
        ('SUPPLY', 'Supply Manager'),
        ('SITE', 'Site Manager'),
        ('SALES', 'Sales Representative'),
        ('TRANSPORT', 'Transport Manager'),
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
    
    @property
    def is_transport_only(self):
        return self.role == 'TRANSPORT'


# ==============================================================================
# 2. Materials & Constants
# ==============================================================================

class Material(models.Model):
    NAME_CHOICES = [
        ('CEMENT', 'Cement (Bags)'),
        ('SHARP_SAND', 'Sharp Sand (Tons)'),
        ('BLACK_SAND', 'Black Sand (Tons)'),
        ('DIESEL', 'Diesel (Liters)'),
        ('STONE_DUST', 'Stone Dust (Tons)'),
        ('WATER', 'Water (Liters)'),
    ]
    name = models.CharField(max_length=20, choices=NAME_CHOICES, unique=True)
    is_inventory_tracked = models.BooleanField(default=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    low_stock_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=10.0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_name_display()} ({self.current_stock})"

    @property
    def is_low_stock(self):
        if not self.is_inventory_tracked: return False
        return self.current_stock <= self.low_stock_threshold


class BlockType(models.Model):
    name = models.CharField(max_length=50)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    current_stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=500)
    
    # Financials (COGS)
    weighted_average_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)

    # Recipe
    blocks_per_bag = models.IntegerField(default=0)
    sand_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    batch_size = models.IntegerField(default=1350)

    # Costs
    operator_rate = models.DecimalField(max_digits=10, decimal_places=2, default=35.00)
    loader_rate = models.DecimalField(max_digits=10, decimal_places=2, default=9.00)
    stacking_rate = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    logistics_rate = models.DecimalField(max_digits=10, decimal_places=2, default=65.00)

    is_half_block = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.current_stock})"

    @property
    def total_variable_rate(self):
        return self.operator_rate + self.loader_rate + self.stacking_rate + self.logistics_rate

    @property
    def is_low_stock(self):
        return self.current_stock <= self.low_stock_threshold


class BusinessRules(models.Model):
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

    def __str__(self):
        return f"{self.name}"


class PaymentAccount(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('BANK', 'Bank Account'),
        ('MOBILE', 'Mobile Money'),
        ('POS', 'POS Terminal'),
        ('CASH', 'Cash at Hand'),
    ]
    BUSINESS_UNIT_CHOICES = [
        ('BLOCK', 'Jafan Block Industry'),
        ('TRANSPORT', 'Jafan Transport',),
        ('SAND', 'JAFAN SAND')
    ]
    
    bank_name = models.CharField(max_length=50)
    account_number = models.CharField(max_length=20, blank=True, null=True)
    account_name = models.CharField(max_length=100, default="GC Okoli Enterprises")
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES, default='BANK')
    business_unit = models.CharField(max_length=20, choices=BUSINESS_UNIT_CHOICES, default='BLOCK')
    
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    
    last_audit_date = models.DateField(null=True, blank=True)
    last_audit_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    last_audit_notes = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['business_unit', 'bank_name']

    def __str__(self):
        return f"{self.bank_name} - {self.business_unit}"

    def save(self, *args, **kwargs):
        # On first creation, set current_balance to opening_balance
        if not self.pk:
            self.current_balance = self.opening_balance
        super().save(*args, **kwargs)
    
    @property
    def balance_display(self):
        return f"₦{self.current_balance:,.2f}"

    @property
    def audit_variance(self):
        if self.last_audit_balance is not None:
            return self.current_balance - self.last_audit_balance
        return None



# ==============================================================================
# 3. People & Structure
# ==============================================================================

class Team(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Machine(models.Model):
    name = models.CharField(max_length=50, unique=True)
    machine_type = models.CharField(max_length=20, choices=[('BLOCK', 'Block Machine'), ('MIXER', 'Mixer'), ('GENERATOR', 'Generator'), ('OTHER', 'Other')], default='BLOCK')
    assigned_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, default='OPERATIONAL')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_machine_type_display()})"


class Customer(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=24, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    office_address = models.TextField(blank=True, null=True)
    customer_type = models.CharField(max_length=20, default='INDIVIDUAL')
    account_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True)
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
        if self.account_balance > 0: return "Credit"
        elif self.account_balance < 0: return "Owes"
        return "Settled"


class Site(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sites')
    name = models.CharField(max_length=100)
    address = models.TextField()
    contact_person = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_outside_town = models.BooleanField(default=False)
    blocks_owed = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['customer', 'name']

    def __str__(self):
        return f"{self.customer.name} - {self.name}"


class Employee(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('MANAGER', 'General Manager'),
        ('OPERATIONS', 'Operations Manager'),
        ('SITE_MANAGER', 'Site Manager'),
        ('SALES', 'Sales Assistant'),
        ('TRANSPORT', 'Transport Officer'),
        ('DRIVER', 'Driver'),
        ('OPERATOR', 'Machine Operator'),
        ('CARRIER', 'Loader/Carrier'),
        ('SECURITY', 'Security'),
        ('GENERAL', 'General Worker'),
    ]
    
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True)
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employee_profile',
        help_text="Link to Django user account for login access"
    )
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    pay_type = models.CharField(max_length=10, default='WEEKLY')
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"


# ==============================================================================
# 4. Logistics
# ==============================================================================

class Vendor(models.Model):
    name = models.CharField(max_length=100)
    is_internal = models.BooleanField(default=False)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    supply_type = models.CharField(max_length=20, default='OTHER')
    account_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"
    
    @property
    def balance_status(self):
        if self.account_balance > 0: return "We Owe"
        elif self.account_balance < 0: return "They Owe"
        return "Settled"


class Truck(models.Model):
    name = models.CharField(max_length=50, unique=True)
    plate_number = models.CharField(max_length=20, blank=True)
    truck_type = models.CharField(max_length=20, default='BLOCK')
    driver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'role': 'DRIVER'})
    status = models.CharField(max_length=20, default='AVAILABLE')
    fuel_type = models.CharField(max_length=10, default='DIESEL')
    fuel_capacity = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    benchmark_fuel = models.DecimalField(max_digits=5, decimal_places=2, default=30.00)
    expected_trips = models.IntegerField(default=8)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TransportAsset(models.Model):
    name = models.CharField(max_length=50, unique=True)
    asset_type = models.CharField(max_length=20, default='BIKE')
    plate_number = models.CharField(max_length=20, blank=True)
    assigned_to = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    fuel_type = models.CharField(max_length=10, default='PETROL')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Expense(models.Model):
    date = models.DateField(default=timezone.now)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    business_unit = models.CharField(max_length=20, default='BLOCK')
    
    is_paid = models.BooleanField(default=True)
    payment_date = models.DateField(null=True, blank=True)
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.SET_NULL, null=True, blank=True)

    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    truck = models.ForeignKey(Truck, on_delete=models.SET_NULL, null=True, blank=True)
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    transport_asset = models.ForeignKey(TransportAsset, on_delete=models.SET_NULL, null=True, blank=True)
    driver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_expenses')

    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True)
    is_auto_synced = models.BooleanField(default=False, editable=False)
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} | {self.category.name} | ₦{self.amount:,.2f}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        
        if self.amount is not None and self.amount <= 0:
            errors['amount'] = 'Expense amount must be greater than zero.'
        
        if self.is_paid and not self.payment_account:
            errors['payment_account'] = 'Payment account is required for paid expenses.'
        
        if errors:
            raise ValidationError(errors)

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = Expense.objects.select_for_update().get(pk=self.pk)
            # Reverse Old Financials
            if old.is_paid and old.payment_account:
                PaymentAccount.objects.filter(pk=old.payment_account.pk).update(current_balance=F('current_balance') + old.amount)
            if old.vendor and not old.is_paid:
                Vendor.objects.filter(pk=old.vendor.pk).update(account_balance=F('account_balance') - old.amount)
            elif old.vendor and old.is_paid:
                # If paid, reverting doesn't inherently change vendor balance, assumes expense logic
                pass 

        if self.truck or self.transport_asset: self.business_unit = 'TRANSPORT'
        elif self.machine: self.business_unit = 'BLOCK'
        if self.is_paid and not self.payment_date: self.payment_date = self.date
        
        super().save(*args, **kwargs)
        
        # Apply New Financials
        if self.is_paid and self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(current_balance=F('current_balance') - self.amount)
        
        if self.vendor and not self.is_paid:
            Vendor.objects.filter(pk=self.vendor.pk).update(account_balance=F('account_balance') + self.amount)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        if self.is_paid and self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(current_balance=F('current_balance') + self.amount)
        if self.vendor and not self.is_paid:
            Vendor.objects.filter(pk=self.vendor.pk).update(account_balance=F('account_balance') - self.amount)
        super().delete(*args, **kwargs)


class ProcurementLog(models.Model):
    date = models.DateField()
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)

    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.SET_NULL, null=True, blank=True)
    is_internal_haulage = models.BooleanField(default=False)
    delivery_truck = models.ForeignKey(Truck, on_delete=models.SET_NULL, null=True, blank=True)
    haulage_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    is_paid = models.BooleanField(default=True)
    # REMOVED: expense_entry field - no longer linking to Expense

    remark = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} - {self.material.name} ({self.quantity})"

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = ProcurementLog.objects.select_for_update().get(pk=self.pk)
            # Reverse Stock
            Material.objects.filter(pk=old.material.pk).update(
                current_stock=F('current_stock') - old.quantity
            )
            # Reverse Vendor Balance (if was credit)
            if not old.is_paid and old.vendor:
                Vendor.objects.filter(pk=old.vendor.pk).update(
                    account_balance=F('account_balance') - old.total_cost
                )
            # Reverse Payment Account (if was paid)
            if old.is_paid and old.payment_account:
                PaymentAccount.objects.filter(pk=old.payment_account.pk).update(
                    current_balance=F('current_balance') + old.total_cost
                )
            # Reverse Internal Haulage Credit
            if old.is_internal_haulage and old.haulage_fee > 0:
                t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
                if t_vendor:
                    Vendor.objects.filter(pk=t_vendor.pk).update(
                        account_balance=F('account_balance') - old.haulage_fee
                    )

        # Calculate unit price
        if self.quantity > 0:
            self.unit_price = self.total_cost / self.quantity

        super().save(*args, **kwargs)

        # Apply New Stock
        Material.objects.filter(pk=self.material.pk).update(
            current_stock=F('current_stock') + self.quantity
        )
        # Update material unit price
        Material.objects.filter(pk=self.material.pk).update(unit_price=self.unit_price)

        # Apply Vendor Balance (if credit purchase)
        if not self.is_paid and self.vendor:
            Vendor.objects.filter(pk=self.vendor.pk).update(
                account_balance=F('account_balance') + self.total_cost
            )
        
        # Apply Payment Account (if paid)
        if self.is_paid and self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
                current_balance=F('current_balance') - self.total_cost
            )

        # Apply Internal Haulage
        if self.is_internal_haulage and self.haulage_fee > 0:
            t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
            if t_vendor:
                Vendor.objects.filter(pk=t_vendor.pk).update(
                    account_balance=F('account_balance') + self.haulage_fee
                )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse Stock
        Material.objects.filter(pk=self.material.pk).update(
            current_stock=F('current_stock') - self.quantity
        )
        # Reverse Vendor Balance (if credit)
        if not self.is_paid and self.vendor:
            Vendor.objects.filter(pk=self.vendor.pk).update(
                account_balance=F('account_balance') - self.total_cost
            )
        # Reverse Payment Account (if paid)
        if self.is_paid and self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
                current_balance=F('current_balance') + self.total_cost
            )
        # Reverse Internal Haulage
        if self.is_internal_haulage and self.haulage_fee > 0:
            t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
            if t_vendor:
                Vendor.objects.filter(pk=t_vendor.pk).update(
                    account_balance=F('account_balance') - self.haulage_fee
                )
        super().delete(*args, **kwargs)


# ==============================================================================
# 5. Production
# ==============================================================================

class ProductionLog(models.Model):
    date = models.DateField()
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, limit_choices_to={'machine_type': 'BLOCK'})
    block_type = models.ForeignKey(BlockType, on_delete=models.PROTECT)
    quantity_produced = models.PositiveIntegerField()
    breakages = models.PositiveIntegerField(default=0)

    # Material Usage
    cement_used = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Manual entry: Bags used")
    black_sand_used = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Manual entry: Tons used")
    
    # Auto-Calculated Fields
    sharp_sand_used = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)
    
    # Financials
    team_pay = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0, help_text="Operator's specific cut")
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)

    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date}: {self.block_type.name} (+{self.quantity_produced})"

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = ProductionLog.objects.select_for_update().get(pk=self.pk)
            # Reverse Inventory Effects
            BlockType.objects.filter(pk=old.block_type.pk).update(current_stock=F('current_stock') - old.quantity_produced)
            Material.objects.filter(name='CEMENT').update(current_stock=F('current_stock') + old.cement_used)
            Material.objects.filter(name='BLACK_SAND').update(current_stock=F('current_stock') + old.black_sand_used)
            Material.objects.filter(name='SHARP_SAND').update(current_stock=F('current_stock') + old.sharp_sand_used)

        # 1. Calculate Sharp Sand (Only if ratio is set)
        if self.block_type.batch_size > 0 and self.block_type.sand_ratio > 0:
            batches = Decimal(self.quantity_produced) / Decimal(self.block_type.batch_size)
            self.sharp_sand_used = batches * self.block_type.sand_ratio
        else:
            self.sharp_sand_used = 0 # Prevent ghost costs if ratio is missing
        
        # 2. Calculate Team Pay (Operator Only)
        op_rate = self.block_type.operator_rate
        qty = Decimal(self.quantity_produced)
        self.team_pay = op_rate * qty

        # 3. Calculate Total Labor (Now including Logistics)
        # Formula: Operator + Loader + Stacking + Logistics
        labor_rate = (
            self.block_type.operator_rate + 
            self.block_type.loader_rate + 
            self.block_type.stacking_rate +
            self.block_type.logistics_rate # <--- ADDED LOGISTICS
        )
        self.labor_cost = Decimal(self.quantity_produced) * labor_rate

        # 4. Calculate Unit Cost
        try: cement_p = Material.objects.get(name='CEMENT').unit_price
        except: cement_p = 0
        try: sand_p = Material.objects.get(name='SHARP_SAND').unit_price
        except: sand_p = 0
        try: black_p = Material.objects.get(name='BLACK_SAND').unit_price
        except: black_p = 0
        
        mat_cost = (self.cement_used * cement_p) + (self.sharp_sand_used * sand_p) + (self.black_sand_used * black_p)
        
        rules = BusinessRules.get_instance()
        batches = Decimal(self.quantity_produced) / Decimal(self.block_type.batch_size or 1350)
        overhead = batches * (rules.diesel_power_cost + rules.water_base_cost + rules.miscellaneous_cost)
        
        total_cost = mat_cost + self.labor_cost + overhead
        if self.quantity_produced > 0:
            self.unit_cost = total_cost / Decimal(self.quantity_produced)

        # 5. Update Weighted Average Cost (WAC)
        bt = BlockType.objects.get(pk=self.block_type.pk)
        current_val = bt.current_stock * bt.weighted_average_cost
        new_val = self.quantity_produced * self.unit_cost
        total_qty = bt.current_stock + self.quantity_produced
        
        # Only update WAC if adding stock (not if negative/error)
        if total_qty > 0:
            new_wac = (current_val + new_val) / total_qty
            BlockType.objects.filter(pk=self.block_type.pk).update(weighted_average_cost=new_wac)

        super().save(*args, **kwargs)

        # 6. Apply Inventory Effects
        BlockType.objects.filter(pk=self.block_type.pk).update(current_stock=F('current_stock') + self.quantity_produced)
        Material.objects.filter(name='CEMENT').update(current_stock=F('current_stock') - self.cement_used)
        Material.objects.filter(name='BLACK_SAND').update(current_stock=F('current_stock') - self.black_sand_used)
        Material.objects.filter(name='SHARP_SAND').update(current_stock=F('current_stock') - self.sharp_sand_used)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse all inventory changes
        BlockType.objects.filter(pk=self.block_type.pk).update(current_stock=F('current_stock') - self.quantity_produced)
        Material.objects.filter(name='CEMENT').update(current_stock=F('current_stock') + self.cement_used)
        Material.objects.filter(name='BLACK_SAND').update(current_stock=F('current_stock') + self.black_sand_used)
        Material.objects.filter(name='SHARP_SAND').update(current_stock=F('current_stock') + self.sharp_sand_used)
        super().delete(*args, **kwargs)


# ==============================================================================
# 6. Sales & Supply
# ==============================================================================

class SalesOrder(models.Model):
    STATUS_CHOICES = [('PENDING', 'Pending Payment'), ('PARTIAL', 'Partially Supplied'), ('COMPLETED', 'Fully Supplied'), ('CANCELLED', 'Cancelled')]
    date = models.DateField(default=timezone.now)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='sales_orders')
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    surcharge_per_block = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return f"SO-{self.pk:05d} - {self.customer.name}"

    def save(self, *args, **kwargs):
        if not self.valid_until: self.valid_until = self.date + timezone.timedelta(days=14)
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
        if total == 0: return 0
        return int((self.total_quantity_supplied / total) * 100)

    @property
    def total_value(self):
        return sum(item.line_total for item in self.items.all())
    
    @property
    def is_valid(self):
        if self.valid_until: return timezone.now().date() <= self.valid_until
        return True


class SalesOrderItem(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('PER_BLOCK', 'Per Block'),
        ('BULK', 'Bulk (Fixed Amount)'),
    ]

    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    block_type = models.ForeignKey(BlockType, on_delete=models.PROTECT)
    quantity_requested = models.PositiveIntegerField()
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_supplied = models.PositiveIntegerField(default=0)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='PER_BLOCK')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_reason = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.quantity_requested} x {self.block_type.name}"

    def save(self, *args, **kwargs):
        base = self.block_type.selling_price
        surcharge = self.order.surcharge_per_block if self.order_id else Decimal('0.00')
        if self.discount_type == 'BULK':
            # agreed_price = undiscounted unit price; bulk discount applied at line level
            self.agreed_price = base + surcharge
        else:
            self.agreed_price = base - self.discount_value + surcharge
        super().save(*args, **kwargs)

    @property
    def line_total(self):
        total = self.quantity_requested * self.agreed_price
        if self.discount_type == 'BULK':
            total -= self.discount_value
        return total


class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='payments')
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=[('TRANSFER', 'Bank Transfer'), ('CASH', 'Cash'), ('POS', 'POS'), ('CHEQUE', 'Cheque')], default='TRANSFER')
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT)
    reference = models.CharField(max_length=100, blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Payment: ₦{self.amount:,.2f} from {self.customer.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than zero.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = Payment.objects.select_for_update().get(pk=self.pk)
            Customer.objects.filter(pk=old.customer.pk).update(account_balance=F('account_balance') - old.amount)
            if old.payment_account:
                PaymentAccount.objects.filter(pk=old.payment_account.pk).update(current_balance=F('current_balance') - old.amount)

        super().save(*args, **kwargs)

        Customer.objects.filter(pk=self.customer.pk).update(account_balance=F('account_balance') + self.amount)
        if self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(current_balance=F('current_balance') + self.amount)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        Customer.objects.filter(pk=self.customer.pk).update(account_balance=F('account_balance') - self.amount)
        if self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(current_balance=F('current_balance') - self.amount)
        super().delete(*args, **kwargs)


class SupplyLog(models.Model):
    DELIVERY_TYPE_CHOICES = [('DELIVERED', 'Company Delivery'), ('SELF_PICKUP', 'Customer Self-Pickup')]
    date = models.DateField(default=timezone.now)
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_TYPE_CHOICES, default='DELIVERED')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='supplies')
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='supplies')
    order_item = models.ForeignKey(SalesOrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='supplies')
    block_type = models.ForeignKey(BlockType, on_delete=models.PROTECT, related_name='supplies')
    quantity_loaded = models.PositiveIntegerField()
    breakages = models.PositiveIntegerField(default=0)
    quantity_returned = models.PositiveIntegerField(default=0)
    quantity_delivered = models.PositiveIntegerField(editable=False, default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    logistics_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_value = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=Decimal('0.00'))
    logistics_income = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False)
    # COGS Fields - Frozen at time of sale for accurate P&L
    cost_of_goods_sold = models.DecimalField(
        max_digits=12, decimal_places=2,
        editable=False, default=Decimal('0.00'),
        help_text="Frozen: quantity_delivered × WAC at time of sale"
    )
    gross_profit_on_sale = models.DecimalField(
        max_digits=12, decimal_places=2,
        editable=False, default=Decimal('0.00'),
        help_text="total_value - cost_of_goods_sold"
    )
    truck = models.ForeignKey(Truck, on_delete=models.SET_NULL, null=True, blank=True, related_name='supplies')
    driver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries', limit_choices_to={'role': 'DRIVER'})
    pickup_authorized_by = models.CharField(max_length=100, blank=True)
    remark = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_supplies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Supply Log"
        verbose_name_plural = "Supply Logs"

    def __str__(self):
        return f"{self.date}: {self.quantity_delivered} {self.block_type.name} -> {self.customer.name}"

    def clean(self):
        if self.breakages + self.quantity_returned > self.quantity_loaded:
            raise ValidationError("Breakages + Returned cannot exceed Quantity Loaded.")
        if self.delivery_type == 'DELIVERED' and not self.truck:
            raise ValidationError({'truck': "Truck is required for Company Delivery."})
        if self.delivery_type == 'SELF_PICKUP' and not self.pickup_authorized_by:
            raise ValidationError({'pickup_authorized_by': "Authorization required for Self-Pickup."})
        
        # Validate quantity doesn't exceed order item remaining
        if self.order_item:
            quantity_to_deliver = self.quantity_loaded - self.breakages - self.quantity_returned
            remaining = self.order_item.quantity_requested - self.order_item.quantity_supplied
            
            # If editing, add back the old quantity_delivered to remaining
            if self.pk:
                old = SupplyLog.objects.get(pk=self.pk)
                if old.order_item_id == self.order_item_id:
                    remaining += old.quantity_delivered
            
            if quantity_to_deliver > remaining:
                raise ValidationError({
                    'quantity_loaded': f"Cannot supply {quantity_to_deliver} blocks. Only {remaining} remaining on this order item."
                })
        
        # Credit Check
        if self.order_item:
            price = self.order_item.agreed_price
        elif self.unit_price:
            price = self.unit_price
        else:
            price = self.block_type.selling_price
        
        qty = self.quantity_loaded - self.breakages - self.quantity_returned
        new_debt = (qty * price) - (self.logistics_discount or 0)
        current_bal = self.customer.account_balance
        if self.pk:
            old = SupplyLog.objects.get(pk=self.pk)
            current_bal += old.total_value  # Add back old debit
        projected = current_bal - new_debt
        if projected < 0 and abs(projected) > self.customer.credit_limit:
            raise ValidationError(f"Credit Limit Exceeded! Projected Balance: {projected}, Limit: {self.customer.credit_limit}")

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        
        if is_edit:
            old = SupplyLog.objects.select_for_update().get(pk=self.pk)
            # REVERSE OLD
            net_deduction = old.quantity_loaded - old.quantity_returned
            BlockType.objects.filter(pk=old.block_type.pk).update(
                current_stock=F('current_stock') + net_deduction
            )
            Customer.objects.filter(pk=old.customer.pk).update(
                account_balance=F('account_balance') + old.total_value
            )
            
            if old.order_item:
                SalesOrderItem.objects.filter(pk=old.order_item.pk).update(
                    quantity_supplied=F('quantity_supplied') - old.quantity_delivered
                )
                self._update_order_status(old.sales_order)
            
            if old.delivery_type == 'DELIVERED' and old.logistics_income > 0:
                t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
                if t_vendor:
                    Vendor.objects.filter(pk=t_vendor.pk).update(
                        account_balance=F('account_balance') - old.logistics_income
                    )

        # SETUP NEW
        if self.order_item:
            self.unit_price = self.order_item.agreed_price
            self.block_type = self.order_item.block_type
            if self.order_item.order:
                self.sales_order = self.order_item.order
        if not self.unit_price:
            self.unit_price = self.block_type.selling_price

        self.quantity_delivered = self.quantity_loaded - self.breakages - self.quantity_returned
        self.total_value = (self.quantity_delivered * self.unit_price) - self.logistics_discount
        
        # Calculate logistics income (Base Rate + Surcharge)
        logistics_base = self.quantity_delivered * self.block_type.logistics_rate
        surcharge = Decimal('0')
        if self.sales_order and self.sales_order.surcharge_per_block:
            surcharge = Decimal(self.quantity_delivered) * self.sales_order.surcharge_per_block
        self.logistics_income = logistics_base + surcharge

        # Calculate COGS - Freeze WAC at time of sale
        current_wac = self.block_type.weighted_average_cost or Decimal('0.00')
        self.cost_of_goods_sold = Decimal(self.quantity_delivered) * current_wac
        
        # Subtract ONLY surcharge from gross profit
        self.gross_profit_on_sale = self.total_value - self.cost_of_goods_sold - surcharge

        super().save(*args, **kwargs)

        # APPLY NEW
        new_net = self.quantity_loaded - self.quantity_returned
        BlockType.objects.filter(pk=self.block_type.pk).update(
            current_stock=F('current_stock') - new_net
        )
        Customer.objects.filter(pk=self.customer.pk).update(
            account_balance=F('account_balance') - self.total_value
        )
        
        if self.order_item:
            SalesOrderItem.objects.filter(pk=self.order_item.pk).update(
                quantity_supplied=F('quantity_supplied') + self.quantity_delivered
            )
            self._update_order_status(self.sales_order)
        
        if self.delivery_type == 'DELIVERED' and self.logistics_income > 0:
            t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
            if t_vendor:
                Vendor.objects.filter(pk=t_vendor.pk).update(
                    account_balance=F('account_balance') + self.logistics_income
                )

        # AUTO-CREATE BREAKAGE LOG
        self._sync_breakage_log()

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Delete auto-created breakage logs first
        BreakageLog.objects.filter(supply_log=self, is_auto_created=True).delete()

        net_deduction = self.quantity_loaded - self.quantity_returned
        BlockType.objects.filter(pk=self.block_type.pk).update(
            current_stock=F('current_stock') + net_deduction
        )
        Customer.objects.filter(pk=self.customer.pk).update(
            account_balance=F('account_balance') + self.total_value
        )
        
        order_to_update = self.sales_order
        if self.order_item:
            SalesOrderItem.objects.filter(pk=self.order_item.pk).update(
                quantity_supplied=F('quantity_supplied') - self.quantity_delivered
            )
        
        if self.delivery_type == 'DELIVERED' and self.logistics_income > 0:
            t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
            if t_vendor:
                Vendor.objects.filter(pk=t_vendor.pk).update(
                    account_balance=F('account_balance') - self.logistics_income
                )
            
        super().delete(*args, **kwargs)
        if order_to_update:
            self._update_order_status(order_to_update)

    def _update_order_status(self, order):
        if order:
            total_ordered = sum(i.quantity_requested for i in order.items.all())
            total_supplied = sum(i.quantity_supplied for i in order.items.all())
            if total_ordered == 0:
                order.status = 'PENDING'
            elif total_supplied >= total_ordered:
                order.status = 'COMPLETED'
            elif total_supplied > 0:
                order.status = 'PARTIAL'
            else:
                order.status = 'PENDING'
            order.save()

    def _sync_breakage_log(self):
        """Auto-create/update BreakageLog for supply breakages."""
        # Delete any existing auto-created breakage log for this supply
        BreakageLog.objects.filter(supply_log=self, is_auto_created=True).delete()
        
        # Create new breakage log if there are breakages
        if self.breakages > 0:
            BreakageLog.objects.create(
                date=self.date,
                block_type=self.block_type,
                quantity_broken=self.breakages,
                reason='LOADING_OFFLOADING',
                description=f"Auto-logged from Supply #{self.pk} to {self.customer.name}",
                recorded_by=self.recorded_by,
                approved_by=None,
                supply_log=self,
                is_auto_created=True,
                convert_to_half=False,
            )


# ==============================================================================
# 7. Returns & Refunds
# ==============================================================================

class ReturnLog(models.Model):
    CONDITION_CHOICES = [('GOOD', 'Good'), ('HALF', 'Broken (Half)'), ('DAMAGED', 'Damaged')]
    date = models.DateField(default=timezone.now)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='returns')
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    original_supply = models.ForeignKey(SupplyLog, on_delete=models.SET_NULL, null=True, blank=True)
    block_type = models.ForeignKey(BlockType, on_delete=models.PROTECT)
    quantity_returned = models.PositiveIntegerField()
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='GOOD')
    restock_as = models.ForeignKey(BlockType, on_delete=models.SET_NULL, null=True, blank=True, related_name='restocked_returns')
    
    credit_customer = models.BooleanField(default=False)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    restocking_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    credit_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False)

    reason = models.TextField()
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='approved_returns')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_returns')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Return: {self.quantity_returned} {self.block_type.name} from {self.customer.name}"

    def clean(self):
        if self.original_supply:
            if self.quantity_returned > self.original_supply.quantity_delivered:
                raise ValidationError("Returned quantity cannot exceed original delivered quantity.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = ReturnLog.objects.select_for_update().get(pk=self.pk)
            # Reverse Old
            if old.credit_customer and old.credit_value > 0:
                Customer.objects.filter(pk=old.customer.pk).update(account_balance=F('account_balance') - old.credit_value)
            if old.condition != 'DAMAGED':
                target = old.restock_as if old.restock_as else old.block_type
                BlockType.objects.filter(pk=target.pk).update(current_stock=F('current_stock') - old.quantity_returned)

        if self.credit_customer:
            self.credit_value = (self.quantity_returned * self.unit_price) - (self.quantity_returned * self.restocking_fee)
            if self.credit_value < 0: self.credit_value = 0
        else: self.credit_value = 0

        super().save(*args, **kwargs)

        # Apply New
        if self.credit_customer and self.credit_value > 0:
            Customer.objects.filter(pk=self.customer.pk).update(account_balance=F('account_balance') + self.credit_value)
        if self.condition != 'DAMAGED':
            target = self.restock_as if self.restock_as else self.block_type
            BlockType.objects.filter(pk=target.pk).update(current_stock=F('current_stock') + self.quantity_returned)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        if self.credit_customer and self.credit_value > 0:
            Customer.objects.filter(pk=self.customer.pk).update(account_balance=F('account_balance') - self.credit_value)
        if self.condition != 'DAMAGED':
            target = self.restock_as if self.restock_as else self.block_type
            BlockType.objects.filter(pk=target.pk).update(current_stock=F('current_stock') - self.quantity_returned)
        super().delete(*args, **kwargs)


class CashRefund(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='refunds')
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT)
    reason = models.TextField()
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='approved_refunds')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False, related_name='recorded_refunds')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = CashRefund.objects.select_for_update().get(pk=self.pk)
            Customer.objects.filter(pk=old.customer.pk).update(account_balance=F('account_balance') + old.amount)
            if old.payment_account:
                PaymentAccount.objects.filter(pk=old.payment_account.pk).update(current_balance=F('current_balance') + old.amount)

        super().save(*args, **kwargs)

        Customer.objects.filter(pk=self.customer.pk).update(account_balance=F('account_balance') - self.amount)
        if self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(current_balance=F('current_balance') - self.amount)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        Customer.objects.filter(pk=self.customer.pk).update(account_balance=F('account_balance') + self.amount)
        if self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(current_balance=F('current_balance') + self.amount)
        super().delete(*args, **kwargs)


class BreakageLog(models.Model):
    date = models.DateField(default=timezone.now)
    block_type = models.ForeignKey(BlockType, on_delete=models.PROTECT, related_name='breakages')
    quantity_broken = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=[
        ('STACKING', 'Stacking'), 
        ('HANDLING', 'Handling'),
        ('LOADING_OFFLOADING', 'Loading/Offloading'),  # NEW
    ], default='HANDLING')
    description = models.TextField(blank=True)
    convert_to_half = models.BooleanField(default=False)
    half_block_type = models.ForeignKey(BlockType, on_delete=models.SET_NULL, null=True, blank=True, related_name='salvaged_from_breakages')
    quantity_salvaged = models.PositiveIntegerField(default=0)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_breakages')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_breakages')  # Changed to allow null for auto-entries
    supply_log = models.ForeignKey('SupplyLog', on_delete=models.SET_NULL, null=True, blank=True, related_name='breakage_logs')  # NEW - Link to source
    is_auto_created = models.BooleanField(default=False, editable=False)  # NEW - Flag for auto entries
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Skip approved_by validation for auto-created entries
        if not self.is_auto_created and not self.approved_by:
            raise ValidationError({'approved_by': 'Approved by is required for manual entries.'})
        
        if self.convert_to_half:
            if not self.half_block_type:
                raise ValidationError({'half_block_type': 'You must select a half block type when converting.'})
            if self.half_block_type and not self.half_block_type.is_half_block:
                raise ValidationError({'half_block_type': 'Selected block type must be a half block.'})
            if self.quantity_salvaged <= 0 and self.quantity_broken > 0:
                pass  # Auto-set in save(), so this is optional

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = BreakageLog.objects.select_for_update().get(pk=self.pk)
            BlockType.objects.filter(pk=old.block_type.pk).update(current_stock=F('current_stock') + old.quantity_broken)
            if old.convert_to_half and old.half_block_type:
                BlockType.objects.filter(pk=old.half_block_type.pk).update(current_stock=F('current_stock') - old.quantity_salvaged)

        if self.convert_to_half and self.quantity_salvaged == 0:
            self.quantity_salvaged = self.quantity_broken * 2
        
        super().save(*args, **kwargs)

        # Only deduct stock if NOT auto-created (SupplyLog already deducted breakages from loaded qty)
        if not self.is_auto_created:
            BlockType.objects.filter(pk=self.block_type.pk).update(current_stock=F('current_stock') - self.quantity_broken)
        
        if self.convert_to_half and self.half_block_type:
            BlockType.objects.filter(pk=self.half_block_type.pk).update(current_stock=F('current_stock') + self.quantity_salvaged)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Only restore stock if NOT auto-created
        if not self.is_auto_created:
            BlockType.objects.filter(pk=self.block_type.pk).update(current_stock=F('current_stock') + self.quantity_broken)
        
        if self.convert_to_half and self.half_block_type:
            BlockType.objects.filter(pk=self.half_block_type.pk).update(current_stock=F('current_stock') - self.quantity_salvaged)
        super().delete(*args, **kwargs)


class FuelLog(models.Model):
    DESTINATION_CHOICES = [('TRUCK', 'Truck'), ('MACHINE', 'Generator'), ('ASSET', 'Asset')]
    FUEL_TYPE_CHOICES = [('DIESEL', 'Diesel'), ('PETROL', 'Petrol'), ('ENGINE_OIL', 'Oil')]
    
    date = models.DateField(default=timezone.now)
    destination_type = models.CharField(max_length=10, choices=DESTINATION_CHOICES, default='TRUCK')
    fuel_type = models.CharField(max_length=15, choices=FUEL_TYPE_CHOICES, default='DIESEL')
    
    truck = models.ForeignKey(Truck, on_delete=models.SET_NULL, null=True, blank=True, related_name='fuel_logs')
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name='fuel_logs')
    transport_asset = models.ForeignKey(TransportAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name='fuel_logs')
    
    driver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='fuel_received')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    engine_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    cost_per_liter = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    fuel_station = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=20, default='CASH')
    is_paid = models.BooleanField(default=True)
    payment_account = models.ForeignKey(
        PaymentAccount, on_delete=models.PROTECT, null=True, blank=True,
        help_text="Required if paid"
    )
    dispensed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    remark = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Fuel Log"
        verbose_name_plural = "Fuel Logs"

    def __str__(self):
        dest = self.truck.name if self.truck else (self.machine.name if self.machine else "Asset")
        return f"{self.quantity}L {self.fuel_type} to {dest}"

    def clean(self):
        if self.destination_type == 'TRUCK' and not self.truck:
            raise ValidationError("Select a Truck.")
        if self.destination_type == 'MACHINE' and not self.machine:
            raise ValidationError("Select a Machine.")
        if self.destination_type == 'ASSET' and not self.transport_asset:
            raise ValidationError("Select a Transport Asset.")
        if self.is_paid and not self.payment_account:
            raise ValidationError({'payment_account': 'Payment account is required when marked as paid.'})
        
        # STOCK CHECK FOR DIESEL
        if self.pk is None and self.fuel_type == 'DIESEL':
            diesel = Material.objects.filter(name='DIESEL').first()
            if diesel and self.quantity > diesel.current_stock:
                raise ValidationError(f"Not enough Diesel! Current Stock: {diesel.current_stock}")

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        
        if is_edit:
            old = FuelLog.objects.select_for_update().get(pk=self.pk)
            # Reverse old diesel stock
            if old.fuel_type == 'DIESEL':
                Material.objects.filter(name='DIESEL').update(current_stock=F('current_stock') + old.quantity)
            # Reverse old payment
            if old.is_paid and old.payment_account:
                PaymentAccount.objects.filter(pk=old.payment_account.pk).update(
                    current_balance=F('current_balance') + old.total_cost
                )

        if self.fuel_type == 'DIESEL' and not self.cost_per_liter:
            mat = Material.objects.filter(name='DIESEL').first()
            if mat:
                self.cost_per_liter = mat.unit_price
        
        self.total_cost = self.quantity * self.cost_per_liter
        super().save(*args, **kwargs)

        # Apply new diesel stock
        if self.fuel_type == 'DIESEL':
            Material.objects.filter(name='DIESEL').update(current_stock=F('current_stock') - self.quantity)
        
        # Apply new payment
        if self.is_paid and self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
                current_balance=F('current_balance') - self.total_cost
            )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse diesel stock
        if self.fuel_type == 'DIESEL':
            Material.objects.filter(name='DIESEL').update(current_stock=F('current_stock') + self.quantity)
        # Reverse payment
        if self.is_paid and self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
                current_balance=F('current_balance') + self.total_cost
            )
        super().delete(*args, **kwargs)


class MaintenanceLog(models.Model):
    TARGET_CHOICES = [('TRUCK', 'Truck'), ('MACHINE', 'Machine'), ('ASSET', 'Asset')]
    date = models.DateField(default=timezone.now)
    target_type = models.CharField(max_length=10, choices=TARGET_CHOICES, default='TRUCK')
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, null=True, blank=True, related_name="maintenance_logs")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, null=True, blank=True, related_name="maintenance_logs")
    transport_asset = models.ForeignKey(TransportAsset, on_delete=models.CASCADE, null=True, blank=True, related_name="maintenance_logs")
    
    service_type = models.CharField(max_length=20, choices=[('ROUTINE', 'Routine'), ('REPAIR', 'Repair')])
    description = models.TextField()
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, default='CASH')
    payment_account = models.ForeignKey('PaymentAccount', on_delete=models.SET_NULL, null=True, blank=True)
    
    expense_entry = models.OneToOneField(Expense, on_delete=models.SET_NULL, null=True, blank=True, editable=False)
    next_service_date = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        target = self.truck.name if self.truck else (self.machine.name if self.machine else (self.transport_asset.name if self.transport_asset else "Unknown"))
        return f"{target} - {self.service_type} ({self.date})"

    def clean(self):
        if self.target_type == 'TRUCK' and not self.truck: raise ValidationError("Select a Truck.")
        if self.target_type == 'MACHINE' and not self.machine: raise ValidationError("Select a Machine.")
        if self.target_type == 'ASSET' and not self.transport_asset: raise ValidationError("Select a Transport Asset.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.truck or self.transport_asset: 
            b_unit = 'TRANSPORT'
        else: 
            b_unit = 'BLOCK'
        
        target_name = self.truck.name if self.truck else (self.machine.name if self.machine else (self.transport_asset.name if self.transport_asset else "Unknown"))
        cat, _ = ExpenseCategory.objects.get_or_create(name="Maintenance and Repair")
        desc = f"Auto: {self.service_type} - {target_name}"

        if not self.expense_entry:
            self.expense_entry = Expense.objects.create(
                date=self.date, category=cat, description=desc, amount=self.cost,
                business_unit=b_unit, is_paid=True, payment_account=self.payment_account,
                vendor=self.vendor, truck=self.truck, machine=self.machine, 
                transport_asset=self.transport_asset,
                is_auto_synced=True, recorded_by=self.recorded_by
            )
        else:
            self.expense_entry.date = self.date
            self.expense_entry.description = desc
            self.expense_entry.amount = self.cost
            self.expense_entry.business_unit = b_unit
            self.expense_entry.payment_account = self.payment_account
            self.expense_entry.save()
        
        super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        if self.expense_entry: 
            self.expense_entry.delete()
        super().delete(*args, **kwargs)


class TransportRevenue(models.Model):
    date = models.DateField(default=timezone.now)
    job_type = models.CharField(max_length=20, default='WATER')
    truck = models.ForeignKey(Truck, on_delete=models.PROTECT, related_name='revenue_logs')
    driver = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='transport_jobs')
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    delivery_address = models.TextField(blank=True, null=True)
    trips = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=True)
    payment_method = models.CharField(max_length=20, default='CASH')
    payment_account = models.ForeignKey(
        PaymentAccount, on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'business_unit': 'TRANSPORT'},
        help_text="Required if paid"
    )
    description = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} | {self.job_type} | ₦{self.amount:,.2f}"

    def clean(self):
        if self.is_paid and not self.payment_account:
            raise ValidationError({'payment_account': 'Payment account is required when marked as paid.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None

        if is_edit:
            old = TransportRevenue.objects.select_for_update().get(pk=self.pk)
            # Reverse old payment
            if old.is_paid and old.payment_account:
                PaymentAccount.objects.filter(pk=old.payment_account.pk).update(
                    current_balance=F('current_balance') - old.amount
                )

        super().save(*args, **kwargs)

        # Apply new payment
        if self.is_paid and self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
                current_balance=F('current_balance') + self.amount
            )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse payment
        if self.is_paid and self.payment_account:
            PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
                current_balance=F('current_balance') - self.amount
            )
        super().delete(*args, **kwargs)


class BankCharge(models.Model):
    date = models.DateField(default=timezone.now)
    account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT, related_name='bank_charges')
    charge_type = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = BankCharge.objects.select_for_update().get(pk=self.pk)
            PaymentAccount.objects.filter(pk=old.account.pk).update(current_balance=F('current_balance') + old.amount)
        
        super().save(*args, **kwargs)
        PaymentAccount.objects.filter(pk=self.account.pk).update(current_balance=F('current_balance') - self.amount)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        PaymentAccount.objects.filter(pk=self.account.pk).update(current_balance=F('current_balance') + self.amount)
        super().delete(*args, **kwargs)


class AccountTransfer(models.Model):
    date = models.DateField(default=timezone.now)
    from_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT, related_name='transfers_out')
    to_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT, related_name='transfers_in')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=200, blank=True)
    is_transport_settlement = models.BooleanField(default=False)
    expense_entry = models.OneToOneField(Expense, on_delete=models.SET_NULL, null=True, blank=True, editable=False)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.from_account == self.to_account: raise ValidationError("Cannot transfer to same account.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = AccountTransfer.objects.select_for_update().get(pk=self.pk)
            PaymentAccount.objects.filter(pk=old.from_account.pk).update(current_balance=F('current_balance') + old.amount)
            PaymentAccount.objects.filter(pk=old.to_account.pk).update(current_balance=F('current_balance') - old.amount)
            if old.is_transport_settlement:
                t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
                if t_vendor: Vendor.objects.filter(pk=t_vendor.pk).update(account_balance=F('account_balance') + old.amount)

        super().save(*args, **kwargs)

        PaymentAccount.objects.filter(pk=self.from_account.pk).update(current_balance=F('current_balance') - self.amount)
        PaymentAccount.objects.filter(pk=self.to_account.pk).update(current_balance=F('current_balance') + self.amount)
        
        if self.is_transport_settlement:
            if not self.expense_entry:
                cat, _ = ExpenseCategory.objects.get_or_create(name="Internal Transfer - Transport")
                self.expense_entry = Expense.objects.create(
                    date=self.date, category=cat, description=f"Settlement: {self.reference}",
                    amount=self.amount, payment_account=self.from_account, is_auto_synced=True, recorded_by=self.recorded_by
                )
                AccountTransfer.objects.filter(pk=self.pk).update(expense_entry=self.expense_entry)
            
            t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
            if t_vendor: Vendor.objects.filter(pk=t_vendor.pk).update(account_balance=F('account_balance') - self.amount)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        PaymentAccount.objects.filter(pk=self.from_account.pk).update(current_balance=F('current_balance') + self.amount)
        PaymentAccount.objects.filter(pk=self.to_account.pk).update(current_balance=F('current_balance') - self.amount)
        if self.is_transport_settlement:
            t_vendor = Vendor.objects.filter(is_internal=True, supply_type='TRANSPORT').first()
            if t_vendor: Vendor.objects.filter(pk=t_vendor.pk).update(account_balance=F('account_balance') + self.amount)
        if self.expense_entry: self.expense_entry.delete()
        super().delete(*args, **kwargs)


class DailyCashClose(models.Model):
    STATUS_CHOICES = [('BALANCED', 'Balanced'), ('SHORT', 'Shortage'), ('EXCESS', 'Excess')]
    account = models.ForeignKey(PaymentAccount, on_delete=models.CASCADE, limit_choices_to={'account_type': 'CASH'}, related_name='daily_closes')
    date = models.DateField(default=timezone.now)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    system_balance_at_close = models.DecimalField(max_digits=12, decimal_places=2)
    physical_cash_count = models.DecimalField(max_digits=12, decimal_places=2)
    difference = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, editable=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def save(self, *args, **kwargs):
        if not self.pk and self.account: self.system_balance_at_close = self.account.current_balance
        self.difference = self.physical_cash_count - self.system_balance_at_close
        if self.difference == 0: self.status = 'BALANCED'
        elif self.difference < 0: self.status = 'SHORT'
        else: self.status = 'EXCESS'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} - {self.account} ({self.get_status_display()})"
    


class VendorPayment(models.Model):
    """Records payments made TO vendors to settle credit purchases."""
    date = models.DateField(default=timezone.now)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='payments_received')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT)
    reference = models.CharField(max_length=100, blank=True, null=True)
    description = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Payment to {self.vendor.name}: ₦{self.amount:,.2f}"

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than zero.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        if is_edit:
            old = VendorPayment.objects.select_for_update().get(pk=self.pk)
            # Reverse old
            Vendor.objects.filter(pk=old.vendor.pk).update(
                account_balance=F('account_balance') + old.amount
            )
            PaymentAccount.objects.filter(pk=old.payment_account.pk).update(
                current_balance=F('current_balance') + old.amount
            )

        super().save(*args, **kwargs)

        # Apply new
        Vendor.objects.filter(pk=self.vendor.pk).update(
            account_balance=F('account_balance') - self.amount
        )
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') - self.amount
        )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        Vendor.objects.filter(pk=self.vendor.pk).update(
            account_balance=F('account_balance') + self.amount
        )
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') + self.amount
        )
        super().delete(*args, **kwargs)




class TeamPayment(models.Model):
    """
    Records payments made to production teams/workers for their work.
    This affects PaymentAccount balance and shows in Cash Flow,
    but does NOT appear in P&L expenses (already captured in COGS via WAC).
    """
    PAYMENT_TYPE_CHOICES = [
        ('TEAM_PAY', 'Team Production Pay'),
        ('STACKING', 'Stacking Payment'),
        ('LOADING', 'Loading Payment'),
        ('OTHER', 'Other Production Labor'),
    ]
    
    date = models.DateField(default=timezone.now)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='TEAM_PAY')
    team = models.ForeignKey(Team, on_delete=models.PROTECT, null=True, blank=True, 
                             help_text="Select team for production pay")
    employee = models.ForeignKey('Employee', on_delete=models.PROTECT, null=True, blank=True,
                                 help_text="Select employee for individual payments")
    
    # Period covered (OPTIONAL - mainly for team production pay)
    period_start = models.DateField(null=True, blank=True, help_text="Start of work period (optional)")
    period_end = models.DateField(null=True, blank=True, help_text="End of work period (optional)")
    
    # Amounts
    calculated_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        help_text="Auto-calculated from ProductionLog (for team pay only)"
    )
    amount_paid = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Actual amount paid"
    )
    
    # Payment details
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT)
    reference = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, help_text="E.g., 'Daily loading for 500 blocks' or 'Stacking at Customer X site'")
    
    # Tracking
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Team Payment"
        verbose_name_plural = "Team Payments"

    def __str__(self):
        if self.team:
            return f"{self.get_payment_type_display()} - {self.team.name}: ₦{self.amount_paid:,.2f}"
        elif self.employee:
            return f"{self.get_payment_type_display()} - {self.employee.name}: ₦{self.amount_paid:,.2f}"
        return f"{self.get_payment_type_display()}: ₦{self.amount_paid:,.2f}"

    def calculate_team_pay(self):
        """Calculate expected team pay from ProductionLog for the period."""
        if not self.team or not self.period_start or not self.period_end:
            return Decimal('0')
        
        total = ProductionLog.objects.filter(
            team=self.team,
            date__gte=self.period_start,
            date__lte=self.period_end
        ).aggregate(total=Sum('team_pay'))['total'] or Decimal('0')
        
        return total

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        
        # Auto-calculate team pay ONLY if team and period are set
        if self.team and self.period_start and self.period_end:
            self.calculated_amount = self.calculate_team_pay()
        
        if is_edit:
            old = TeamPayment.objects.select_for_update().get(pk=self.pk)
            # Reverse old payment account deduction
            PaymentAccount.objects.filter(pk=old.payment_account.pk).update(
                current_balance=F('current_balance') + old.amount_paid
            )

        super().save(*args, **kwargs)

        # Apply new payment account deduction
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') - self.amount_paid
        )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse payment account deduction
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') + self.amount_paid
        )
        super().delete(*args, **kwargs)


# ==============================================================================
# 8. Sand Sales
# ==============================================================================

class SandVehicleType(models.Model):
    """Vehicle types that determine sand quantity and price."""
    name = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Sand Vehicle Type"
        verbose_name_plural = "Sand Vehicle Types"

    def __str__(self):
        return f"{self.name} - ₦{self.price:,.2f}"


class SandSale(models.Model):
    """Records sand sales (walk-in cash sales, no credit)."""
    date = models.DateField(default=timezone.now)
    vehicle_type = models.ForeignKey(SandVehicleType, on_delete=models.PROTECT, related_name='sales')
    quantity = models.PositiveIntegerField(default=1, help_text="Number of vehicles")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT)
    
    # Optional customer info for walk-ins
    customer_name = models.CharField(max_length=100, blank=True, help_text="Optional - for walk-in customers")
    customer_phone = models.CharField(max_length=20, blank=True)
    
    remark = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Sand Sale"
        verbose_name_plural = "Sand Sales"

    def __str__(self):
        return f"{self.date} | {self.quantity}x {self.vehicle_type.name} | ₦{self.total_amount:,.2f}"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be at least 1.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        
        if is_edit:
            old = SandSale.objects.select_for_update().get(pk=self.pk)
            # Reverse old payment account credit
            PaymentAccount.objects.filter(pk=old.payment_account.pk).update(
                current_balance=F('current_balance') - old.total_amount
            )

        # Calculate totals
        self.unit_price = self.vehicle_type.price
        self.total_amount = self.quantity * self.unit_price

        super().save(*args, **kwargs)

        # Apply new payment account credit
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') + self.total_amount
        )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse payment account credit
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') - self.total_amount
        )
        super().delete(*args, **kwargs)



class QuickSale(models.Model):
    """
    Quick cash-and-carry sales for walk-in customers.
    No customer account needed - just record the sale and payment.
    Supports split payments (e.g., part cash, part POS).
    """
    date = models.DateField(default=timezone.now)
    
    # What was sold
    block_type = models.ForeignKey(BlockType, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, 
        editable=False,
        help_text="Auto-filled from block type selling price"
    )
    logistics_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Discount per block for self-pickup (e.g., ₦50/block)"
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    # Primary Payment (required)
    payment_account = models.ForeignKey(
        PaymentAccount, on_delete=models.PROTECT,
        limit_choices_to={'is_active': True},
        related_name='quick_sales_primary',
        verbose_name="Primary Account"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('CASH', 'Cash'),
            ('TRANSFER', 'Bank Transfer'),
            ('POS', 'POS'),
        ],
        default='CASH',
        verbose_name="Primary Method"
    )
    reference = models.CharField(max_length=100, blank=True, help_text="Transfer reference or POS receipt")
    
    # Secondary Payment (optional - for split payments)
    secondary_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Amount paid via secondary method (leave 0 if single payment)"
    )
    secondary_account = models.ForeignKey(
        PaymentAccount, on_delete=models.PROTECT,
        null=True, blank=True,
        limit_choices_to={'is_active': True},
        related_name='quick_sales_secondary',
        verbose_name="Secondary Account"
    )
    secondary_method = models.CharField(
        max_length=20,
        choices=[
            ('', '---------'),
            ('CASH', 'Cash'),
            ('TRANSFER', 'Bank Transfer'),
            ('POS', 'POS'),
        ],
        blank=True,
        verbose_name="Secondary Method"
    )
    secondary_reference = models.CharField(max_length=100, blank=True, help_text="Secondary payment reference")
    
    # Optional buyer info
    buyer_name = models.CharField(max_length=100, blank=True, help_text="Optional - buyer's name")
    buyer_phone = models.CharField(max_length=24, blank=True, help_text="Optional - buyer's phone")
    
    # Pickup
    pickup_authorized_by = models.CharField(max_length=100, blank=True)
    
    # Tracking
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quick_sales_recorded'
    )
    remark = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Quick Sale"
        verbose_name_plural = "Quick Sales"
    
    def __str__(self):
        return f"QS-{self.pk:05d} | {self.quantity} {self.block_type.name} | ₦{self.total_amount:,.0f}"
    
    @property
    def primary_amount(self):
        """Amount paid via primary method."""
        return self.total_amount - (self.secondary_amount or Decimal('0'))
    
    @property
    def is_split_payment(self):
        """Check if this is a split payment."""
        return self.secondary_amount > 0 and self.secondary_account is not None
    
    def clean(self):
        """Validate split payment fields."""
        from django.core.exceptions import ValidationError
        
        # Calculate expected total for validation
        if self.block_type_id and self.quantity:
            expected_total = self.quantity * (self.block_type.selling_price - (self.logistics_discount or Decimal('0')))
        else:
            expected_total = Decimal('0')
        
        # Validate secondary_amount is not negative
        if self.secondary_amount and self.secondary_amount < 0:
            raise ValidationError({'secondary_amount': 'Secondary amount cannot be negative'})
        
        # Validate secondary_amount is not >= total
        if self.secondary_amount and expected_total > 0:
            if self.secondary_amount >= expected_total:
                raise ValidationError({'secondary_amount': 'Secondary amount must be less than total amount'})
        
        # Validate secondary payment fields are complete
        if self.secondary_amount and self.secondary_amount > 0:
            if not self.secondary_account:
                raise ValidationError({'secondary_account': 'Secondary account required when secondary amount > 0'})
            if not self.secondary_method:
                raise ValidationError({'secondary_method': 'Secondary method required when secondary amount > 0'})
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        # Auto-fill unit price from block type
        self.unit_price = self.block_type.selling_price
        
        # Calculate total (with discount per block)
        self.total_amount = self.quantity * (self.unit_price - (self.logistics_discount or Decimal('0')))
        
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Deduct stock
            self.block_type.current_stock -= self.quantity
            self.block_type.save(update_fields=['current_stock'])
            
            # Credit primary payment account
            primary_amt = self.primary_amount
            self.payment_account.current_balance += primary_amt
            self.payment_account.save(update_fields=['current_balance'])
            
            # Credit secondary payment account (if split payment)
            if self.is_split_payment:
                self.secondary_account.current_balance += self.secondary_amount
                self.secondary_account.save(update_fields=['current_balance'])
    
    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Restore stock
        self.block_type.current_stock += self.quantity
        self.block_type.save(update_fields=['current_stock'])
        
        # Debit primary payment account
        primary_amt = self.primary_amount
        self.payment_account.current_balance -= primary_amt
        self.payment_account.save(update_fields=['current_balance'])
        
        # Debit secondary payment account (if split payment)
        if self.is_split_payment:
            self.secondary_account.current_balance -= self.secondary_amount
            self.secondary_account.save(update_fields=['current_balance'])
        
        super().delete(*args, **kwargs)
# ==============================================================================
# 9. Loans & Debtors
# ==============================================================================

class Debtor(models.Model):
    """People who can receive loans - can be employees or external persons."""
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    employee = models.OneToOneField(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='debtor_profile',
        help_text="Link to employee if this is a staff member"
    )
    address = models.TextField(blank=True)
    id_number = models.CharField(max_length=50, blank=True, help_text="NIN, Voter's Card, etc.")
    
    # Balance tracking (positive = they owe us)
    loan_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Debtor"
        verbose_name_plural = "Debtors"

    def __str__(self):
        if self.employee:
            return f"{self.name} (Staff)"
        return self.name

    @property
    def balance_status(self):
        if self.loan_balance > 0:
            return "Owes"
        elif self.loan_balance < 0:
            return "Overpaid"
        return "Settled"


class Loan(models.Model):
    """Records loans given to debtors."""
    REPAYMENT_MODE_CHOICES = [
        ('WEEKLY', 'Weekly Deduction'),
        ('MONTHLY', 'Monthly/Salary Deduction'),
        ('LUMP_SUM', 'Lump Sum'),
        ('FLEXIBLE', 'Flexible/As Available'),
    ]
    
    date = models.DateField(default=timezone.now)
    debtor = models.ForeignKey(Debtor, on_delete=models.PROTECT, related_name='loans')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT)
    
    purpose = models.CharField(max_length=200, blank=True)
    repayment_mode = models.CharField(max_length=20, choices=REPAYMENT_MODE_CHOICES, default='FLEXIBLE')
    expected_repayment_date = models.DateField(null=True, blank=True)
    
    # Tracking
    amount_repaid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False)
    is_fully_repaid = models.BooleanField(default=False, editable=False)
    
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Loan"
        verbose_name_plural = "Loans"

    def __str__(self):
        return f"LOAN-{self.pk:05d} | {self.debtor.name} | ₦{self.amount:,.2f}"

    @property
    def outstanding_balance(self):
        return self.amount - self.amount_repaid

    @property
    def repayment_progress(self):
        if self.amount == 0:
            return 100
        return int((self.amount_repaid / self.amount) * 100)

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'Loan amount must be greater than zero.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        
        if is_edit:
            old = Loan.objects.select_for_update().get(pk=self.pk)
            # Reverse old: Add back to payment account, subtract from debtor balance
            PaymentAccount.objects.filter(pk=old.payment_account.pk).update(
                current_balance=F('current_balance') + old.amount
            )
            Debtor.objects.filter(pk=old.debtor.pk).update(
                loan_balance=F('loan_balance') - old.amount
            )

        super().save(*args, **kwargs)

        # Apply new: Deduct from payment account, add to debtor balance
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') - self.amount
        )
        Debtor.objects.filter(pk=self.debtor.pk).update(
            loan_balance=F('loan_balance') + self.amount
        )

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Reverse: Add back to payment account, subtract from debtor balance
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') + self.amount
        )
        Debtor.objects.filter(pk=self.debtor.pk).update(
            loan_balance=F('loan_balance') - self.amount
        )
        super().delete(*args, **kwargs)

    def update_repayment_status(self):
        """Called by LoanRepayment to update totals."""
        total_repaid = self.repayments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        self.amount_repaid = total_repaid
        self.is_fully_repaid = (total_repaid >= self.amount)
        self.save(update_fields=['amount_repaid', 'is_fully_repaid', 'updated_at'])


class LoanRepayment(models.Model):
    """Records repayments made against loans."""
    date = models.DateField(default=timezone.now)
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name='repayments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT)
    
    repayment_method = models.CharField(max_length=20, choices=[
        ('CASH', 'Cash'),
        ('TRANSFER', 'Bank Transfer'),
        ('SALARY_DEDUCTION', 'Salary Deduction'),
        ('OTHER', 'Other'),
    ], default='CASH')
    
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Loan Repayment"
        verbose_name_plural = "Loan Repayments"

    def __str__(self):
        return f"Repayment: ₦{self.amount:,.2f} for {self.loan.debtor.name}"

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'Repayment amount must be greater than zero.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_edit = self.pk is not None
        
        if is_edit:
            old = LoanRepayment.objects.select_for_update().get(pk=self.pk)
            # Reverse old
            PaymentAccount.objects.filter(pk=old.payment_account.pk).update(
                current_balance=F('current_balance') - old.amount
            )
            Debtor.objects.filter(pk=old.loan.debtor.pk).update(
                loan_balance=F('loan_balance') + old.amount
            )

        super().save(*args, **kwargs)

        # Apply new
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') + self.amount
        )
        Debtor.objects.filter(pk=self.loan.debtor.pk).update(
            loan_balance=F('loan_balance') - self.amount
        )
        
        # Update loan repayment status
        self.loan.update_repayment_status()

    @transaction.atomic
    def delete(self, *args, **kwargs):
        loan = self.loan
        # Reverse
        PaymentAccount.objects.filter(pk=self.payment_account.pk).update(
            current_balance=F('current_balance') - self.amount
        )
        Debtor.objects.filter(pk=loan.debtor.pk).update(
            loan_balance=F('loan_balance') + self.amount
        )
        super().delete(*args, **kwargs)
        # Update loan status after delete
        loan.update_repayment_status()



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
auditlog.register(MaintenanceLog)
auditlog.register(TransportAsset)
auditlog.register(TransportRevenue)
auditlog.register(BankCharge)
auditlog.register(AccountTransfer)
auditlog.register(DailyCashClose)
auditlog.register(VendorPayment)
auditlog.register(TeamPayment)
auditlog.register(SandVehicleType)
auditlog.register(SandSale)
auditlog.register(Debtor)
auditlog.register(Loan)
auditlog.register(LoanRepayment)
auditlog.register(QuickSale)