# coupon utils

def apply_coupon_based_discount(discount, discount_type, subtotal):
    if discount and discount_type:
        if discount_type == 'AMOUNT':
            subtotal = subtotal - discount
        elif discount_type == 'PERCENT':
            discount = (discount * subtotal) / 100
            subtotal = subtotal - discount
    return discount, subtotal
