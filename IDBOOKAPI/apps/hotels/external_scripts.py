from apps.hotels.models import Room


def change_json_12hr_price():
    rooms = Room.objects.all()
    for room in rooms:
        try:
            room_json = room.room_price
            room_json['price_12hrs'] = room_json.pop('price_12_hrs')
            room.room_price = room_json
            room.save()
            print(room.id)
        except Exception as e:
            print(e)
