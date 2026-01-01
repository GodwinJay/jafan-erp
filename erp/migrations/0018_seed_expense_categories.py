from django.db import migrations


def create_expense_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model('erp', 'ExpenseCategory')
    
    categories = [
        {'name': 'Fuel', 'description': 'Vehicle fuel and diesel'},
        {'name': 'Maintenance', 'description': 'Repairs and servicing'},
        {'name': 'Salaries', 'description': 'Staff wages and payments'},
        {'name': 'Utilities', 'description': 'Electricity, water, etc.'},
        {'name': 'Miscellaneous', 'description': 'Other expenses'},
    ]
    
    for cat in categories:
        ExpenseCategory.objects.get_or_create(
            name=cat['name'],
            defaults={'description': cat['description'], 'is_active': True}
        )


def reverse_expense_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model('erp', 'ExpenseCategory')
    ExpenseCategory.objects.filter(name__in=[
        'Raw Materials', 'Fuel', 'Maintenance', 'Salaries', 'Utilities', 'Miscellaneous'
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0017_expensecategory_expense_procurementlog_expense_entry'),
    ]

    operations = [
        migrations.RunPython(create_expense_categories, reverse_expense_categories),
    ]