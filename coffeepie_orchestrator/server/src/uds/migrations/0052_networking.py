# Generated migration for Coffee Pie NAT traversal & networking models

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('uds', '0051_seed_credit_packages'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertifiedDevice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('mac_address', models.CharField(db_index=True, max_length=17, unique=True)),
                ('serial_number', models.CharField(db_index=True, max_length=128, unique=True)),
                ('model_name', models.CharField(max_length=64)),
                ('manufacturer', models.CharField(max_length=128)),
                ('firmware_version', models.CharField(blank=True, default='', max_length=32)),
                ('public_key', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('is_verified', models.BooleanField(default=False)),
                ('network_tier', models.CharField(choices=[('L2', 'Layer 2 - Private LAN (Certified)'), ('L3', 'Layer 3 - Internet via Relay'), ('L4', 'Layer 4 - WebRTC Fallback')], default='L2', max_length=2)),
                ('last_seen', models.DateTimeField(auto_now_add=True)),
                ('last_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('geo_region', models.CharField(blank=True, default='', max_length=8)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='owned_devices', to='uds.User')),
            ],
            options={
                'db_table': 'uds_certified_devices',
                'ordering': ('-registered_at',),
            },
        ),
        migrations.CreateModel(
            name='TurnServer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('region', models.CharField(db_index=True, max_length=8)),
                ('hostname', models.CharField(max_length=256)),
                ('port', models.PositiveIntegerField(default=3478)),
                ('tls_port', models.PositiveIntegerField(default=5349)),
                ('username_prefix', models.CharField(max_length=32)),
                ('shared_secret', models.CharField(max_length=128)),
                ('is_active', models.BooleanField(default=True)),
                ('priority', models.PositiveSmallIntegerField(default=0)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'uds_turn_servers',
                'ordering': ('-priority',),
            },
        ),
        migrations.CreateModel(
            name='OrchestratorRegion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('region', models.CharField(db_index=True, max_length=8, unique=True)),
                ('name', models.CharField(max_length=64)),
                ('orchestrator_url', models.URLField(max_length=512)),
                ('is_active', models.BooleanField(default=True)),
                ('is_primary', models.BooleanField(default=False)),
                ('priority', models.PositiveSmallIntegerField(default=0)),
                ('latitude', models.FloatField(blank=True, null=True)),
                ('longitude', models.FloatField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'uds_orchestrator_regions',
                'ordering': ('-priority', '-is_primary'),
            },
        ),
        migrations.CreateModel(
            name='NatSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('local_ip', models.GenericIPAddressField()),
                ('public_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('local_port', models.PositiveIntegerField()),
                ('public_port', models.PositiveIntegerField(blank=True, null=True)),
                ('turn_username', models.CharField(blank=True, default='', max_length=128)),
                ('turn_password', models.CharField(blank=True, default='', max_length=128)),
                ('network_tier', models.CharField(choices=[('L2', 'Layer 2 - Private LAN (Certified)'), ('L3', 'Layer 3 - Internet via Relay'), ('L4', 'Layer 4 - WebRTC Fallback')], max_length=2)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to='uds.CertifiedDevice')),
                ('turn_server', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to='uds.TurnServer')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='nat_sessions', to='uds.User')),
            ],
            options={
                'db_table': 'uds_nat_sessions',
            },
        ),
    ]
