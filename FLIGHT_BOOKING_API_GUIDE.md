# 🛫 Flight Booking API Usage Guide

## ❌ **Problem You Encountered**

Your request had `"total_amount": "0"`, which caused:
1. **No AirIQ call** - Because invalid pricing (0 amount)
2. **No final_amount** - Because pricing calculation failed
3. **No PNR data** - Because AirIQ booking wasn't created
4. **No payment redirect** - Because validation failed early

## ✅ **Solution: Proper Flight Booking Flow**

### **Required API Call Sequence:**

#### **1. Search Flights**
```http
POST /api/v1/flights/search/
{
  "trip_type": "O",
  "origin": "DEL",
  "destination": "BOM", 
  "departure_date": "20251120",
  "adult_count": 1,
  "child_count": 0,
  "infant_count": 0
}

Response includes: track_id, flight options
```

#### **2. Get Pricing** 
```http
POST /api/v1/flights/pricing/
{
  "track_id": "AQ161430230821344...",
  "flight_option_id": "...",
  "adults": 1,
  "children": 0,
  "infants": 0
}

Response includes: pricing_token, total_amount, segments
```

#### **3. Create Booking (Optimized Request)**
```http
POST /api/v1/booking/bookings/
{
  "booking_type": "FLIGHT",
  
  // === REQUIRED: Session Link ===
  "track_id": "{{track_id}}",           // From search
  "pricing_token": "{{pricing_token}}", // From pricing
  
  // === REQUIRED: Valid Pricing ===
  "total_amount": "15750",              // From pricing response (NOT "0"!)
  
  // === REQUIRED: User Data ===
  "passengers": [
    {
      "passenger_type": "ADT",
      "title": "MR", 
      "first_name": "JOHN",
      "last_name": "DOE",
      "date_of_birth": "1990-01-01",
      "gender": "male"
    }
  ],
  "contact": {
    "country_code": "91",
    "phone": "7338085595", 
    "email": "user@example.com"
  },
  
  // === REQUIRED: Block Choice ===
  "block_pnr": false,  // false = immediate payment, true = hold booking
  
  // === AUTO-PREFILLED (optional to send) ===
  "flight_segments": {{flight_segments}}, // From pricing (can be omitted)
  "base_origin": "DEL",                    // From search (can be omitted) 
  "base_destination": "BOM",               // From search (can be omitted)
  "trip_type": "O",                        // From search (can be omitted)
  "adult_count": 1,                        // From search (can be omitted)
  "child_count": 0,                        // From search (can be omitted)
  
  // === OPTIONAL: User Preferences ===
  "gst_info": {},
  "seats": [],
  "baggage": [],
  "meals": []
}
```

---

## 🔄 **Response Patterns**

### **✅ For block_pnr: true (Hold Booking)**
```json
{
  "status": "success",
  "message": "Booking Created - Hold expires in 30 minutes",
  "data": {
    "id": 16442,
    "status": "pending",
    "final_amount": 15750,
    "flight_booking": {
      "status": "HELD",
      "airiq_pnr": "ABCD123", 
      "airline_pnr": "6E4567",
      "hold_expires_at": "2024-01-15T12:30:00Z"
    }
  }
}
```

### **✅ For block_pnr: false (Immediate Payment Required)**
```json
{
  "status": "error",
  "message": "Payment is required to confirm this booking",
  "error_code": "PAYMENT_REQUIRED",
  "data": {
    "booking_id": 16442,
    "amount": 15750,
    "payment_required": true,
    "redirect_to_payment": true,
    "flight_booking": {
      "status": "PENDING_PAYMENT",
      "airiq_pnr": "ABCD123",
      "airline_pnr": "6E4567"
    }
  }
}
```

---

## 🚨 **Common Mistakes to Avoid**

### **❌ Invalid total_amount**
```json
{
  "total_amount": "0"        // ❌ Will fail validation
  "total_amount": 0          // ❌ Will fail validation  
  "total_amount": ""         // ❌ Will fail validation
}
```

### **✅ Valid total_amount**
```json
{
  "total_amount": "15750"    // ✅ From pricing response
}
```

### **❌ Missing required fields**
```json
{
  // ❌ Missing passengers
  // ❌ Missing contact
  // ❌ Missing track_id or pricing_token
}
```

### **✅ Minimal valid request**
```json
{
  "booking_type": "FLIGHT",
  "track_id": "AQ16143...",
  "pricing_token": "AQAG059...",
  "total_amount": "15750",
  "passengers": [{...}],
  "contact": {...},
  "block_pnr": true
}
```

---

## 🔧 **Data Flow Explanation**

### **What Happens Behind the Scenes:**

1. **Validation**: Check required user data and pricing
2. **AirIQ Call**: Create booking with complete payload
3. **Pricing Calculation**: Calculate GST, taxes, final amount
4. **Status Determination**: 
   - `block_pnr: true` → `HELD` status
   - `block_pnr: false` → `PENDING_PAYMENT` status
5. **Response**: Return booking data or payment redirect

### **Smart Prefilling Logic:**

- ✅ **User provides**: `track_id` only → System retrieves all session data
- ✅ **User provides**: Full data → System uses provided data as overrides
- ✅ **Flexible**: Works with minimal or complete requests

---

## 🎯 **Testing Your Fix**

### **Update Your Request:**
```diff
{
  "booking_type": "FLIGHT",
  "track_id": "{{track_id}}",
  "pricing_token": "{{pricing_token}}",
- "total_amount": "0",
+ "total_amount": "15750",        // Use actual pricing amount!
  "passengers": [...],
  "contact": {...},
  "block_pnr": true
}
```

### **Expected Results:**
1. **✅ AirIQ call made** - With proper payload
2. **✅ Valid pricing** - GST, taxes calculated
3. **✅ PNR data saved** - AirIQ PNR, airline PNR
4. **✅ Proper status** - HELD or PENDING_PAYMENT
5. **✅ Payment redirect** - For block_pnr: false

---

## 📋 **API Validation Rules**

The system now validates:

1. **Required Fields**: passengers, contact, session link
2. **Valid Pricing**: total_amount > 0
3. **Session Data**: track_id or pricing_token present
4. **Passenger Count**: Matches adult/child/infant counts
5. **GST Completeness**: If GST number provided, all fields required

---

## 🚀 **Next Steps**

1. **Get valid pricing** from /flights/pricing/ endpoint
2. **Use real total_amount** in booking request  
3. **Test both flows**:
   - `block_pnr: true` (hold booking)
   - `block_pnr: false` (immediate payment)
4. **Handle payment redirect** for immediate bookings
5. **Process payment** to confirm booking

The system is now properly set up to handle the complete flight booking flow with AirIQ integration! 🎉