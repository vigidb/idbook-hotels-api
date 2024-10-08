# Generated by Django 4.2.3 on 2023-08-12 08:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0006_remove_bankdetail_google_pay_number_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companydetail',
            name='state',
            field=models.CharField(choices=[('Andhra Pradesh', 'Andhra Pradesh'), ('Arunachal Pradesh', 'Arunachal Pradesh'), ('Assam', 'Assam'), ('Bihar', 'Bihar'), ('Chandigarh (UT)', 'Chandigarh (UT)'), ('Chhattisgarh', 'Chhattisgarh'), ('Dadra and Nagar Haveli (UT)', 'Dadra and Nagar Haveli (UT)'), ('Daman and Diu (UT)', 'Daman and Diu (UT)'), ('Delhi (NCT)', 'Delhi (NCT)'), ('Goa', 'Goa'), ('Gujarat', 'Gujarat'), ('Haryana', 'Haryana'), ('Himachal Pradesh', 'Himachal Pradesh'), ('Jammu and Kashmir', 'Jammu and Kashmir'), ('Jharkhand', 'Jharkhand'), ('Karnataka', 'Karnataka'), ('Kerala', 'Kerala'), ('Lakshadweep (UT)', 'Lakshadweep (UT)'), ('Madhya Pradesh', 'Madhya Pradesh'), ('Maharashtra', 'Maharashtra'), ('Manipur', 'Manipur'), ('Meghalaya', 'Meghalaya'), ('Mizoram', 'Mizoram'), ('Nagaland', 'Nagaland'), ('Odisha', 'Odisha'), ('Puducherry (UT)', 'Puducherry (UT)'), ('Punjab', 'Punjab'), ('Rajasthan', 'Rajasthan'), ('Sikkim', 'Sikkim'), ('Tamil Nadu', 'Tamil Nadu'), ('Telangana', 'Telangana'), ('Tripura', 'Tripura'), ('Uttarakhand', 'Uttarakhand'), ('Uttar Pradesh', 'Uttar Pradesh'), ('West Bengal', 'West Bengal')], default='', max_length=30),
        ),
    ]
