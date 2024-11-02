

def booking_comfirmed_notification_template(booking_id, booking_type, confirmation_code, notification_dict):
    try:
        # Notification
        title = "{booking_type} Booking Confirmed".format(booking_type=booking_type)
        description = "We are pleased to confirm your {booking_type} booking. \
The confirmation code is: {confirmation_code}".format(booking_type=booking_type,
                                              confirmation_code=confirmation_code)
        redirect_url = "/booking/bookings/{booking_id}/".format(booking_id=booking_id)
     
        
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
        redirect_url = "/booking/bookings/{booking_id}/".format(booking_id=booking_id)
     
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        notification_dict['redirect_url'] = redirect_url
        
    except Exception as e:
        print('Notification Error', e)

    return notification_dict

def wallet_minbalance_notification_template(wallet_balance, notification_dict):
    try:
        title = "Low Wallet Balance Notification"
        description = " A gentle reminder that your Idbook wallet balance \
is LOW ({wallet_balance} INR)".format(wallet_balance=wallet_balance)
        
        notification_dict['title'] = title
        notification_dict['description'] = description
        
    except Exception as e:
        print('Notification Wallet Balance Template Error', e)

    return notification_dict
