# Generated migration for Coffee Pie Ads API models

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('uds', '0052_networking'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdvertiserApiKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('api_key', models.CharField(db_index=True, max_length=64, unique=True)),
                ('name', models.CharField(blank=True, default='', max_length=128)),
                ('is_active', models.BooleanField(default=True)),
                ('allowed_origins', models.JSONField(blank=True, default=list)),
                ('rate_limit_per_minute', models.PositiveIntegerField(default=60)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('last_used', models.DateTimeField(blank=True, null=True)),
                ('advertiser', models.ForeignKey(on_delete=models.CASCADE, related_name='ad_api_keys', to='uds.User')),
            ],
            options={
                'db_table': 'uds_ad_api_keys',
            },
        ),
        migrations.CreateModel(
            name='AdCampaign',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('campaign_name', models.CharField(max_length=256)),
                ('bid_amount', models.PositiveIntegerField()),
                ('daily_budget', models.PositiveBigIntegerField()),
                ('total_budget', models.PositiveBigIntegerField()),
                ('remaining_budget', models.PositiveBigIntegerField()),
                ('ad_content', models.JSONField(default=dict)),
                ('targeting', models.JSONField(default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('impressions', models.PositiveBigIntegerField(default=0)),
                ('clicks', models.PositiveBigIntegerField(default=0)),
                ('spent', models.PositiveBigIntegerField(default=0)),
                ('starts_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('advertiser', models.ForeignKey(on_delete=models.CASCADE, related_name='ad_campaigns', to='uds.User')),
            ],
            options={
                'db_table': 'uds_ad_campaigns',
                'ordering': ('-bid_amount',),
            },
        ),
    ]
