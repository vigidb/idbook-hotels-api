from django.db import models

# Create your models here.


class Stylist(models.Model):
    shop = models.ForeignKey(ShopDetail, on_delete=models.CASCADE, related_name='stylist')
    mobile_number = models.CharField(max_length=10, db_index=True, unique=True,
                              validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                         message='Enter a valid phone number')],
                              default='9999999999'
                              )
    first_name = models.CharField(max_length=30, null=True, blank=True)
    last_name = models.CharField(max_length=30, null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='Other')
    date_of_birth = models.DateField(auto_now=False, auto_now_add=False, validators=[MinAgeValidator(18)], blank=True,
                                     null=True)
    profile_picture = models.CharField(max_length=255, blank=True, null=True)
    education = models.CharField(max_length=25, choices=EDUCATION_CHOICES, default='Others')
    experience = models.CharField(max_length=25)
    review = models.FloatField(default=0)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.first_name)

    class Meta:
        verbose_name_plural = 'Stylists'

