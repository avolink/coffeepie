from django.db import migrations


def seed_default_packages(apps, schema_editor):
    CreditPackage = apps.get_model('uds', 'CreditPackage')
    packages = [
        {'name': 'Capa Gratuita', 'package_type': 'FREE', 'credits': 0, 'price_cop': 0, 'validity_days': 0},
        {'name': 'Paquete Pequeño', 'package_type': 'SMALL', 'credits': 10000, 'price_cop': 10000, 'validity_days': 7, 'has_no_ads': True},
        {'name': 'Paquete Mediano', 'package_type': 'MEDIUM', 'credits': 500000, 'price_cop': 50000, 'validity_days': 30, 'has_no_ads': True, 'has_mirror': True, 'has_snapshots': True},
        {'name': 'Paquete Grande', 'package_type': 'LARGE', 'credits': 6000000, 'price_cop': 300000, 'validity_days': 365, 'has_no_ads': True, 'has_mirror': True, 'has_snapshots': True, 'has_ha': True, 'has_live_migration': True, 'has_non_certified_access': True, 'has_account_executive': True},
    ]
    for pkg in packages:
        CreditPackage.objects.get_or_create(package_type=pkg['package_type'], defaults=pkg)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('uds', '0050_credits_billing'),
    ]

    operations = [
        migrations.RunPython(seed_default_packages, reverse_noop),
    ]
