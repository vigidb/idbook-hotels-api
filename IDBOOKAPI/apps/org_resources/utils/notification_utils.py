

def booking_comfirmed_notification_template(booking_id, booking_type, confirmation_code, notification_dict):
    try:
        # Notification
        title = "{booking_type} Booking Confirmed".format(booking_type=booking_type)
        description = "We are pleased to confirm your {booking_type} booking. \
The confirmation code is: {confirmation_code}".format(booking_type=booking_type,
                                              confirmation_code=confirmation_code)
        redirect_url = "/bookings/{booking_id}".format(booking_id=booking_id)
     
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Error', e)

    return notification_dict

def booking_cancelled_notification_template(booking_id, booking_type, cancellation_code, notification_dict):
    try:
        # Notification
        title = "{booking_type} Booking Cancelled".format(booking_type=booking_type)
        description = " We regret to inform you that your {booking_type} booking has been successfully cancelled.\
The cancellation code is: {cancellation_code}".format(booking_type=booking_type,
                                                      cancellation_code=cancellation_code)
        redirect_url = "/bookings/{booking_id}".format(booking_id=booking_id)
     
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Error', e)

    return notification_dict

def booking_completed_notification_template(booking_id, booking_type, notification_dict):
    try:
        # Notification
        title = "Hotel Stay Completed"
        description = "Thank you for choosing Idbook! Your Hotel stay has been completed. We hope you enjoyed your stay and would appreciate your feedback."
        redirect_url = "https://www.ambitionbox.com/overview/idbook-hotels-overview"
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Error', e)
    return notification_dict

def wallet_minbalance_notification_template(wallet_balance, notification_dict):
    try:

        wallet_balance = float(wallet_balance)
        
        title = "Low Wallet Balance Notification"
        description = " A gentle reminder that your Idbook wallet balance \
is LOW ({wallet_balance} INR)".format(wallet_balance=wallet_balance)
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        
    except Exception as e:
        print('Notification Wallet Balance Template Error', e)

    return notification_dict

def wallet_booking_balance_notification_template(booking, wallet_balance, notification_dict):
    try:
        booking_type = booking.booking_type
        wallet_balance = float(wallet_balance)
        booking_amount = float(booking.final_amount)
        
        # balance_amount = booking_amount - booking.total_payment_made
        title = "Low Wallet Balance Notification"
        description = " A gentle reminder that your Idbook wallet balance \
is LOW ({wallet_balance} INR) for the {booking_type} booking. \
Your total booking amount is {booking_amount}. \
Please recharge your wallet to confirm booking".format(
    wallet_balance=wallet_balance, booking_type=booking_type, booking_amount=booking_amount)
        redirect_url = "/bookings/{booking_id}".format(booking_id=booking.id)
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Wallet Balance Template Error', e)

    return notification_dict
