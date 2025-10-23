# 🚀 Flight Booking Integration Plan with Booking App

## 📋 **Current State Analysis**

### **Existing Booking App Models:**
1. **`Booking`** (Main model) - Handles payments, GST, discounts, invoices
2. **`FlightBooking`** (Basic) - Simple flight details only  
3. **`Invoice`** - PDF generation, GST compliance
4. **`tasks.py`** - Email/SMS notifications, invoice generation

### **Flights App Models:**
1. **`FlightBooking`** (Advanced) - AirIQ integration, PNR, status management
2. **`PassengerDetail`** - Detailed passenger info 
3. **`AncillaryService`** - SSR services
4. **`FlightBookingPayment`** - Payment tracking
5. **`AirIQApiLog`** - API logging

## 🔄 **Integration Strategy**

### **Phase 1: Enhance Existing Booking App FlightBooking Model**
**Goal:** Extend booking app's FlightBooking model with flights app features

### **Phase 2: Create Flight-Specific Models in Booking App**  
**Goal:** Move passenger, ancillary, and AirIQ-specific models to booking app

### **Phase 3: Update Flights App to Use Booking App Models**
**Goal:** Modify flights viewsets to work with booking app models

### **Phase 4: Add Flight Payment & Notification Integration**
**Goal:** Connect to existing payment gateways and notification system

---

## 🛠 **Implementation Plan**

### **Step 1: Enhance FlightBooking Model in Booking App**

Create a migration to add AirIQ-specific fields to the existing `FlightBooking` model:

```python
# apps/booking/migrations/XXXX_enhance_flight_booking.py

class Migration(migrations.Migration):
    dependencies = [
        ('booking', '0025_last_migration'),  # Replace with actual last migration
    ]

    operations = [
        # Add AirIQ integration fields
        migrations.AddField(
            model_name='flightbooking',
            name='airiq_pnr',
            field=models.CharField(max_length=20, blank=True, help_text="AirIQ PNR"),
        ),
        migrations.AddField(
            model_name='flightbooking',
            name='airline_pnr', 
            field=models.CharField(max_length=20, blank=True, help_text="Airline PNR"),
        ),
        migrations.AddField(
            model_name='flightbooking',
            name='airiq_track_id',
            field=models.CharField(max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='flightbooking',
            name='booking_reference',
            field=models.CharField(max_length=20, blank=True, unique=True),
        ),
        migrations.AddField(
            model_name='flightbooking',
            name='status',
            field=models.CharField(max_length=20, default='INITIATED', choices=[
                ('INITIATED', 'Booking Initiated'),
                ('HELD', 'Booking Held'),
                ('CONFIRMED', 'Confirmed'),
                ('TICKETED', 'Ticketed'),
                ('CANCELLED', 'Cancelled'),
                ('COMPLETED', 'Completed'),
            ]),
        ),
        # Add search session reference
        migrations.AddField(
            model_name='flightbooking',
            name='search_session_data',
            field=models.JSONField(default=dict, help_text="Flight search session data"),
        ),
        # Add selected flight details  
        migrations.AddField(
            model_name='flightbooking',
            name='selected_flight_data',
            field=models.JSONField(default=dict, help_text="Selected flight option data"),
        ),
        # Add ticket details
        migrations.AddField(
            model_name='flightbooking',
            name='ticket_numbers',
            field=models.JSONField(default=list, help_text="Ticket numbers for passengers"),
        ),
    ]
```

### **Step 2: Create Flight-Specific Models in Booking App**

```python
# apps/booking/models.py - Add these models

class FlightPassenger(models.Model):
    """Passenger details for flight bookings"""
    flight_booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE, related_name='passengers')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='flight_passengers')
    
    # Passenger identification
    passenger_reference = models.PositiveSmallIntegerField()
    passenger_type = models.CharField(max_length=3, choices=PASSENGER_TYPE)
    
    # Personal details
    title = models.CharField(max_length=5, choices=PASSENGER_TITLE)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    
    # Travel documents
    passport_number = models.CharField(max_length=20, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    
    # Ticket details
    ticket_number = models.CharField(max_length=20, blank=True)
    seat_number = models.CharField(max_length=5, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'booking_flight_passenger'
        unique_together = ['flight_booking', 'passenger_reference']

class FlightAncillaryService(models.Model):
    """Ancillary services for flight bookings"""
    flight_booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE, related_name='ancillary_services')
    passenger = models.ForeignKey(FlightPassenger, on_delete=models.CASCADE, related_name='services')
    
    service_type = models.CharField(max_length=20, choices=SSR_CATEGORY)
    service_code = models.CharField(max_length=20)
    service_description = models.CharField(max_length=200)
    service_price = models.DecimalField(max_digits=8, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'booking_flight_ancillary'
```

### **Step 3: Create Migration Script for Data Transfer**

```python
# apps/booking/management/commands/migrate_flight_bookings.py

from django.core.management.base import BaseCommand
from apps.flights.models import FlightBooking as OldFlightBooking
from apps.booking.models import Booking, FlightBooking as NewFlightBooking

class Command(BaseCommand):
    help = 'Migrate flight bookings from flights app to booking app'
    
    def handle(self, *args, **options):
        # This will be a safe migration script
        old_bookings = OldFlightBooking.objects.all()
        
        for old_booking in old_bookings:
            try:
                # Create main Booking record
                booking = Booking.objects.create(
                    user=old_booking.user,
                    booking_type='FLIGHT',
                    subtotal=old_booking.base_amount,
                    service_tax=old_booking.tax_amount,
                    final_amount=old_booking.total_amount,
                    status=self.map_status(old_booking.status),
                    created=old_booking.created_at,
                    updated=old_booking.updated_at,
                )
                
                # Create enhanced FlightBooking
                flight_booking = NewFlightBooking.objects.create(
                    flight_no=old_booking.selected_flight.flight_number,
                    departure_date=old_booking.selected_flight.departure_datetime,
                    arrival_date=old_booking.selected_flight.arrival_datetime,
                    flying_from=old_booking.selected_flight.origin,
                    flying_to=old_booking.selected_flight.destination,
                    airiq_pnr=old_booking.airiq_pnr,
                    airline_pnr=old_booking.airline_pnr,
                    booking_reference=old_booking.booking_reference,
                    status=old_booking.status,
                )
                
                # Link to main booking
                booking.flight_booking = flight_booking
                booking.save()
                
                # Migrate passengers
                for passenger in old_booking.passengers.all():
                    FlightPassenger.objects.create(
                        flight_booking=flight_booking,
                        booking=booking,
                        passenger_reference=passenger.passenger_reference,
                        title=passenger.title,
                        first_name=passenger.first_name,
                        last_name=passenger.last_name,
                        date_of_birth=passenger.date_of_birth,
                        gender=passenger.gender,
                        # ... other fields
                    )
                
                self.stdout.write(f"Migrated booking {old_booking.id}")
                
            except Exception as e:
                self.stdout.write(f"Error migrating booking {old_booking.id}: {e}")
```

### **Step 4: Update Flights ViewSets to Use Booking App**

```python
# apps/flights/viewsets.py - Updated FlightBookingViewSet

from apps.booking.models import Booking, FlightBooking, FlightPassenger
from apps.booking.tasks import create_invoice_task, send_booking_email_task

class FlightBookingViewSet(viewsets.ModelViewSet):
    def create(self, request):
        """Create flight booking using booking app models"""
        try:
            with transaction.atomic():
                # Create main Booking record
                booking = Booking.objects.create(
                    user=request.user,
                    booking_type='FLIGHT',
                    adult_count=booking_data.get('adults', 1),
                    child_count=booking_data.get('children', 0),
                    infant_count=booking_data.get('infants', 0),
                    subtotal=pricing_data['base_amount'],
                    service_tax=pricing_data['tax_amount'], 
                    final_amount=pricing_data['total_amount'],
                    status='pending'
                )
                
                # Create FlightBooking record
                flight_booking = FlightBooking.objects.create(
                    flight_no=flight_option.flight_number,
                    departure_date=flight_option.departure_datetime,
                    arrival_date=flight_option.arrival_datetime,
                    flying_from=flight_option.origin,
                    flying_to=flight_option.destination,
                    booking_reference=self.generate_booking_reference(),
                    selected_flight_data=flight_option_data,
                    status='INITIATED'
                )
                
                # Link them
                booking.flight_booking = flight_booking
                booking.save()
                
                # Create passengers
                for passenger_data in passengers:
                    FlightPassenger.objects.create(
                        flight_booking=flight_booking,
                        booking=booking,
                        # ... passenger fields
                    )
                
                # If payment provided, process it
                if payment_data:
                    return self.process_payment(booking, payment_data)
                else:
                    # Send booking email
                    send_booking_email_task.delay(booking.id, 'search-booking')
                    return self.get_response(data=booking_data, message="Booking created")
        
        except Exception as e:
            return self.get_error_response(message=f"Booking failed: {e}")
    
    @action(detail=True, methods=['post'], url_path='payment')
    def process_payment(self, request, pk=None):
        """Process payment using existing payment gateway"""
        booking = self.get_object()  # This will be a Booking object now
        
        # Use existing payment processing from booking app
        # Similar to hotel booking payment flow
        
        payment_data = request.data
        payment_gateway = payment_data.get('payment_gateway', 'PHONEPAY')
        
        if payment_gateway == 'PHONEPAY':
            # Use existing PhonePe integration
            return self._process_phonepay_payment(booking, payment_data)
        elif payment_gateway == 'PAYU':
            # Use existing PayU integration  
            return self._process_payu_payment(booking, payment_data)
        
    def _process_phonepay_payment(self, booking, payment_data):
        """Process PhonePe payment for flight booking"""
        # Reuse existing PhonePe integration from booking app
        # This will integrate with existing payment infrastructure
        pass
```

### **Step 5: Add Flight-Specific Tasks**

```python
# apps/booking/tasks.py - Add flight-specific tasks

@celery_idbook.task(bind=True)
def create_flight_booking_with_airiq(self, booking_id, flight_option_data, passengers_data):
    """Create AirIQ booking after payment confirmation"""
    booking = get_booking(booking_id)
    flight_booking = booking.flight_booking
    
    try:
        # Prepare AirIQ booking data
        airiq_booking_data = prepare_airiq_booking_data(
            flight_booking, passengers_data, booking
        )
        
        # Call AirIQ booking API
        from apps.flights.services.airiq_service import airiq_service
        response = airiq_service.create_booking(
            airiq_booking_data, 
            flight_booking.airiq_track_id
        )
        
        if response.get('Status', {}).get('ResultCode') == '1':
            # Update booking with AirIQ details
            flight_booking.airiq_pnr = response.get('AirIqPNR')
            flight_booking.airline_pnr = response.get('AirlinePNR')
            flight_booking.status = 'CONFIRMED'
            flight_booking.save()
            
            booking.status = 'confirmed'
            booking.save()
            
            # Generate invoice
            create_invoice_task.delay(booking.id)
            
            # Send confirmation email
            send_booking_email_task.delay(booking.id, 'confirmed-booking')
            
        else:
            # Handle booking failure
            booking.status = 'failed'
            booking.save()
            
    except Exception as e:
        booking.status = 'failed' 
        booking.save()
        raise e

@celery_idbook.task(bind=True)
def issue_flight_ticket(self, booking_id):
    """Issue flight ticket via AirIQ after payment confirmation"""
    booking = get_booking(booking_id)
    flight_booking = booking.flight_booking
    
    try:
        from apps.flights.services.airiq_service import airiq_service
        
        ticket_response = airiq_service.issue_ticket(
            booking_track_id=flight_booking.airiq_track_id,
            airiq_pnr=flight_booking.airiq_pnr,
            airline_pnr=flight_booking.airline_pnr,
            booking_amount=float(booking.final_amount)
        )
        
        if ticket_response.get('Status', {}).get('ResultCode') == '1':
            # Update ticket details
            tickets = ticket_response.get('TicketDetails', [])
            ticket_numbers = [ticket.get('TicketNumber') for ticket in tickets]
            
            flight_booking.ticket_numbers = ticket_numbers
            flight_booking.status = 'TICKETED'
            flight_booking.save()
            
            booking.status = 'completed'
            booking.save()
            
            # Send ticket email with attachment
            send_booking_email_task.delay(booking.id, 'confirmed-booking')
            
    except Exception as e:
        print(f"Ticket issuance failed: {e}")
```

### **Step 6: Update Flight Email Templates**

```html
<!-- templates/email_template/booking-confirmation-flight.html -->
<!-- Enhance existing template with new fields -->

<div class="flight-details">
    <h3>Flight Details</h3>
    <p><strong>Flight:</strong> {{ booking.flight_booking.airline_code }} {{ booking.flight_booking.flight_no }}</p>
    <p><strong>Route:</strong> {{ booking.flight_booking.flying_from }} → {{ booking.flight_booking.flying_to }}</p>
    <p><strong>Departure:</strong> {{ booking.flight_booking.departure_date|date:"d M Y, H:i" }}</p>
    <p><strong>Arrival:</strong> {{ booking.flight_booking.arrival_date|date:"d M Y, H:i" }}</p>
    <p><strong>PNR:</strong> {{ booking.flight_booking.airiq_pnr }}</p>
    
    {% if booking.flight_booking.ticket_numbers %}
        <h4>Ticket Numbers:</h4>
        <ul>
        {% for ticket in booking.flight_booking.ticket_numbers %}
            <li>{{ ticket }}</li>
        {% endfor %}
        </ul>
    {% endif %}
</div>

<div class="passengers">
    <h3>Passengers</h3>
    {% for passenger in booking.flight_passengers.all %}
        <p>{{ passenger.title }} {{ passenger.first_name }} {{ passenger.last_name }}</p>
    {% endfor %}
</div>
```

---

## 🎯 **Migration Execution Plan**

### **Phase 1: Preparation (Day 1)**
1. ✅ Create backup of existing data
2. ✅ Create enhanced FlightBooking migration
3. ✅ Create FlightPassenger and FlightAncillaryService models
4. ✅ Test migration on development environment

### **Phase 2: Data Migration (Day 2)**
1. ✅ Run data migration script
2. ✅ Validate data integrity
3. ✅ Update flights app viewsets to use booking models
4. ✅ Test basic booking creation

### **Phase 3: Payment Integration (Day 3-4)**
1. ✅ Implement payment processing endpoints  
2. ✅ Connect to existing PhonePe/PayU gateways
3. ✅ Add payment confirmation workflow
4. ✅ Test payment flow end-to-end

### **Phase 4: Notifications & Invoice (Day 5)**
1. ✅ Update flight email templates
2. ✅ Add flight invoice generation
3. ✅ Test notification system
4. ✅ Add SMS notifications

### **Phase 5: Testing & Cleanup (Day 6-7)**
1. ✅ Comprehensive testing
2. ✅ Performance testing  
3. ✅ Remove old flight booking models (after confirmation)
4. ✅ Update API documentation

## ✅ **Benefits of This Integration**

1. **✅ Unified Booking System** - All bookings use same models and workflows
2. **✅ Payment Integration** - Automatic integration with existing gateways
3. **✅ GST Compliance** - Built-in tax calculations and invoice generation
4. **✅ Notification System** - Email/SMS using existing templates  
5. **✅ Discount System** - Coupon and pro member discounts work automatically
6. **✅ Reporting** - Flight bookings appear in existing reports
7. **✅ No Breaking Changes** - Hotel booking functionality unaffected

## 🔒 **Safety Measures**

1. **Data Backup** - Full database backup before migration
2. **Gradual Migration** - Migrate in batches with validation
3. **Rollback Plan** - Keep old models until confirmed working
4. **Testing** - Comprehensive testing at each phase
5. **Monitoring** - Monitor for any issues post-deployment

This integration will give you a **production-ready flight booking system** that leverages all your existing booking infrastructure while maintaining the advanced AirIQ features you've already built!