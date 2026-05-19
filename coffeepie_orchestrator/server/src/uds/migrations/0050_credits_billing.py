# Generated migration for Coffee Pie credit/billing models

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('uds', '0049_datetime_to_utc'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreditPackage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('name', models.CharField(max_length=64, unique=True)),
                ('package_type', models.CharField(choices=[('FREE', 'Free Tier'), ('SMALL', 'Small Package'), ('MEDIUM', 'Medium Package'), ('LARGE', 'Large Package')], max_length=16, unique=True)),
                ('credits', models.PositiveBigIntegerField()),
                ('price_cop', models.PositiveIntegerField()),
                ('validity_days', models.PositiveIntegerField()),
                ('has_no_ads', models.BooleanField(default=False)),
                ('has_mirror', models.BooleanField(default=False)),
                ('has_snapshots', models.BooleanField(default=False)),
                ('has_ha', models.BooleanField(default=False)),
                ('has_live_migration', models.BooleanField(default=False)),
                ('has_non_certified_access', models.BooleanField(default=False)),
                ('has_account_executive', models.BooleanField(default=False)),
                ('support_level', models.CharField(default='basic', max_length=64)),
                ('is_active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'uds_credit_packages',
                'ordering': ('credits',),
            },
        ),
        migrations.CreateModel(
            name='CreditAccount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('balance', models.BigIntegerField(default=0)),
                ('lifetime_purchased', models.BigIntegerField(default=0)),
                ('lifetime_consumed', models.BigIntegerField(default=0)),
                ('lifetime_ad_rewards', models.BigIntegerField(default=0)),
                ('last_activity', models.DateTimeField(auto_now_add=True)),
                ('is_advertiser', models.BooleanField(default=False)),
                ('advertiser_name', models.CharField(blank=True, default='', max_length=128)),
                ('advertiser_segments', models.JSONField(blank=True, default=list)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('credited_until', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=models.CASCADE, related_name='credit_account', to='uds.User')),
            ],
            options={
                'db_table': 'uds_credit_accounts',
            },
        ),
        migrations.CreateModel(
            name='CreditTransaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('txn_type', models.CharField(choices=[('PURCHASE', 'Credit Purchase'), ('CONSUMPTION', 'Slice Usage Consumption'), ('AD_BID', 'Advertiser Bid Placed'), ('AD_REWARD', 'Ad Reward to User'), ('REFUND', 'Refund'), ('BONUS', 'Promotional Bonus'), ('TRANSFER', 'Manual Transfer'), ('EXPIRATION', 'Credit Expiration')], max_length=16)),
                ('amount', models.BigIntegerField()),
                ('balance_after', models.BigIntegerField()),
                ('description', models.CharField(blank=True, default='', max_length=256)),
                ('reference_id', models.CharField(blank=True, default='', max_length=128)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('account', models.ForeignKey(on_delete=models.CASCADE, related_name='transactions', to='uds.CreditAccount')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='credit_transactions', to='uds.User')),
            ],
            options={
                'db_table': 'uds_credit_transactions',
                'ordering': ('-timestamp',),
            },
        ),
        migrations.CreateModel(
            name='AdvertiserBid',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('bid_amount', models.PositiveIntegerField()),
                ('total_budget', models.PositiveBigIntegerField()),
                ('remaining_budget', models.PositiveBigIntegerField()),
                ('segments', models.JSONField(default=dict)),
                ('ad_url', models.URLField(max_length=512)),
                ('is_active', models.BooleanField(default=True)),
                ('starts_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('advertiser', models.ForeignKey(on_delete=models.CASCADE, related_name='ad_bids', to='uds.User')),
            ],
            options={
                'db_table': 'uds_ad_bids',
                'ordering': ('-bid_amount',),
            },
        ),
    ]
