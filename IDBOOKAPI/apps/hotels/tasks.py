from IDBOOKAPI.celery import app as celery_idbook
from .models import Property, MonthlyPayAtHotelEligibility
from apps.authentication.models import User
from apps.sms_gateway.mixins.fastwosms_mixins import send_template_sms
from django.template.loader import get_template
from django.conf import settings
from IDBOOKAPI.email_utils import send_booking_email
from IDBOOKAPI.utils import shorten_url
from apps.booking.models import Booking, Review
from .utils.db_utils import get_user_booking_data
from .utils.hotel_utils import (generate_service_agreement_pdf, send_agreement_email,
    generate_hotel_receipt_pdf, send_receipt_email_with_attachment)
from apps.org_resources.utils.notification_utils import create_hotelier_notification
from apps.booking.tasks import send_booking_sms_task
from datetime import datetime
import uuid

@celery_idbook.task(bind=True)
def send_hotel_sms_task(self, notification_type='', params=None):
    if params is None:
        params = {}
    
    print(f"Inside {notification_type} SMS task")

    try:
        def get_property_from_id(property_id):
            return Property.objects.filter(id=property_id).first()

        def get_booking_property(booking_id):
            booking = Booking.objects.filter(id=booking_id).first()
            return booking, booking.hotel_booking.confirmed_property if booking and booking.hotel_booking else None

        def send_sms(mobile, template, variables):
            print("variables_values", variables)
            response = send_template_sms(mobile, template, variables)
            print(f"SMS sent with template '{template}'. Response: {response}")
            return response

        def shorten_link(url):
            print("website_link", url)
            return shorten_url(url)

        # Template logic
        if notification_type == 'HOTEL_PROPERTY_ACTIVATION':
            property = get_property_from_id(params.get('property_id'))
            if property and property.phone_no:
                website_link = f"https://www.idbookhotels.com/hotelier/login?utm_source=sms&utm_medium=notification&utm_campaign=property_activation&ref={property.slug}"
                short_link = shorten_link(website_link)
                variables_values = f"Hotelier|{property.name}|{short_link}"
                send_sms(
                    property.phone_no,
                    "HOTEL_PROPERTY_ACTIVATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTEL_PROPERTY_DEACTIVATION':
            property = get_property_from_id(params.get('property_id'))
            if property and property.phone_no:
                variables_values = f"Hotelier|{property.name}|Invalid/incomplete listing"
                send_sms(
                    property.phone_no,
                    "HOTEL_PROPERTY_DEACTIVATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELIER_BOOKING_NOTIFICATION':
            booking, property = get_booking_property(params.get('booking_id'))
            if property and property.phone_no:
                variables_values = f"Hotelier|{property.name}|{booking.hotel_booking.confirmed_checkin_time}"
                send_sms(
                    property.phone_no,
                    "HOTELIER_BOOKING_NOTIFICATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELER_BOOKING_CANCEL_NOTIFICATION':
            booking, property = get_booking_property(params.get('booking_id'))
            if property and property.phone_no:
                variables_values = f"Hotelier|{property.name}|{booking.reference_code}"
                send_sms(
                    property.phone_no,
                    "HOTELER_BOOKING_CANCEL_NOTIFICATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELER_PAYMENT_NOTIFICATION':
            booking, property = get_booking_property(params.get('booking_id'))
            if property and property.phone_no:
                final_amount = float(booking.final_amount or 0)
                code = booking.confirmation_code or booking.reference_code
                variables_values = f"Hotelier|{final_amount}|{code}"
                send_sms(
                    property.phone_no,
                    "HOTELER_PAYMENT_NOTIFICATION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELIER_PROPERTY_REVIEW_NOTIFICATION':
            review = Review.objects.select_related('property').filter(id=params.get('review_id')).first()
            if review and review.property and review.property.phone_no:
                variables_values = f"Hotelier|{review.property.name}|{float(review.overall_rating)}"
                send_sms(
                    review.property.phone_no,
                    "HOTELIER_PROPERTY_REVIEW_NOTIFICATION",
                    variables_values
                )
                create_hotelier_notification(review.property, notification_type, variables_values)

        elif notification_type == 'HOTEL_PROPERTY_SUBMISSION':
            property = get_property_from_id(params.get('property_id'))
            if property and property.phone_no:
                variables_values = f"Hotelier|{property.name}"
                send_sms(
                    property.phone_no,
                    "HOTEL_PROPERTY_SUBMISSION",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

        elif notification_type == 'HOTELIER_PAH_FEATURE':
            property = get_property_from_id(params.get('property_id'))
            if property and property.phone_no:
                website_link = "https://www.idbookhotels.com/"
                short_link = shorten_link(website_link)
                variables_values = f"Hotelier|{property.name}|{short_link}"
                send_sms(
                    property.phone_no,
                    "HOTELIER_PAH_FEATURE",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)
        
        elif notification_type == 'HOTELIER_PAH_BOOKING_ALERT':
            booking, property = get_booking_property(params.get('booking_id'))
            if property and property.phone_no and booking:
                variables_values = f"Hotelier|{property.name}|{float(booking.final_amount)}"
                send_sms(
                    property.phone_no,
                    "HOTELIER_PAH_BOOKING_ALERT",
                    variables_values
                )
                create_hotelier_notification(property, notification_type, variables_values)

    except Exception as e:
        print(f'{notification_type} SMS Task Error: {e}')

    return None

@celery_idbook.task(bind=True)
def send_hotel_email_task(self, notification_type='', params=None):
    """
    Background task to send email notifications to hotels
    """
    if params is None:
        params = {}
    print(f"Inside {notification_type} Email task")
    
    try:
        if notification_type == 'HOTEL_PROPERTY_ACTIVATION':
            property_id = params.get('property_id')
            if not property_id:
                print("No property_id provided in params")
                return

            try:
                property = Property.objects.get(id=property_id)
                
                if property and property.email:
                    recipient_email = property.email
                    print("recipient_email", recipient_email)
                    
                    # user = None
                    # if property.managed_by_id:
                    #     try:
                    #         user = User.objects.get(id=property.managed_by_id)
                    #     except User.DoesNotExist:
                    #         pass
                    
                    # hotelier_name = user.name if user else "Hotelier"
                    hotelier_name = "Hotelier"
                    property_name = property.name
                    # login_link = f"{settings.FRONTEND_URL}/login"
                    login_link = f"https://www.idbookhotels.com/hotelier/login?utm_source=email&utm_medium=notification&utm_campaign=property_activation&ref={property.slug}"
                    print("login_link", login_link)
                    short_login_link = shorten_url(login_link)
                    print("short_login_link", short_login_link)
                    context = {
                        'hotelier_name': hotelier_name,
                        'property_name': property_name,
                        'login_link': short_login_link
                    }
                    
                    email_template = get_template('email_template/hotelier-active-property.html')
                    html_content = email_template.render(context)

                    subject = f"Your property {property_name} is now ACTIVE on Idbook"
                    send_booking_email(subject, property, [recipient_email], html_content)
                    
                    print(f"Email sent for property activation to {recipient_email}")
                    return True
                else:
                    print(f"Property not found or no email available for property_id: {property_id}")
            except Property.DoesNotExist:
                print(f"Property with id {property_id} not found")
                
    except Exception as e:
        print(f'{notification_type} Email Task Error: {e}')
        return None


@celery_idbook.task(bind=True)
def update_monthly_pay_at_hotel_eligibility_task(self, user_id, booking_date):
    """
    Update monthly pay at hotel eligibility based on confirmed bookings count
    """
    print("Inside update monthly pay at hotel eligibility task")
    try:
        data = get_user_booking_data(user_id, booking_date)

        existing_eligibility = MonthlyPayAtHotelEligibility.objects.filter(
            user_id=user_id,
            month=data['month_name']
        ).first()

        if existing_eligibility and existing_eligibility.updated_by == "Admin":

            remaining_limit = existing_eligibility.eligible_limit - data['spent_amount']
            
            monthly_eligibility, created = MonthlyPayAtHotelEligibility.objects.update_or_create(
                user_id=user_id,
                month=data['month_name'],
                defaults={
                    'total_booking_count': data['booking_count'],
                    'total_cancel_count': data['total_cancel_count'],
                    'spent_amount': data['spent_amount'],
                    'is_eligible': existing_eligibility.is_eligible and remaining_limit > 0,
                    'eligible_limit': existing_eligibility.eligible_limit,
                    'cancel_limit': existing_eligibility.cancel_limit,
                    'is_blacklisted': existing_eligibility.is_blacklisted,
                    'updated_by': existing_eligibility.updated_by
                }
            )
            
            data['remaining_limit'] = remaining_limit
            data['eligible_limit'] = existing_eligibility.eligible_limit
            data['is_eligible'] = existing_eligibility.is_eligible and remaining_limit > 0
            data['is_blacklisted'] = existing_eligibility.is_blacklisted
            
        else:
            monthly_eligibility, created = MonthlyPayAtHotelEligibility.objects.update_or_create(
                user_id=user_id,
                month=data['month_name'],
                defaults={
                    'total_booking_count': data['booking_count'],
                    'eligible_limit': data['eligible_limit'],
                    'is_eligible': data['is_eligible'],
                    'total_cancel_count': data['total_cancel_count'],
                    'cancel_limit': data['cancel_limit'],
                    'is_blacklisted': data['is_blacklisted'],
                    'spent_amount': data['spent_amount'],
                    'updated_by': "Automatic"
                }
            )

        print(f"Updated monthly pay at hotel eligibility for user {user_id}, month: {data['month_name']}")
        print(
            f"Booking count: {data['booking_count']}, Eligible limit: {data['eligible_limit']}, "
            f"Spent amount: {data['spent_amount']}, Remaining limit: {data['remaining_limit']}, "
            f"Cancel count: {data['total_cancel_count']}, Cancel limit: {data['cancel_limit']}, "
            f"Is eligible: {data['is_eligible']}, Is blacklisted: {data['is_blacklisted']}"
        )
        # Check if user is not eligible and send the ELIGIBILITY_LOSS_NOTIFICATION
        if not data['is_eligible']:
            send_booking_sms_task.apply_async(
                kwargs={
                    'notification_type': 'ELIGIBILITY_LOSS_NOTIFICATION',
                    'params': {
                        'user_id': user_id,
                    }
                }
            )

        return {
            'user_id': user_id,
            'month': data['month_name'],
            'booking_count': data['booking_count'],
            'eligible_limit': float(data['eligible_limit']),
            'spent_amount': float(data['spent_amount']),
            'remaining_limit': float(data['remaining_limit']),
            'is_eligible': data['is_eligible'],
            'is_blacklisted': data['is_blacklisted'],
            'updated_by': monthly_eligibility.updated_by
        }

    except Exception as e:
        print('Update Monthly Pay At Hotel Eligibility Task Error:', e)
        print(traceback.format_exc())
        return {
            'status': 'error',
            'message': str(e)
        }

@celery_idbook.task(bind=True)
def create_service_agreement_task(self, property_id, is_verified=False, verified_at=None, ip_address=None):

    print("Inside Service Agreement Task")
    
    try:
        property = Property.objects.get(id=property_id)
        
        if property:
            property_name = property.name
            property_address = f"{property.area_name}, {property.city_name}, {property.state}, {property.country}"
            date = datetime.now()
            
            # If not verified, generate a unique verification token
            if not is_verified:
                verification_token = str(uuid.uuid4())
                property.verify_token = verification_token
                property.save()
            
            pdf_context = {
                'property_name': property_name,
                'property_address': property_address,
                'date': date,
                'is_verified': is_verified
            }
            
            # Add verification details if available
            if is_verified and verified_at and ip_address:
                verified_date = datetime.fromisoformat(verified_at)
                pdf_context['verified_date'] = verified_date.strftime('%d-%B-%Y %H:%M:%S')
                pdf_context['ip_address'] = ip_address
            
            # Generate the PDF agreement
            try:
                print(f"Generating {'verified' if is_verified else 'initial'} service agreement PDF")
                if is_verified:
                    # Generate and save PDF to database
                    pdf_result = generate_service_agreement_pdf(
                        pdf_context, 
                        property_id=property_id,
                        save_to_db=True,
                        property_obj=property
                    )
                else:
                    # Generate PDF without saving to database
                    pdf_result = generate_service_agreement_pdf(
                        pdf_context, 
                        property_id=property_id,
                        save_to_db=False
                    )
                
                # Send email to hotelier with the agreement attached
                if property.email:
                    if is_verified:
                        # For verified agreements, send verification confirmation
                        email_context = {
                            'name': 'Hotelier',
                            'property_name': property_name,
                            'ip_address': ip_address,
                            'verified_at': pdf_context.get('verified_date')
                        }
                        print("Verified email_context", email_context)
                        
                        send_agreement_email(
                            property, 
                            pdf_result, 
                            email_context,
                            is_verification=True
                        )
                        print(f"Verification confirmation email sent to {property.email}")
                    else:
                        # For initial agreements, send request for verification
                        email_context = {
                            'name': 'Hotelier',
                            'property_name': property_name,
                            'commission': '20%',
                            'token': property.verify_token
                        }
                        print("Initial email_context", email_context)
                        
                        send_agreement_email(
                            property, 
                            pdf_result, 
                            email_context,
                            is_verification=False
                        )
                        print(f"Service agreement email sent to {property.email}")
                else:
                    print(f"No email address found for property {property_id}")
                
                return pdf_result
                
            except Exception as e:
                print(f"Error generating service agreement PDF: {str(e)}")
                raise
                
    except Property.DoesNotExist:
        print(f"Property with ID {property_id} does not exist")
        raise
    except Exception as e:
        print(f"Error in create_service_agreement_task: {str(e)}")
        raise

@celery_idbook.task(bind=True)
def send_hotel_receipt_email_task(self, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        commission = booking.commission_info
        room_details = booking.hotel_booking.confirmed_room_details[0]
        booking_slot = room_details.get('booking_slot', booking.hotel_booking.booking_slot)
        checkin = booking.hotel_booking.confirmed_checkin_time
        checkout = booking.hotel_booking.confirmed_checkout_time

        hotel = booking.hotel_booking.confirmed_property
        recipient_email = hotel.email
        print("recipient_email", recipient_email)

        context = {
            "booking_id": booking.reference_code,
            "booking_date": datetime.now(),
            "reservation_datetime": datetime.now(),
            "check_in_date": checkin,
            "check_out_date": checkout,
            "booking_slot": booking_slot,
            "day_count": room_details.get("no_of_days") if booking_slot == "24 Hrs" else None,
            "hour_count": room_details.get("booking_slot") if booking_slot != "24 Hrs" else None,
            "guest_name": booking.user.name,
            "hotel_name": booking.hotel_booking.confirmed_property.name,
            "room_type": booking.hotel_booking.room_type,
            "num_adults": booking.adult_count,
            "num_children": booking.child_count,
            "num_rooms": room_details.get("no_of_rooms"),

            # Amount Details
            "room_charges": float(booking.subtotal),
            "property_tax": float(booking.gst_amount),
            "extra_charges": float(room_details.get("extra_bed_price", 0)),
            "coupon_code": booking.coupon_code,
            "discount_text": f"INR {float(booking.discount)}" if booking.discount else "None",
            "pro_discount": booking.pro_member_discount_percent,
            "pro_discount_value": booking.pro_member_discount_value,
            "final_amount": float(booking.final_amount),
            "commission_amount": float(commission.com_amnt),
            "commission_tax": float(commission.tax_amount),
            "payable_amount": float(commission.hotelier_amount),
        }
        
        # Generate the PDF receipt and save it to the booking object
        try:
            pdf_bytes = generate_hotel_receipt_pdf(context, booking_id=booking_id, booking_obj=booking)
            
            email_template = get_template('email_template/hotelier-receipt.html')
            html_content = email_template.render(context)
            subject = f"Hotelier Receipt for Booking - {booking.reference_code}"
            
            send_receipt_email_with_attachment(
                subject,
                hotel,
                [recipient_email],
                html_content,
                pdf_bytes,
                f"Hotel_Receipt_{booking.reference_code}.pdf"
            )
            
            print(f"Receipt email with attachment sent to {recipient_email} for booking {booking.reference_code}")
            return True
        except Exception as e:
            print(f"Error generating or attaching PDF: {e}")
            # Fallback to sending email without attachment if PDF generation fails
            email_template = get_template('email_template/hotelier-receipt.html')
            html_content = email_template.render(context)
            subject = f"Hotelier Receipt for Booking - {booking.reference_code}"
            send_booking_email(subject, hotel, [recipient_email], html_content)
            print(f"Receipt email sent without attachment to {recipient_email} for booking {booking.reference_code}")
            return False
    except Booking.DoesNotExist:
        print(f"Booking with id {booking_id} not found")
        return None
    except Exception as e:
        print(f"Error in sending hotel receipt email: {e}")
        return None