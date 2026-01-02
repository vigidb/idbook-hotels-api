# Socket-Based Room Availability API Guide

## Overview
The Room Availability Socket provides real-time room availability information for hotel properties. It calculates availability by considering:
- Total available rooms
- Booked rooms (confirmed and on_hold bookings)
- Blocked rooms (manually blocked by hoteliers)
- Dynamic pricing (if configured)

## Development Setup

### Prerequisites

1. **Redis Server** (Required for Channel Layers)
   ```bash
   # Install Redis (macOS)
   brew install redis
   
   # Start Redis
   brew services start redis
   # OR run manually
   redis-server
   
   # Verify Redis is running
   redis-cli ping  # Should return "PONG"
   ```

2. **Daphne ASGI Server** (Required for WebSocket support)
   ```bash
   # Install Daphne (already in requirements.txt)
   pip install daphne==4.1.2
   ```

### Running the Server

**⚠️ Important:** Django's default `runserver` does NOT support WebSockets. You must use an ASGI server.

#### Option 1: Using Daphne (Recommended)
```bash
# From the IDBOOKAPI directory
cd IDBOOKAPI
daphne -b 0.0.0.0 -p 8000 IDBOOKAPI.asgi:application
```

#### Option 2: Using Uvicorn
```bash
# Install uvicorn if not already installed
pip install uvicorn[standard]

# Run with uvicorn
cd IDBOOKAPI
uvicorn IDBOOKAPI.asgi:application --host 0.0.0.0 --port 8000
```

#### Option 3: Using Django's runserver (Limited - HTTP only, no WebSockets)
```bash
# This will NOT work for WebSockets!
python manage.py runserver  # ❌ WebSockets won't work
```

### Verify Setup

1. **Check Redis is running:**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

2. **Check Daphne is installed:**
   ```bash
   daphne --version
   ```

3. **Test WebSocket connection:**
   - Start server with Daphne
   - Try connecting to: `ws://localhost:8000/ws/socket/room-availability/2/`
   - Should connect successfully

### Troubleshooting

**Error: "No addresses found" or Connection Refused**
- ✅ Make sure you're running Daphne/uvicorn, NOT `runserver`
- ✅ Verify Redis is running: `redis-cli ping`
- ✅ Check the port (8000) is not already in use
- ✅ Verify `daphne` is in `INSTALLED_APPS` (first in the list)

**Error: "Connection refused" on Redis**
- Start Redis: `redis-server` or `brew services start redis`
- Check Redis port (default 6379) matches settings.py

**WebSocket connects but no response**
- Check server logs for errors
- Verify the date format in your request matches expected format
- Check that property_id exists in database

**Warning: pkg_resources is deprecated**
- This is a harmless deprecation warning from `rest_framework_simplejwt`
- The server is still running correctly
- To suppress the warning, you can:
  ```python
  # In settings.py, add at the top:
  import warnings
  warnings.filterwarnings('ignore', category=UserWarning, module='rest_framework_simplejwt')
  ```
  Or update `djangorestframework-simplejwt` to a newer version when available

## WebSocket URL

```
ws://your-domain/ws/socket/room-availability/{property_id}/
```

**Example:**
```
ws://localhost:8000/ws/socket/room-availability/123/
```

## How It Works

### 1. Connection
- Client connects to the WebSocket endpoint with a `property_id` in the URL
- Server creates a room group: `customer_room_availability_{property_id}`
- Connection is accepted and client joins the group

### 2. Request Format (Manual Request)
Once connected, send a JSON message with check-in and check-out times to get availability:

```json
{
  "confirmed_checkin_time": "2024-01-15T14:00:00Z",
  "confirmed_checkout_time": "2024-01-17T11:00:00Z"
}
```

### 3. Automatic Updates (Real-time Push)
**The socket automatically pushes updates when:**
- ✅ A room is booked (booking created/updated/deleted)
- ✅ A room is blocked by hotelier (BlockedProperty created/updated/deleted)
- ✅ Dynamic pricing is changed (DynamicRoomPricing created/updated/deleted)
- ✅ Room default pricing is updated

**No need to send a request** - updates are pushed automatically to all connected clients!

### 4. Response Format
The server broadcasts availability data to all connected clients in the room group:

```json
{
  "room_availability": [
    {
      "id": 1,
      "type": "DELUXE ROOM",
      "no_available_rooms": 10,
      "no_booked_room": 3,
      "no_of_blocked_rooms": 2,
      "current_available_room": 5,
      "pricing": {
        "default_pricing": {
          "base_rate": 5000,
          "price_4hrs": 2000,
          "price_8hrs": 3000,
          "price_12hrs": 4000,
          "extra_bed_price": 500,
          "child_bed_price": [
            {
              "age_limit": [0, 4],
              "child_bed_price": 0
            },
            {
              "age_limit": [5, 12],
              "child_bed_price": 300
            }
          ],
          "pet_charges": 0
        },
        "has_dynamic_pricing": true,
        "dynamic_pricing": {
          "2024-01-15": {
            "room_price": {
              "base_rate": 6000,
              "price_4hrs": 2500,
              "price_8hrs": 3500,
              "price_12hrs": 4500
            }
          },
          "2024-01-16": {
            "room_price": {
              "base_rate": 7000,
              "price_4hrs": 3000,
              "price_8hrs": 4000,
              "price_12hrs": 5000
            }
          }
        },
        "is_slot_price_enabled": true
      }
    }
  ],
  "property": 123,
  "checkin_time": "2024-01-15T14:00:00+00:00",
  "checkout_time": "2024-01-17T11:00:00+00:00"
}
```

**Automatic Update Response:**
```json
{
  "room_availability": [
    {
      "id": 1,
      "type": "DELUXE ROOM",
      "no_available_rooms": 10,
      "no_booked_room": 4,
      "no_of_blocked_rooms": 2,
      "current_available_room": 4,
      "pricing": {...}
    }
  ],
  "property": 123,
  "auto_update": true
}
```

**Note:** Automatic updates include `"auto_update": true` and don't include `checkin_time`/`checkout_time` since they use the date range from the booking/block that triggered the update.
```

## Edge Cases & Validations

The socket implementation handles the following edge cases:

### 1. Property Status Validation
- **On Connection**: Validates that the property exists and has `status="Active"`
- **Behavior**: Connection is rejected if property doesn't exist or is inactive
- **Error**: Connection closes with code `4004` if validation fails

### 2. Past Date Validation
- **Check-in Time**: Must be in the future (cannot be in the past)
- **Check-out Time**: Must be in the future (cannot be in the past)
- **Error Message**: Returns clear error message: "Check-in time cannot be in the past" or "Check-out time cannot be in the past"

### 3. Date Range Validation
- **Check-in < Check-out**: Ensures checkout time is after checkin time
- **Error Message**: "Checkout time must be after checkin time"

### 4. Booking Type Detection
The socket automatically detects the booking type based on duration:
- **≤ 4 hours**: `"4 Hrs"` (Hourly booking)
- **≤ 8 hours**: `"8 Hrs"` (Hourly booking)
- **≤ 12 hours**: `"12 Hrs"` (Hourly booking)
- **> 12 hours**: `"24 Hrs"` (Day-based booking)

The `booking_type` is included in the response for manual requests.

## Support for Day-Based & Hourly Bookings

The socket API properly supports **both** booking models:

### Day-Based Bookings (24 Hrs)
- **Use Case**: Traditional overnight hotel stays
- **Duration**: More than 12 hours
- **Availability Calculation**: Uses datetime comparisons to check for overlapping bookings
- **Pricing**: Uses `base_rate` from `room_price` JSON field

### Hourly Bookings (4, 8, 12 Hrs)
- **Use Case**: Short-term stays, day-use rooms, meeting rooms
- **Duration**: 4, 8, or 12 hours
- **Availability Calculation**: Uses **exact datetime comparisons** (not just dates) to ensure accurate slot-based availability
- **Pricing**: Uses slot-specific prices:
  - `price_4hrs` for 4-hour bookings
  - `price_8hrs` for 8-hour bookings
  - `price_12hrs` for 12-hour bookings
- **Room Flag**: Rooms with `is_slot_price_enabled=True` support hourly bookings

### How It Works

1. **Booking Detection**: The socket calculates the duration between check-in and check-out times
2. **Type Classification**: Automatically classifies as hourly (4/8/12 Hrs) or day-based (24 Hrs)
3. **Availability Query**: The backend uses datetime comparisons for both types:
   ```python
   # Works for both hourly and day-based bookings
   confirmed_checkin_time__lt=check_out
   confirmed_checkout_time__gt=check_in
   ```
4. **Pricing Response**: Returns both default and slot pricing in the response:
   ```json
   {
     "pricing": {
       "default_pricing": {
         "base_rate": 1000,
         "price_4hrs": 400,
         "price_8hrs": 600,
         "price_12hrs": 800
       },
       "is_slot_price_enabled": true,
       "has_dynamic_pricing": false
     }
   }
   ```

### Frontend Usage for Both Models

```javascript
// Example: Handle both booking types
function getPriceForBooking(room, checkin, checkout, bookingType) {
  const pricing = room.pricing;
  
  // For hourly bookings, use slot-specific price
  if (bookingType !== "24 Hrs" && pricing.is_slot_price_enabled) {
    const slotKey = bookingType.toLowerCase().replace(" ", ""); // "4hrs", "8hrs", "12hrs"
    const slotPrice = pricing.default_pricing[`price_${slotKey}`];
    if (slotPrice && slotPrice > 0) {
      return slotPrice;
    }
  }
  
  // For day-based bookings or fallback, use base_rate
  return pricing.default_pricing.base_rate;
}
```

## Availability Calculation

The system properly calculates availability by:

1. **Total Available Rooms**: Base count from `Room.no_available_rooms`
2. **Booked Rooms**: Counts rooms from:
   - Confirmed bookings (`status='confirmed'`)
   - On-hold bookings (`status='on_hold'` with valid `on_hold_end_time`)
   - Only bookings that overlap with the requested date range
3. **Blocked Rooms**: Counts rooms from:
   - Active `BlockedProperty` records
   - Only blocks that overlap with the requested date range
4. **Current Available**: 
   ```
   current_available_room = no_available_rooms - (no_booked_room + no_of_blocked_rooms)
   ```

### Date Range Filtering
- **Booked Rooms**: Uses `confirmed_checkin_time < checkout` AND `confirmed_checkout_time > checkin`
- **Blocked Rooms**: Uses `start_date < end_date` AND `end_date > start_date`
- Both properly handle datetime comparisons for accurate overlap detection

## Pricing Logic

### Default vs Dynamic Pricing

The API returns **both** default and dynamic pricing:

1. **Default Pricing**: Always included from `Room.room_price` JSON field
2. **Dynamic Pricing**: Included if available for the date range
   - Checked per date in the date range
   - Only active `DynamicRoomPricing` records are considered
   - Returns pricing for each date that has dynamic pricing configured

### Pricing Priority (Frontend Decision)

**Recommended Frontend Logic:**
```javascript
function getRoomPrice(room, date) {
  const pricing = room.pricing;
  
  // Check if dynamic pricing exists for this date
  if (pricing.has_dynamic_pricing && pricing.dynamic_pricing[date]) {
    return pricing.dynamic_pricing[date].room_price;
  }
  
  // Fall back to default pricing
  return pricing.default_pricing;
}
```

## On-Hold Bookings (Real-Time Updates)

The socket automatically tracks and broadcasts updates for bookings that are "on hold" (in the booking process).

### How It Works

1. **When a booking is placed on hold:**
   - The `hotel/pre-confirm` API creates a booking with `status="on_hold"`
   - The booking has an `on_hold_end_time` (typically 5 minutes from creation)
   - The socket signal automatically broadcasts an availability update
   - Rooms on hold are **temporarily removed** from available count

2. **Availability Response Includes:**
   ```json
   {
     "room_availability": [
       {
         "id": 114,
         "type": "Deluxe",
         "no_available_rooms": 10,
         "no_booked_room": 3,  // Includes confirmed + on_hold bookings
         "no_of_on_hold_rooms": 1,  // Separate count for display
         "no_of_blocked_rooms": 0,
         "current_available_room": 7,  // Already accounts for on_hold
         "pricing": {...}
       }
     ]
   }
   ```

3. **Frontend Display:**
   - Show `no_of_on_hold_rooms` to indicate "X rooms being booked"
   - Display a message like: "1 room is currently being booked by another customer"
   - Update in real-time as holds are created or expire

4. **When Holds Expire:**
   - The availability automatically updates (expired holds are filtered out)
   - For real-time updates when holds expire, run the periodic task:
     ```bash
     python manage.py check_expired_holds
     ```
   - Recommended: Set up a cron job or Celery beat to run this every minute

### Automatic Updates

The socket broadcasts updates when:
- ✅ Booking is created with `status="on_hold"`
- ✅ Booking status changes to `on_hold`
- ✅ Booking is confirmed (status changes to `confirmed`)
- ✅ Booking is canceled
- ✅ Booking hold expires (if periodic task is running)

### Periodic Task Setup

For production, set up a cron job to check for expired holds:

```bash
# Add to crontab (runs every minute)
* * * * * cd /path/to/project && python manage.py check_expired_holds
```

Or use Celery Beat:
```python
# In your Celery configuration
from celery.schedules import crontab

app.conf.beat_schedule = {
    'check-expired-holds': {
        'task': 'apps.socket_com.tasks.check_expired_holds',
        'schedule': crontab(minute='*'),  # Every minute
    },
}
```

### Slot Pricing

If `is_slot_price_enabled` is `true`:
- Use slot-specific prices: `price_4hrs`, `price_8hrs`, `price_12hrs`
- Otherwise, use `base_rate` for 24-hour bookings

## Frontend Implementation

### JavaScript Example (using WebSocket API)

```javascript
// Connect to socket
const propertyId = 123;
const socket = new WebSocket(`ws://your-domain/ws/socket/room-availability/${propertyId}/`);

// Connection opened
socket.onopen = function(event) {
  console.log('Connected to room availability socket');
  
  // Request availability for date range
  const request = {
    confirmed_checkin_time: "2024-01-15T14:00:00Z",
    confirmed_checkout_time: "2024-01-17T11:00:00Z"
  };
  
  socket.send(JSON.stringify(request));
};

// Listen for availability updates
socket.onmessage = function(event) {
  const data = JSON.parse(event.data);
  const rooms = data.room_availability;
  
  rooms.forEach(room => {
    console.log(`Room ${room.type}:`);
    console.log(`  Available: ${room.current_available_room}`);
    console.log(`  Booked: ${room.no_booked_room}`);
    console.log(`  Blocked: ${room.no_of_blocked_rooms}`);
    
    // Get pricing for a specific date
    const checkinDate = "2024-01-15";
    const price = getRoomPrice(room, checkinDate);
    console.log(`  Price for ${checkinDate}:`, price);
  });
};

// Handle errors
socket.onerror = function(error) {
  console.error('WebSocket error:', error);
};

// Connection closed
socket.onclose = function(event) {
  console.log('Socket connection closed');
};

// Helper function to get price
function getRoomPrice(room, date) {
  const pricing = room.pricing;
  
  if (pricing.has_dynamic_pricing && pricing.dynamic_pricing[date]) {
    return pricing.dynamic_pricing[date].room_price;
  }
  
  return pricing.default_pricing;
}
```

### React Example

```jsx
import { useEffect, useState } from 'react';

function useRoomAvailability(propertyId, checkin, checkout) {
  const [rooms, setRooms] = useState([]);
  const [socket, setSocket] = useState(null);

  useEffect(() => {
    if (!propertyId || !checkin || !checkout) return;

    const ws = new WebSocket(
      `ws://your-domain/ws/socket/room-availability/${propertyId}/`
    );

    ws.onopen = () => {
      ws.send(JSON.stringify({
        confirmed_checkin_time: checkin,
        confirmed_checkout_time: checkout
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setRooms(data.room_availability || []);
    };

    ws.onerror = (error) => {
      console.error('Socket error:', error);
    };

    setSocket(ws);

    return () => {
      ws.close();
    };
  }, [propertyId, checkin, checkout]);

  // Request update when dates change
  useEffect(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        confirmed_checkin_time: checkin,
        confirmed_checkout_time: checkout
      }));
    }
  }, [checkin, checkout, socket]);

  return rooms;
}

// Usage in component
function RoomAvailability({ propertyId, checkin, checkout }) {
  const rooms = useRoomAvailability(propertyId, checkin, checkout);

  return (
    <div>
      {rooms.map(room => (
        <div key={room.id}>
          <h3>{room.type}</h3>
          <p>Available: {room.current_available_room}</p>
          <p>Booked: {room.no_booked_room}</p>
          <p>Blocked: {room.no_of_blocked_rooms}</p>
          <p>Price: {getRoomPrice(room, checkin)}</p>
        </div>
      ))}
    </div>
  );
}
```

## API Suitability for Socket-Based Hotel Room Management

### ✅ Strengths

1. **Real-time Updates**: All connected clients receive updates simultaneously
2. **Accurate Availability**: Properly counts booked and blocked rooms
3. **Date Range Support**: Handles check-in/check-out date ranges correctly
4. **Pricing Integration**: Includes both default and dynamic pricing
5. **Efficient**: Uses raw SQL queries for performance
6. **Scalable**: Uses Django Channels for WebSocket support

### ⚠️ Considerations

1. **No Automatic Updates**: Client must send a message to trigger availability check
2. **No Room-Level Filtering**: Returns all rooms for the property
3. **No Caching**: Each request queries the database
4. **Error Handling**: Basic error handling (prints to console)

### Recommendations

1. **Add Auto-Refresh**: Consider sending periodic updates when bookings change
2. **Add Room Filtering**: Allow filtering by room type or ID
3. **Add Caching**: Cache availability for short periods to reduce DB load
4. **Improve Error Handling**: Return structured error messages to clients
5. **Add Authentication**: Currently no authentication required (consider adding)

## Testing

### Test Scenarios

1. **Basic Availability**: Connect and request availability for a date range
2. **With Bookings**: Create a booking and verify availability decreases
3. **With Blocks**: Create a block and verify availability decreases
4. **Dynamic Pricing**: Set dynamic pricing and verify it's returned
5. **Multiple Clients**: Connect multiple clients and verify all receive updates
6. **Date Range Edge Cases**: Test overlapping dates, same-day bookings, etc.

### Sample Test Script

```python
import asyncio
import websockets
import json

async def test_room_availability():
    uri = "ws://localhost:8000/ws/socket/room-availability/123/"
    
    async with websockets.connect(uri) as websocket:
        # Send availability request
        request = {
            "confirmed_checkin_time": "2024-01-15T14:00:00Z",
            "confirmed_checkout_time": "2024-01-17T11:00:00Z"
        }
        await websocket.send(json.dumps(request))
        
        # Receive response
        response = await websocket.recv()
        data = json.loads(response)
        print(json.dumps(data, indent=2))

asyncio.run(test_room_availability())
```

## Summary

The socket-based room availability API is **well-suited** for real-time hotel room management:

- ✅ Properly calculates availability (booked + blocked)
- ✅ Includes pricing (default + dynamic)
- ✅ Real-time updates to all connected clients
- ✅ Efficient database queries
- ✅ Supports date range filtering

**Frontend should:**
- Use dynamic pricing if available, otherwise default pricing
- Handle slot pricing when `is_slot_price_enabled` is true
- Update UI when new availability data is received
- Re-request availability when date range changes
