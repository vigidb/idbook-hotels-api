# Generated by Django 4.2.3 on 2023-08-12 05:19

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('authentication', '0002_alter_user_email_alter_user_first_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='name',
            field=models.CharField(help_text='Name of the role.', max_length=50, unique=True),
        ),
        migrations.AlterField(
            model_name='role',
            name='permissions',
            field=models.ManyToManyField(help_text='Select permissions associated with this role.', to='auth.permission'),
        ),
        migrations.AlterField(
            model_name='role',
            name='short_code',
            field=models.CharField(db_index=True, default='', help_text='Short code representing the role.', max_length=3, unique=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='category',
            field=models.CharField(blank=True, help_text='Category of the user.', max_length=20),
        ),
        migrations.AlterField(
            model_name='user',
            name='created',
            field=models.DateTimeField(auto_now_add=True, help_text='Date and time when the user account was created.'),
        ),
        migrations.AlterField(
            model_name='user',
            name='custom_id',
            field=models.CharField(blank=True, db_index=True, help_text='Custom ID for the user.', max_length=15),
        ),
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(blank=True, db_index=True, help_text='Email address of the user.', max_length=254, null=True, validators=[django.core.validators.EmailValidator]),
        ),
        migrations.AlterField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=False, help_text="Whether the user's email address is verified."),
        ),
        migrations.AlterField(
            model_name='user',
            name='first_name',
            field=models.CharField(blank=True, help_text='First name of the user.', max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Whether the user account is active.'),
        ),
        migrations.AlterField(
            model_name='user',
            name='is_staff',
            field=models.BooleanField(default=False, help_text='Whether the user has staff privileges.'),
        ),
        migrations.AlterField(
            model_name='user',
            name='last_name',
            field=models.CharField(blank=True, help_text='Last name of the user.', max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='mobile_number',
            field=models.CharField(db_index=True, help_text='Mobile number of the user (10 digits only).', max_length=10, unique=True, validators=[django.core.validators.RegexValidator(message='Enter a valid phone number', regex='^\\+?1?\\d{9,15}$')]),
        ),
        migrations.AlterField(
            model_name='user',
            name='mobile_verified',
            field=models.BooleanField(default=False, help_text="Whether the user's mobile number is verified."),
        ),
        migrations.AlterField(
            model_name='user',
            name='referral',
            field=models.CharField(blank=True, help_text='Referral code associated with the user.', max_length=120),
        ),
        migrations.AlterField(
            model_name='user',
            name='roles',
            field=models.ManyToManyField(help_text='Select roles associated with this user.', related_name='user_role', to='authentication.role'),
        ),
        migrations.AlterField(
            model_name='user',
            name='updated',
            field=models.DateTimeField(auto_now=True, help_text='Date and time when the user account was last updated.'),
        ),
    ]
