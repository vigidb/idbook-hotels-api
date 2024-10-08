# Generated by Django 4.2.3 on 2023-08-17 10:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0007_alter_companydetail_state'),
    ]

    operations = [
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_address', models.CharField(help_text='Full address', max_length=100)),
                ('district', models.CharField(help_text='District', max_length=50)),
                ('state', models.CharField(choices=[('Andhra Pradesh', 'Andhra Pradesh'), ('Arunachal Pradesh', 'Arunachal Pradesh'), ('Assam', 'Assam'), ('Bihar', 'Bihar'), ('Chandigarh (UT)', 'Chandigarh (UT)'), ('Chhattisgarh', 'Chhattisgarh'), ('Dadra and Nagar Haveli (UT)', 'Dadra and Nagar Haveli (UT)'), ('Daman and Diu (UT)', 'Daman and Diu (UT)'), ('Delhi (NCT)', 'Delhi (NCT)'), ('Goa', 'Goa'), ('Gujarat', 'Gujarat'), ('Haryana', 'Haryana'), ('Himachal Pradesh', 'Himachal Pradesh'), ('Jammu and Kashmir', 'Jammu and Kashmir'), ('Jharkhand', 'Jharkhand'), ('Karnataka', 'Karnataka'), ('Kerala', 'Kerala'), ('Lakshadweep (UT)', 'Lakshadweep (UT)'), ('Madhya Pradesh', 'Madhya Pradesh'), ('Maharashtra', 'Maharashtra'), ('Manipur', 'Manipur'), ('Meghalaya', 'Meghalaya'), ('Mizoram', 'Mizoram'), ('Nagaland', 'Nagaland'), ('Odisha', 'Odisha'), ('Puducherry (UT)', 'Puducherry (UT)'), ('Punjab', 'Punjab'), ('Rajasthan', 'Rajasthan'), ('Sikkim', 'Sikkim'), ('Tamil Nadu', 'Tamil Nadu'), ('Telangana', 'Telangana'), ('Tripura', 'Tripura'), ('Uttarakhand', 'Uttarakhand'), ('Uttar Pradesh', 'Uttar Pradesh'), ('West Bengal', 'West Bengal')], default='', help_text='State', max_length=50)),
                ('country', models.CharField(choices=[('INDIA', 'INDIA'), ('NEPAL', 'NEPAL'), ('BHUTAN', 'BHUTAN'), ('CHINA', 'CHINA'), ('UAE', 'UAE'), ('MALDIVES', 'MALDIVES')], default='INDIA', help_text='Country', max_length=50)),
                ('pin_code', models.PositiveIntegerField(default=0, help_text='PIN code')),
            ],
        ),
    ]
