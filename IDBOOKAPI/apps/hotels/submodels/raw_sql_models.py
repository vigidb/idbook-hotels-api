from .__init__ import *


class CalendarRoom(models.Model):
    property_id = models.BigIntegerField()
    room_id = models.BigIntegerField()
    no_unavailable_rooms = models.PositiveSmallIntegerField(default=0)
    blocked_booked = models.CharField(max_length=50)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    class Meta:
        managed = False
    
