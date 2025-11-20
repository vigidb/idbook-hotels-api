
Welcome
9218077408
Logout
AAS NEW GEN API
API Version 2.0
1.Introduction
2.Access URL
3.Login
4. Availability
5. Fare Rules
6. Pricing
7. Seatmap
8. Booking
9. Ticketing
10. Get Booking
11. Get Account Balance
12. Booking Track Status
13 Cancellation
14. Reschedule
15. Post Ancillary
16. Hold Cancel
17. GetMultiClass
18. GetMultiClassFare
19. Support
20. Annexure
19. Download Samples
Cockpit Console
AirIQ API Service’s (Rest API – Latest) AAS
The Access URL, Authentication, Request, and Response formats are all included in this document, which serves as the API (Application Programming Interface) Reference Handbook.

API Reference Manual of AAS
Document History
The Application Programming Interface (API) User Guide document history lists the changes made to each edition, along with the part that was affected and an explanation of the change.

Version	2.0
Date	30-JUNE-2025
Changes	Document Created (First Reseles)
Disclaimer
This information is proprietary to AiriqOnline.in and may only be used in line with a documented license agreement has been consented by AiriqOnline.in.

1. Introduction
A method of accessing and utilising data from its hosted services is provided by AirIQ using integrated web services known as Airiq Web Services (AAS). It offers an external plug-in a gateway to all airline tickets purchased through AirIQOnline.in. This gateway can be used to create a standalone application or be integrated into a user's current tool.

2. Access URL
Test URL :http://airiqnewapi.mywebcheck.in/TravelAPI.svc


Production URL : Will be provided by mail on successful completion of Test Cases


Methods	URL
Login	{URL}/Login
Availability	{URL}/Availability
Fare Rules	{URL}/GetFareRule
Pricing	{URL}/Pricing
Seat Map	{URL}/GetAvailSeatMap
Booking	{URL}/Book
Ticketing	{URL}/IssueTicket
Get Booking	{URL}/RetrieveBooking
Get Account Balance	{URL}/GetBalance
Booking Track Status	{URL}/TrackStatus
Cancel	{URL}/Cancel
Reschedule Avail	{URL}/RescheduleAvail
Reschedule	{URL}/Reschedule
GetSSR	{URL}/GetSSR
AddSSR	{URL}/AddSSR
HoldCancel	{URL}/HoldCancel
GetMultiClass	{URL}/GetMultiClass
GetMultiClassFare	{URL}/GetMultiClassFare
3.1 Login Method
Parameters	Value
AgentID	Your Agent ID
Username	Your Username ID
Password	Your Password ID
3.2. Description
The most straightforward method of identifying is HTTP Basic Authentication. In this method, the three credentials—Agent ID, Username, and Password—are combined into a single value and sent through a special HTTP header called Authorization, where they are Base64-encoded. The Token needs to be repeated back in each future request, and the login procedure will return it. When a token expires, the login function must be called once more, and each request after that must include the updated Token.

A maximum of 5 active logins is allowed per user account.
If the user tries to log in more than 5 times concurrently, the system block the new login attempt.
A created token is good through the end of the day.
3.3 Authentication
HTTP Basic Authentication
Step 1: Produce a Base64 string using the reasoning shown below. AgentID*Username:Password

Step 2: Use the Base64 string as described below in the request header section

Key : Authorization

Value : Base64 string (Example:QUdFTlRJRCpNT0JJTEVOTzpQQVNTV09SRA==)

3.4 Response
3.4.1 Success
Copy Code
                                                        {
                                                        "AgentID": "XXXXXXXXXXXX",
                                                        "UserName": "XXXXXXXXXXXX ",
                                                        "Token": "3HjkLnFINC1SU05LTDA0MDAxMDEwNytBSDQtOTcwK0FINC1kaGFuYWErQ=",
                                                        "Status": {
                                                        "ResultCode": "1",
                                                        "Error": "",
                                                        "SequenceID": "1221485289115"
                                                        }
​
                                                    
3.4.2 Failure
Copy Code
                                                        {
                                                        "AgentID": "",
                                                        "Status": {
                                                        "Error": "Invalid Credentials",
                                                        "ResultCode": "0",
                                                        "SequenceID": "13070550229411"},
                                                        "Token": "",
                                                        "UserName": ""
                                                        }
                                                    
3.4.3 Exception
Copy Code
                                                        {
                                                        "AgentID": "",
                                                        "Status": {
                                                        "Error": "EX-Unable to authenticate",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "13070550069411"
                                                        },
                                                        "Token": "",
                                                        "UserName": ""
                                                        }
                                                    
4 Availability
4.1 Method: Availability
4.2 Description
The availability method offers the cheapest fare choices as well as information on the flights that are currently available. The example request contains one AvailInfo query for a one-way trip. The return flight query should be added with this field if the trip is roundtrip. Booking engines begin looking for the best option among all available options after the requested query has been parsed and validated. Flight information will be returned in the ItineraryFlightList object if the search is successful.

4.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
TripType	String	>Trip Type shows the type of booking. It may be an O-Oneway or R-Roundtrip or Y-Roundtrip Special.
AirlineID	String	Two-letter airline code; mandatory for Roundtrip Special. For other cases, if left blank, the system defaults to all airlines.
DepartureStation	String	3 Letter IATA Departure Airport code
ArrivalStation	String	3 Letter IATA Arrival Airport code
FlightDate	Date	Travel date should be in the following format (yyyymmdd)
FarecabinOption	String	Cabin Identification E- Economy, P- Premium Economy, B- Business and F- First
FareType	String	Fare type indicator – N: Normal Fare, C: Corporate Fare, R: Retail Fare; mandatory for Roundtrip Special. For other cases, if left blank, the system defaults to all fare types
OnlyDirectFlight	Boolean	True –System responds only direct flight. False – System responds all the flights.
AdultCount	Integer	Minimum of 1 and Maximum up to 9
ChildCount	Integer	Total no of Adults and child can be maximum 9
InfantCount	Integer	Minimum of 1 and Maximum up to 4. Infant alone not allowed to travel
RoundTrip Special

Domestic flights with code Y: For FSC flights, you will receive a combined airline response with a single price. For LCC flights, you will receive onward and return flights with segment‑wise price breakups.
International flights with code Y: Similarly, for FSC flights, you will get a combined airline response with a single price. For LCC flights, you will get onward and return flights with segment‑wise price breakups.

4.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXXXX",
                                                        "UserName": "XXXXXXXXX",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        },
                                                        "TripType": "O",
                                                        "AirlineID": "",
                                                        "AvailInfo": [
                                                        {
                                                        "DepartureStation": "IXB",
                                                        "ArrivalStation": "DEL",
                                                        "FlightDate": "20231114",
                                                        "FarecabinOption": "E",
                                                        "FareType": "N",
                                                        "OnlyDirectFlight": false
                                                        }
                                                        ],
                                                        "PassengersInfo": {
                                                        "AdultCount": "1",
                                                        "ChildCount": "0",
                                                        "InfantCount": "0"
                                                        }
                                                        }
                                                    
4.5 Response
4.5.1 Success
Refer to the sample JSON request and response that is attached

4.5.2 Failure
Copy Code
                                                        {
                                                        "ItineraryFlightList": null,
                                                        "Status": {
                                                        "Error": "Request format is invalid",
                                                        "ResultCode": "0",
                                                        "SequenceID": "11413958113534"
                                                        },
                                                        "Trackid": null
                                                        }
                                                    
4.5.3 Exception
Copy Code
                                                        {
                                                        "ItineraryFlightList": null,
                                                        "Status": {
                                                        "Error": "Ex-Unable to fetch the flight results.",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "1141345598894"
                                                        },
                                                        "Trackid": null
                                                        }
                                                    
5 Fare Rules
5.1 Method: GetFareRule
5.2 Description
GetFarerule To obtain the terms and conditions of a specific flight option's fare, use the GetFarerule method. It includes the fare base code as well as other pertinent information.

5.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
FlightID	String	Pass the same value from Availability response.
TrackId	String	Unique reference Id from Availability response.
5.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXXXXX",
                                                        "UserName": "XXXXXXXXXX",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        },
                                                        "FlightsInfo": [
                                                        {
                                                        "FlightID": "7368"
                                                        },
                                                        {
                                                        "FlightID": "7369"
                                                        }
                                                        ],
                                                        "Trackid": "AQ130816280740263181308249563236LAHRK1IJE3F"
                                                        }
                                                    
5.5 Response
5.5.1 Success
Refer to the sample JSON request and response that is attached

5.5.2 Failure
Copy Code
                                                        {
                                                        "FareRuleInfo": null,
                                                        "Status": {
                                                        "Error": "The requested token was timed out.",
                                                        "ResultCode": "0",
                                                        "SequenceID": "11112771818929"
                                                        }
                                                        }
                                                    
5.5.3 Exception
Copy Code
                                                        {
                                                        "FareRuleInfo": null,
                                                        "Status": {
                                                        "Error": "EX-Unable to get FareRule for the requested flight",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "11205467465130"
                                                        }
                                                        }
                                                    
6 Pricing
6.1 Method: Pricing
6.2 Description
The chosen route must be re-priced using a pricing technique. If the selected fare is available, it will answer with a full fare breakdown, check-in baggage , mandatory booking details, and a list of any available SSRs, meal, baggage, and other services.

6.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
BaseOrigin	String	3 Letter IATA Departure Airport code.
BaseDestination	String	3 Letter IATA Arrival Airport code.
TripType	String	Trip Type shows the type of booking. It may be an O-Oneway or R-Roundtrip or Y-Roundtrip Special.
AdultCount	Integer	Minimum of 1 and Maximum up to 9
ChildCount	Integer	Total no of Adults and child can be maximum 9
InfantCount	Integer	Minimum of 1 and Maximum up to 4. Infant alone not allowed to travel
TrackId	String	Unique reference Id from Availability response.
FlightID	String	Pass the same value from Availability response.
FlightNumber	String	Booking Flight Number.
Origin	String	3 Letter IATA Departure Airport code.
Destination	String	3 Letter IATA Arrival Airport code.
DepartureDateTime	DateTime	Flight Departure Date and Time. [DD MMM YYYY HH:MM]
ArrivalDateTime	DateTime	Flight Arrival Date and Time. [DD MMM YYYY HH:MM]
BaseAmount	Decimal	Flight Basic Fare
GrossAmount	Decimal	Flight Gross fare
6.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXXX",
                                                        "UserName": "XXXXXXXXX",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        },
                                                        "SegmentInfo": {
                                                        "BaseOrigin": "IXB",
                                                        "BaseDestination": "DEL",
                                                        "TripType": "O",
                                                        "AdultCount": "1",
                                                        "ChildCount": "0",
                                                        "InfantCount": "0"
                                                        },
                                                        "Trackid": "AQ130816280740263181308249563236LAHRK1IJE3F",
                                                        "ItineraryInfo": [
                                                        {
                                                        "FlightDetails": [
                                                        {
                                                        "FlightID": "7368",
                                                        "FlightNumber": "6E 292",
                                                        "Origin": "IXB",
                                                        "Destination": "CCU",
                                                        "DepartureDateTime": "14 Nov 2023 14:20",
                                                        "ArrivalDateTime": "14 Nov 2023 15:25"
                                                        },
                                                        {
                                                        "FlightID": "7369",
                                                        "FlightNumber": "6E 2516",
                                                        "Origin": "CCU",
                                                        "Destination": "DEL",
                                                        "DepartureDateTime": "14 Nov 2023 16:50",
                                                        "ArrivalDateTime": "14 Nov 2023 19:25"
                                                        }
                                                        ],
                                                        "BaseAmount": "15900.00",
                                                        "GrossAmount": "19873"
                                                        }
                                                        ]
                                                        }
                                                    
6.5 Response
6.5.1 Success
Refer to the sample JSON request and response that is attached

6.5.2 Failure
The seatmap for a certain flight option can be obtained using the GetAvailSeatMap function. It includes the seat information and other pertinent information related to it, such as seat restrictions and amount

Copy Code
                                                        {
                                                        "PriceItenaryInfo": null,
                                                        "ResponseStatus": {
                                                        "Error": "The requested token was timed out.",
                                                        "ResultCode": "0",
                                                        "SequenceID": "14571588578522"
                                                        }
                                                        }
                                                    
6.5.3 Exception
Copy Code
                                                        {
                                                        "PriceItenaryInfo": null,
                                                        "ResponseStatus": {
                                                        "Error": "EX-Unable to price the requested flights.",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "14781588535522"
                                                        }
                                                        }
                                                    
7 Seat Map
7.1 Method: GetAvailSeatMap
7.2 Description
GetAvailSeatMap method is used to get the seatmap of a specific flight option. It contains the seat details and relevant details associated with it, such as seat restrictions and amount.

7.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
BaseOrigin	String	3 Letter IATA Departure Airport code.
BaseDestination	String	3 Letter IATA Arrival Airport code.
FlightID	String	Flight ID from from Pricing response.
FlightNumber	Integer	Flight Number from Pricing response.
Origin	Integer	3 Letter IATA Departure Airport code.
Destination	Integer	3 Letter IATA Arrival Airport code.
DepartureDateTime	DateTime	Flight Departure Date and Time. [DD MMM YYYY HH:MM]
ArrivalDateTime	DateTime	Flight Arrival Date and Time. [DD MMM YYYY HH:MM]
PaxRefNumber	Integer	Passenger wise unique serial reference number.
Title	String	Passenger Salutation / Title [Mr, Mrs, Miss, Ms, Mstr and Dr]
PaxType	String	Indicates booking passenger type (ADT/CHD/INF)
FirstName	String	First Name of the booking Passenger.
LastName	String	Last Name of the booking Passenger
TrackId	String	Unique reference Id from Pricing response.
7.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXX",
                                                        "UserName": "XXXXXXXXX",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        },
                                                        "SegmentInfo": {
                                                        "BaseOrigin": "IXB",
                                                        "BaseDestination": "DEL",
                                                        "TripType": "O"
                                                        },
                                                        "FlightsInfo": [
                                                        {
                                                        "FlightID": "7368",
                                                        "FlightNumber": "6E 292",
                                                        "Origin": "IXB",
                                                        "Destination": "CCU",
                                                        "DepartureDateTime": "14 Nov 2023 14:20",
                                                        "ArrivalDateTime": "14 Nov 2023 15:25"
                                                        },
                                                        {
                                                        "FlightID": "7369",
                                                        "FlightNumber": "6E 2516",
                                                        "Origin": "CCU",
                                                        "Destination": "DEL",
                                                        "DepartureDateTime": "14 Nov 2023 16:50",
                                                        "ArrivalDateTime": "14 Nov 2023 19:25"
                                                        }
                                                        ],
                                                        "APIPaxDetails": [
                                                        {
                                                        "PaxRefNumber": "1",
                                                        "Title": "Mr",
                                                        "PaxType": "ADT",
                                                        "FirstName": "TESTA",
                                                        "LastName": "TEST"
                                                        }
                                                        ],
                                                        "TrackId": "AQ131620651068521731316232989362MDJAYW12CHN"
                                                        }
                                                    
7.5 Response
Field Name	Data Type	Description
Seat Group	String	If passenger selects any premium seat or window/aisle seat, then charges will be applied on the same and will be reflected in AssignSeats response. You can identify the seat charges as well as Seat Groupfrom the tag namely ‘SeatGroup’ in GetAvailSeatMap Response.
Seat Position	String	A seat position in an airline refers to the positioning of a seat on an aircraft. Ex :- A row seats are window seats, B row seats are middle seats, and C row seats are aisle seats.
Seat Status	String	The availability of a seat on an aircraft is referred to as seat status in the airline. A code, such as "true" for availability or "false" for lack of availability.
XAxis	String	X-axis" would represent the horizontal axis. It helps in identifying the location of seats from side to side within the aircraft.
YAxis	String	Y-axis" would represent the vertical axis, It helps in identifying the location of seats from side to side within the aircraft.
Copy Code
                                                        {
                                                        "FlightSeat": [
                                                        {
                                                        "SeatMap": [
                                                        {
                                                        "Destination": "CCU",
                                                        "ItinRef": "0",
                                                        "MaxHeight": "69",
                                                        "MaxWidth": "14",
                                                        "Origin": "IXB",
                                                        "SeatAmount": "0",
                                                        "SeatAvailability": "Closed",
                                                        "SeatCategory": "",
                                                        "SeatCharacterstic": "",
                                                        "SeatGroup": "98",
                                                        "SeatID": "AQ132051322175817861320538751323B63WSHXSZQY|1640",
                                                        "SeatMessage": "",
                                                        "SeatName": "1A",
                                                        "SeatPosition": "",
                                                        "SeatRef": "1A",
                                                        "SeatReferenceAPI": "",
                                                        "SeatStatus": "true",
                                                        "SeatType": "NS",
                                                        "Seatcharacteristics": null,
                                                        "SegRef": "1",
                                                        "WingSeat": "",
                                                        "XAxis": "1",
                                                        "YAxis": "6"
                                                        }
                                                        ]
                                                        }
                                                        ]
                                                        }
                                                    
7.5.1 Success
Refer to the sample JSON request and response that is attached

7.5.2 Failure
Copy Code
                                                        {
                                                        "FlightSeat": null,
                                                        "ResponseStatus": {
                                                        "Error": "The requested token was timed out.",
                                                        "ResultCode": "0",
                                                        "SequenceID": "85433868698134"
                                                        }
                                                        }
                                                    
7.5.3 Exception
Copy Code
                                                        {
                                                        "FlightSeat": null,
                                                        "ResponseStatus": {
                                                        "Error": "EX-Unable to fetch seat for the requested segments.",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "174533868988134"
                                                        }
                                                        }
                                                    
8 Booking
8.1 Method: Booking
8.2 Description
Booking The booking technique is used to reserve seats, meals, luggage, and other ancillary services for one or more people together with route information (air itinerary), traveller’s information, and contact information for a specific itinerary based on the most recent price quote.

Note: In case of booking with GST need to provide the details in GSTInfo(For more details refer annexure 14.2)

8.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
AdultCount	Integer	Minimum of 1 and Maximum up to 9
ChildCount	Integer	Total no of Adults and child can be maximum 9
InfantCount	Integer	Minimum of 1 and Maximum up to 4. Infant alone not allowed to travel
ItineraryFlightsInfo
Token	String	Pricing reference value
FlightID	String	Pass the same value from Pricing response.
FlightNumber	String	Booking Flight Number.
Origin	String	3 Letter IATA Departure Airport code.
Destination	String	3 Letter IATA Arrival Airport code.
DepartureDateTime	DateTime	Flight Departure Date and Time. [DD MMM YYYY HH:MM]
ArrivalDateTime	DateTime	Flight Arrival Date and Time. [DD MMM YYYY HH:MM]
PaymentMode	String	Mode of Payment T- Agent Deposit
SeatID	String	Pass the same value from Seatmap response.
PaxRefNumber	Integer	Unique passenger reference ID starts with 1
BaggageID	String	Pass the same value from Pricing response.
PaxRefNumber	Integer	Unique passenger reference ID starts with 1
MealID	String	Pass the same value from Pricing response.
PaxRefNumber	Integer	Unique passenger reference ID starts with 1
OtherSSRID	String	Pass the same value from Pricing response.
PaxRefNumber	Integer	Unique passenger reference ID starts with 1
PaxDetailsInfo
PaxRefNumber	Integer	Passenger wise unique serial reference number.
Title	String	Passenger Salutation / Title [Mr, Mrs, Miss, Ms, Mstr and Dr]
FirstName	String	First Name of the booking Passenger
LastName	String	Last Name of the booking Passenger
DOB	Date	Date of Birth of the booking Passenger [DD/MM/YYYY]
Gender	String	Gender identification of the booking Passenger
PaxType	String	Indicates booking passenger type (ADT/CHD/INF)
PassportNo	String	Passport Number of the booking passenger
PassportExpiry	Date	Passport Expiry date of the booking passenger [DD/MM/YYYY]
PassportIssuedDate	Date	Passport Issued date of the booking passenger [DD/MM/YYYY]
PassportCountryCode	String	Passport Issued CountryCode [Eg:IN,US,CA]
InfantRef	String	Indicator to identify in case of travelling with Infant passenger
AddressDetails
CountryCode	String	Dialing country code of the booking passenger
ContactNumber	String	Contact Number of the booking passenger
EmailID	String	Email ID of the booking passenger
GSTInfo
GSTNumber	String	GST Number for the booking
GSTCompanyName	String	GST Company Name for the booking
GSTAddress	String	GST Address for the booking
GSTEmailID	String	GST EmailID for the booking
GSTMobileNumber	String	GST Mobile Number for the booking
TripType	String	Trip Type shows the type of booking. It may be an O-Oneway or R-Roundtrip or Y-Roundtrip Special.
BlockPNR	Boolean	Refer Pricing response “AllowBlockPNR = true” the flight is eligible to Block / Hold the booking. BlockPNR=False: Ticket get issued immediately. BlockPNR=True: Hold the booking.
BaseOrigin	String	3 Letter IATA Departure Airport code.
BaseDestination	String	3 Letter IATA Arrival Airport code.
TrackId	String	Unique reference Id from Pricing response.
8.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXX",
                                                        "UserName": "XXXXXXXXXX",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        },
                                                        "AdultCount": 1,
                                                        "ChildCount": 0,
                                                        "InfantCount": 0,
                                                        "ItineraryFlightsInfo": [
                                                        {
                                                        "Token": "AQAG0D9569010007722",
                                                        "FlightsInfo": [
                                                        {
                                                        "FlightID": "7368",
                                                        "FlightNumber": "6E 292",
                                                        "Origin": "IXB",
                                                        "Destination": "CCU",
                                                        "DepartureDateTime": "14 Nov 2023 14:20",
                                                        "ArrivalDateTime": "14 Nov 2023 15:25"
                                                        },
                                                        {
                                                        "FlightID": "7369",
                                                        "FlightNumber": "6E 2516",
                                                        "Origin": "CCU",
                                                        "Destination": "DEL",
                                                        "DepartureDateTime": "14 Nov 2023 16:50",
                                                        "ArrivalDateTime": "14 Nov 2023 19:25"
                                                        }
                                                        ],
                                                        "PaymentMode": "T",
                                                        "SeatsSSRInfo": [
                                                        {
                                                        "PaxRefNumber": "1",
                                                        "SeatID": "AQ132051322175817861320538751323B63WSHXSZQY|1646"
                                                        }
                                                        ],
                                                        "BaggSSRInfo": [
                                                        {
                                                        "BaggageID": "6941",
                                                        "PaxRefNumber": "1"
                                                        }
                                                        ],
                                                        "MealsSSRInfo": [
                                                        {
                                                        "MealID": "8322",
                                                        "PaxRefNumber": "1"
                                                        }
                                                        ],
                                                        "OtherSSRInfo": [],
                                                        "PaymentInfo": [
                                                        {
                                                        "TotalAmount": "22598"
                                                        }
                                                        ]
                                                        }
                                                        ],
                                                        "PaxDetailsInfo": [
                                                        {
                                                        "PaxRefNumber": "1",
                                                        "Title": "MR",
                                                        "FirstName": "TESTA",
                                                        "LastName": "TEST",
                                                        "DOB": "11/05/1992",
                                                        "Gender": "Male",
                                                        "PaxType": "ADT",
                                                        "PassportNo": "",
                                                        "PassportExpiry": "",
                                                        "PassportIssuedDate": "",
                                                        "InfantRef": ""
                                                        }
                                                        ],
                                                        "AddressDetails": {
                                                        "CountryCode": "91",
                                                        "ContactNumber": "9876543210",
                                                        "EmailID": "test123@gmail.com"
                                                        },
                                                        "GSTInfo": {
                                                        "GSTNumber": "",
                                                        "GSTCompanyName": "",
                                                        "GSTAddress": "",
                                                        "GSTEmailID": "",
                                                        "GSTMobileNumber": ""
                                                        },
                                                        "FFNumberInfo": [
                                                        {
                                                        "SegRefNumber": "1",
                                                        "PaxRefNumber": "1",
                                                        "AirlineCode": "6E",
                                                        "FlyerNumber": "028504394",
                                                        "Itinref": "0"
                                                        }
                                                        ],
                                                        "TripType": "O",
                                                        "BlockPNR": false,
                                                        "BaseOrigin": "IXB",
                                                        "BaseDestination": "DEL",
                                                        "TrackId": "AQ131620651068521731316232989362MDJAYW12CHN"
                                                        }
                                                    
8.5 Response
8.5.1 Success
Refer to the sample JSON request and response that is attached

8.5.2 Pending
Copy Code
                                                        {
                                                        "TrackId": "AQRSNKL040010107415171120221517568383190023565",
                                                        "Bookingresponse": {
                                                        "ItinearyDetails": null
                                                        },
                                                        "Status": {
                                                        "Error": "The booking might be confirmed. Please check customer care.",
                                                        "ResultCode": "2",
                                                        "SequenceID": "15152533966567"
                                                        }
                                                        }
                                                    
8.5.3 Failure
Copy Code
                                                        {
                                                        "TrackId": "AQ1143196379622320221117114324",
                                                        "Bookingresponse": {
                                                        "ItinearyDetails": null
                                                        },
                                                        "Status": {
                                                        "Error": "The requested token was timed out. ",
                                                        "ResultCode": "0",
                                                        "SequenceID": "16295878029252"}
                                                        }
                                                    
8.5.4 Exception
Copy Code
                                                        {
                                                        "TrackId": "AQRSNKL040010107415171120221517568383190023565",
                                                        "Bookingresponse": {
                                                        "ItinearyDetails": null
                                                        },
                                                        "Status": {
                                                        "Error": "EX-Unable to book for the requested segments. ",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "12355533746467"
                                                        }
                                                        }
                                                    
9 Ticketing
9.1 Method: IssueTicket
9.2 Description
This method is to be called to confirm the ticket for already blocked itinerary.

9.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
BookingTrackId	String	Unique reference Id from Booking response.
AirIqPNR	String	Airiq Booking reference number
AirlinePNR	String	Airline Booking reference number
BookingAmount	Decimal	Total Booking Amount
PaymentMode	String	Mode of Payment T- Agent Deposit
9.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXXXX",
                                                        "UserName": "XXXXX",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        },
                                                        "BookingTrackId": "AQRSNKL040010107699181120220906471464990023574",
                                                        "AirIqPNR": "BX18DK0003",
                                                        "AirlinePNR": "UKS1QA",
                                                        "BookingAmount": "11262.00",
                                                        "PaymentMode": "T"
                                                        }
                                                    
9.5 Response
9.5.1 Success
Refer to the sample JSON request and response that is attached

9.5.2 Pending
Copy Code
                                                        {
                                                        "TrackId": "AQRSNKL040010107699181120220906471464990023574",
                                                        "Bookingresponse": {
                                                        "ItinearyDetails": null
                                                        },
                                                        "Status": {
                                                        "Error": "The booking might be confirmed. Please check customer care.",
                                                        "ResultCode": "2",
                                                        "SequenceID": "15155537725467"
                                                        }
                                                        }
                                                    
9.5.3 Failure
Copy Code
                                                        {
                                                        "TrackId": "AQRSNKL040010107699181120220906471464990023574",
                                                        "Bookingresponse":{
                                                        "ItinearyDetails": null
                                                        },
                                                        "Status":{                                                         
                                                        "Error": "The requested token was timed out. ",
                                                        "ResultCode": "0",
                                                        "SequenceID": "38291478098842"}
                                                        }
                                                        }
                                                    
9.5.4 Exception
Copy Code
                                                        {
                                                        "TrackId": "AQRSNKL040010107699181120220906471464990023574",
                                                        "Bookingresponse": {
                                                        "ItinearyDetails": null
                                                        },
                                                        "Status":{
                                                        "Error": "EX-Unable to book for the requested segments. ",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "15155533947484"
                                                        }
                                                        }
                                                    
10 Get Booking
10.1 Method: RetrieveBooking
10.2 Description
This method is to be called to confirm the ticket for already blocked itinerary.

10.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
AiriqPNR	String	Airiq Booking reference number
10.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXXXXXXXXXX",
                                                        "UserName": "XXXXXXXX ",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        },
                                                        "Item": [
                                                        {
                                                        "AirIqPNR": "BX17DK0005"
                                                        }
                                                        ]
                                                        }
                                                    
10.5 Response
10.5.1 Success
Refer to the sample JSON request and response that is attached

10.5.2 Failure
Copy Code
                                                        {
                                                        "Retrieveresponse": null,
                                                        "Status": {
                                                        "Error": "The requested token was timed out.",
                                                        "ResultCode": "0",
                                                        "SequenceID": "18133268418217"
                                                        }
                                                        }
                                                    
10.5.3 Exception
Copy Code
                                                        {
                                                        "Retrieveresponse": null,
                                                        "Status":
                                                        {
                                                        "Error": "EX-Unable to get RetrivePnr for the requested segments.",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "19822143798711"}
                                                        }
                                                    
11 Get Account Balance
11.1 Method: GetBalance
11.2 Description
GetBalance Get Balance - Agency's current balance in their Airiqonline Account can be found using the GetBalance function.

11.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
11.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXXXXXXXX",
                                                        "UserName": "XXXXXXXXXXXXX",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        }
                                                        }
                                                    
11.5 Response
11.5.1 Success
Copy Code
                                                        {
                                                        "Status": {
                                                        "Error": "",
                                                        "ResultCode": "1",
                                                        "SequenceID": "12401475083610"},
                                                        "TopupBalance": "1022.01",
                                                        "CreditBalance": "00.00"
                                                        }
                                                    
11.5.2 Failure
Copy Code
                                                        {
                                                        "Status": {
                                                        "Error": "The requested token was timed out.",
                                                        "ResultCode": "0",
                                                        "SequenceID": "18394703912223"},
                                                        "TopupBalance": null,
                                                        "CreditBalance": null
                                                        }
                                                    
11.5.3 Exception
Copy Code
                                                        {
                                                        "Status": {
                                                        "Error": "EX-Unable to get the balance",
                                                        "ResultCode": "-1",
                                                        "SequenceID": "15394703964453"
                                                        },
                                                        "TopupBalance": null,
                                                        "CreditBalance": null
                                                        }
                                                    
12 Booking Track Status
12.1 Method: TrackStatus
12.2 Description
TrackStatus TrackStatus method is used to check the booking request’s current status.

12.3 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
BookingTrackId	String	Unique reference Id from Booking response.
12.4 Request
Copy Code
                                                        {
                                                        "AgentInfo": {
                                                        "AgentId": "XXXXXXXXXX",
                                                        "UserName": "XXXXXXX",
                                                        "AppType": "API",
                                                        "Version": 2.0
                                                        },
                                                        "Item": [
                                                        {
                                                        "BookingTrackId": "AQRSNKL040010107160171120221050073773810023554"
                                                        }
                                                        ]
                                                        }
                                                    
12.5 Response
Refer to the sample JSON request and response that is attached

13 Cancellation
13.1 Description
Cancellation Status Cancellation Status method is used to check the booking Cancellation current status.

13.2 Data Format and Details
Field Name	Data Type	Description
AgentID	String	Your Agent ID
Username	String	Your Username
AppType	String	Default Value API
Version	String	API version
Flag	String	PENALTY OR CANCEL
AIRIQPNR	String	Your Airiq Pnr
Remarks	String	Your Request Remarks
13.3 Request
Copy Code
                                                            {
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXXXXXXXXX",
                                                            "UserName": "XXXXX",
                                                            "AppType": "API",
                                                            "Version": 2.0
                                                            },
                                                            "OnlineInfo": {
                                                            "Flag": "PENALTY/CANCEL",
                                                            "AiriqPNR": "XXXXXX",
                                                            "Remarks": "Remarks Testt"
                                                            }
                                                            }
                                                        
13.4 Response
Copy Code
                                                            {
                                                            "CancelStatus": "SUCCESS",
                                                            "Remarks": "Your request to Penalty has been processed successfully.",
                                                            "PenalityAmount": "0000",
                                                            "TotalBookingAmount": "0000",
                                                            "Status": {
                                                            "ResultCode": "1",
                                                            "Error": "",
                                                            "SequenceID": "XXXXXXXXXXXXX"
                                                            }
                                                            }
                                                        
13.5 Failure
Copy Code
                                                            {
                                                            "CancelStatus": "Failed",
                                                            "Status": {
                                                            "Error": "Unable to Check penalty or Cancel the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "0",
                                                            "SequenceID": "15001591842768130"
                                                            }
                                                            }
                                                        
13.6 Exception
Copy Code
                                                            {
                                                            "CancelStatus": "PENDING",
                                                            "Status": {
                                                            "Error": "EX-Unable to Check penalty or Cancel the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "-1",
                                                            "SequenceID": "XXXXXXXXXXXXXXX"
                                                            }
                                                            }
                                                        
13.7 Pending
Copy Code
                                                            {
                                                            "CancelStatus": "PENDING",
                                                            "Status": {
                                                            "Error": "Unable to Check penalty or Cancel the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "-2",
                                                            "SequenceID": "XXXXXXXXXXXXXXX"
                                                            }
                                                            }
                                                        
14 Reschedule Avail
14.1 Data Format and Details
Field Name	Data Type	Description
TripType	String	One-way or Round-trip. (O = One-way, R = Round-trip, Y- Roundtrip Special)
AgentInfo.AgentId	String	Your Agent ID
AgentInfo.TerminalId	String	Your Terminal ID
AgentInfo.UserName	String	Your Username
AgentInfo.AppType	String	Default Value: API
AgentInfo.Version	String	API version
AvailInfo DepartureStation	String	Departure airport code (e.g., BOM)
AvailInfo ArrivalStation	String	Arrival airport code (e.g., DEL)
AvailInfo FlightDate	String	Flight date in YYYYMMDD format
Airiq PNR	String	Your Airiq PNR
Remarks	String	Remarks for the request
14.2 Reschedule Avail Request
Copy Code
                                                            {
                                                            "TripType": "O",
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXXXXXXXX",
                                                            "UserName": "dhanaa",
                                                            "AppType": "API",
                                                            "Version": 2.0
                                                            },
                                                            "AvailInfo": [
                                                            {
                                                            "DepartureStation": "XXX",
                                                            "ArrivalStation": "XXX",
                                                            "FlightDate": "20250810"
                                                            }
                                                            ],
                                                            "AiriqPNR": "XXXXXXXXXXXX",
                                                            "Remarks": "Test"
                                                            }
​
                                                        
14.3 Reschedule Avail Response
Copy Code
                                                            {
                                                            "Trackid": "AQ1529473540502431215295031386525F6RGWLZIXC",
                                                            "ItineraryFlightList": [
                                                            {
                                                            "Items": [
                                                            {
                                                            "FlightDetails": [
                                                            {
                                                            "FlightID": "4752",
                                                            "AirlineDescription": "6E",
                                                            "FlightNumber": "6E 853",
                                                            "Origin": "DEL",
                                                            "Destination": "BOM",
                                                            "DepartureTerminal": "1",
                                                            "ArrivalTerminal": "2",
                                                            "DepartureDateTime": "20 Jul 2025 01:55",
                                                            "ArrivalDateTime": "20 Jul 2025 04:15",
                                                            "Class": "R",
                                                            "JourneyTime": "-140",
                                                            "ReferenceToken": "4W5CapdTFjWeELsv4gHcF0jmYti8d50a7YdeI9xYTqe8JoJ8OMh9s96ZUdNA96a7I0ohIa4ObRtMv+tlf1Xw1ynmVWW0AIBrPgtS2GRVBC6Ua+SnDauKWxul8T1KUz7wnBZZFHW/PKy4OWlgO8vwvg==",
                                                            "SegRef": "1",
                                                            "ItinRef": "0",
                                                            "ConnectionFlag": "N",
                                                            "FareId": "6E0",
                                                            "Cabin": "E",
                                                            "FareBasisCode": "AA07",
                                                            "Stops": "0",
                                                            "Via": "",
                                                            "AirlineCategory": "LCC",
                                                            "CNX": "N",
                                                            "PlatingCarrier": "6E",
                                                            "OperatingCarrier": "6E",
                                                            "SegmentDetails": "Aircraft Type : 321\r\nJourney Time : -140\r\nStart Terminal : 1\r\nEndTerminal : 2\r\nBaggage : 15kg",
                                                            "FlyingTime": "-140",
                                                            "OfflineIndicator": false,
                                                            "MultiClass": "0",
                                                            "AllowFQT": false,
                                                            "AvailSeat": "30",
                                                            "PromoCode": "",
                                                            "PromoCodeDesc": "",
                                                            "FareTypeDescription": "N",
                                                            "FareDescription": "Normal",
                                                            "FareRuleInfo": "",
                                                            "Refundable": "True",
                                                            "Baggage": "15kg"
                                                            }
                                                            ],
                                                            "Fares": [
                                                            {
                                                            "Currency": "INR",
                                                            "FareType": "N",
                                                            "Faredescription": [
                                                            {
                                                            "Paxtype": "ADT",
                                                            "BaseAmount": "1250",
                                                            "TotalTaxAmount": "691",
                                                            "GrossAmount": "1941",
                                                            "NetAmount": "1902.18",
                                                            "Commission": "0.00",
                                                            "Incentive": "0.00",
                                                            "Servicecharge": "38.82",
                                                            "TDS": "0.00",
                                                            "Discount": "0.00",
                                                            "PLBAmount": "0.00",
                                                            "SF": "0.00",
                                                            "SFGST": "0.00",
                                                            "Taxes": [
                                                            {
                                                            "Amount": "0.00",
                                                            "Code": "CSC"
                                                            },
                                                            {
                                                            "Amount": "691",
                                                            "Code": "TAX"
                                                            }
                                                            ]
                                                            }
                                                            ],
                                                            "FlightId": "6E0"
                                                            }
                                                            ]
                                                            }
​
                                                            ]
                                                            }
                                                            ],
                                                            "Status": {
                                                            "Error": "",
                                                            "ResultCode": "1",
                                                            "SequenceID": "15294735405024312"
                                                            }
                                                            }
                                                        
14.4 Reschedule Avail Failure
Copy Code
                                                            {
                                                            "Trackid": null,
                                                            "ItineraryFlightList": null,
                                                            "Status": {
                                                            "Error": "Unable to get avail flight details for the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "0",
                                                            "SequenceID": "15045887738540218"
                                                            }
                                                            }
​
​
                                                        
14.5 Reschedule Avail Exception
Copy Code
                                                            {
                                                            "Trackid": null,
                                                            "ItineraryFlightList": null,
                                                            "Status": {
                                                            "Error": "EX-Unable to get avail flight details for the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "-1",
                                                            "SequenceID": "15045887738540218"
                                                            }
                                                            }
                                                        
14.6 Reschedule Avail Pending
Copy Code
                                                            {
                                                            "Trackid": null,
                                                            "ItineraryFlightList": null,
                                                            "Status": {
                                                            "Error": "Unable to get avail flight details for the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "-2",
                                                            "SequenceID": "15045887738540218"
                                                            }
                                                            }
                                                        
14.7 Data Format and Details
Field Name	Data Type	Description
AgentInfo.AgentId	String	Your Agent ID
AgentInfo.TerminalId	String	Your Terminal ID
AgentInfo.UserName	String	Your Username
AgentInfo.AppType	String	Default value: API
AgentInfo.Version	String	API version
SegmentInfo.BaseOrigin	String	Departure station code (e.g., BOM)
SegmentInfo.BaseDestination	String	Arrival station code (e.g., DEL)
SegmentInfo.TripType	String	Trip type (e.g., O = One-way)
Trackid	String	Tracking ID for the request
AiriqPNR	String	Your Airiq PNR
Remarks	String	Remarks for the request
Flag	String	Action flag (e.g., CHECKFARE/CONFIRM)
ContactNo	String	User's contact number
ItineraryInfo FlightDetails FlightID	String	Unique ID of the flight
ItineraryInfo FlightDetails FlightNumber	String	Flight number (e.g., 6E 853)
ItineraryInfo FlightDetails Origin	String	Flight origin station
ItineraryInfo FlightDetails Destination	String	Flight destination station
ItineraryInfo FlightDetails DepartureDateTime	String	Departure date and time (e.g., 27 Feb 2024 02:00)
ItineraryInfo FlightDetails ArrivalDateTime	String	Arrival date and time (e.g., 27 Feb 2024 04:20)
ItineraryInfo BaseAmount	String	Base fare of the itinerary
ItineraryInfo GrossAmount	String	Total amount including taxes
14.8 Reschedule Request
Copy Code
                                                            {
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXXXXXX",
                                                            "TerminalId": "XXXXXXXXXX",
                                                            "UserName": "XXXXXXXXXX",
                                                            "AppType": "API",
                                                            "Version": 2.0
                                                            },
                                                            "SegmentInfo": {
                                                            "BaseOrigin": "XXX",
                                                            "BaseDestination": "XXX",
                                                            "TripType": "O"
                                                            },
                                                            "Trackid": "XXXXXXXXXXXXXXXXXXXX",
                                                            "AiriqPNR": "XXXXXXXXXX",
                                                            "Remarks": "XXXXXXXXXX",
                                                            "Flag": "CONFIRM",
                                                            "ContactNo": "XXXXXXXXXX",
                                                            "ItineraryInfo": [
                                                            {
                                                            "FlightDetails": [
                                                            {
                                                            "FlightID": "XXX",
                                                            "FlightNumber": "XXX",
                                                            "Origin": "XXXXXXXXX",
                                                            "Destination": "XXX",
                                                            "DepartureDateTime": "27 Feb 2024 02:00",
                                                            "ArrivalDateTime": "27 Feb 2024 04:20"
                                                            }
                                                            ],
                                                            "BaseAmount": "XXXXXXXXX",
                                                            "GrossAmount": "XXXXXXXXX"
                                                            }
                                                            ]
                                                            }
                                                        
14.9 Reschedule Response
Copy Code
                                                            {
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXXXXX",
                                                            "TerminalId": "XXXXXXXXX",
                                                            "UserName": "XXX",
                                                            "AppType": "API",
                                                            "Version": 2.0
                                                            },
                                                            "SegmentInfo": {
                                                            "BaseOrigin": "XXX",
                                                            "BaseDestination": "XXX",
                                                            "TripType": "O"
                                                            },
                                                            "Trackid": "XXXXXXXXX",
                                                            "AiriqPNR": "BT27GF0027",
                                                            "Remarks": "XXX",
                                                            "Flag": "CONFIRM",
                                                            "ContactNo": "XXXXXXXXX",
                                                            "ItineraryInfo": [
                                                            {
                                                            "FlightDetails": [
                                                            {
                                                            "FlightID": "XXXXXXXXX",
                                                            "FlightNumber": "6E 853",
                                                            "Origin": "XXX",
                                                            "Destination": "XXX",
                                                            "DepartureDateTime": "27 Feb 2024 02:00",
                                                            "ArrivalDateTime": "27 Feb 2024 04:20"
                                                            }
                                                            ],
                                                            "BaseAmount": "XXXXXXXXX",
                                                            "GrossAmount": "XXXXXXXXX"
                                                            }
                                                            ]
                                                            }
                                                        
14.10 Reschedule Failure
Copy Code
                                                            {
                                                            "Status": {
                                                            "Error": "Unable to Reschedule for the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "0",
                                                            "SequenceID": "15060631274218514"
                                                            }
                                                            }
                                                        
14.11 Reschedule Exception
Copy Code
                                                            {
                                                            "Status": {
                                                            "Error": "EX-Unable to Reschedule for the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "-1",
                                                            "SequenceID": "15060631274218514"
                                                            }
                                                            }
                                                        
14.11 Reschedule Exception
Copy Code
                                                            {
                                                            "Status": {
                                                            "Error": "Unable to Reschedule for the requested PNR. Kindly contact customer care.",
                                                            "ResultCode": "-2",
                                                            "SequenceID": "15060631274218514"
                                                            }
                                                            }
                                                        
15 PostAncillary Avail
15.1 Data Format and Details
Field Name	Data Type	Description
AgentInfo.AgentId	String	Your Agent ID
AgentInfo.UserName	String	Your Username
AgentInfo.AppType	String	Default Value: API
AgentInfo.Version	String	API version
Airiq PNR	String	Your Airiq PNR
Airline PNR	String	Your Airline PNR
15.2 Get Ssr Request
Copy Code
                                                            {
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXXXX",
                                                            "UserName": "XXXXXXXXXXX",
                                                            "AppType": "API",
                                                            "Version": "XXX"
                                                            },
                                                            "AirIqPNR": "AF23HC0015",
                                                            "AirlinePNR" :"BEK4PX"
                                                            }
                                                        
15.3 Get Ssr Responces
Copy Code
                                                            {
                                                            "TrackId": "AQ143613790123208541436182601064CGDVYIH6EK0",
                                                            "SsrDetails": {
                                                            "Baggages": [
                                                            {
                                                            "Amount": "4500",
                                                            "Code": "ExcessBaggage 10KG|EB10",
                                                            "Description": "ExcessBaggage 10KG",
                                                            "Destination": "DEL",
                                                            "Id": "9735",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "0"
                                                            },
                                                            {
                                                            "Amount": "2250",
                                                            "Code": "ExcessBaggage 05KG|EB05",
                                                            "Description": "ExcessBaggage 05KG",
                                                            "Destination": "DEL",
                                                            "Id": "9736",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "0"
                                                            }
                                                            ],
                                                            "Meals": [
                                                            {
                                                            "Amount": "300",
                                                            "Code": "Vegetables in Red Thai Curry with Steamed Rice|VCC2",
                                                            "Description": "Vegetables in Red Thai Curry with Steamed Rice",
                                                            "Destination": "DEL",
                                                            "Id": "6785",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1"
                                                            },
                                                            {
                                                            "Amount": "300",
                                                            "Code": "Chicken in Red Thai Curry with Steamed Rice|NCC2",
                                                            "Description": "Chicken in Red Thai Curry with Steamed Rice",
                                                            "Destination": "DEL",
                                                            "Id": "6786",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1"
                                                            },
                                                            {
                                                            "Amount": "300",
                                                            "Code": "Grilled Chicken Breast with Mushroom Sauce, Yellow Rice, SautÃ© Carrot and Beans Baton|NCC1",
                                                            "Description": "Grilled Chicken Breast with Mushroom Sauce, Yellow Rice, SautÃ© Carrot and Beans Baton",
                                                            "Destination": "DEL",
                                                            "Id": "6787",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1"
                                                            },
                                                            {
                                                            "Amount": "0",
                                                            "Code": "Kids Meal|CHML",
                                                            "Description": "Kids Meal",
                                                            "Destination": "DEL",
                                                            "Id": "6788",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1"
                                                            }
                                                            ],
                                                            "OtherSSR": [
                                                            {
                                                            "Amount": "59",
                                                            "Code": "Pre-book SpiceAssurance|SASR",
                                                            "Description": "Pre-book SpiceAssurance",
                                                            "Destination": "DEL",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1",
                                                            "category": "ASSURANCE",
                                                            "id": "2142"
                                                            },
                                                            {
                                                            "Amount": "300",
                                                            "Code": "Priority check-in|PRCP",
                                                            "Description": "Priority check-in",
                                                            "Destination": "DEL",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1",
                                                            "category": "PRIORITY_CHECK_IN",
                                                            "id": "2143"
                                                            },
                                                            {
                                                            "Amount": "149",
                                                            "Code": "Priority check-in + Bag out first|PCBF",
                                                            "Description": "Priority check-in + Bag out first",
                                                            "Destination": "DEL",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1",
                                                            "category": "BAGOUT+PRIORITY_CHECK_IN",
                                                            "id": "2144"
                                                            },
                                                            {
                                                            "Amount": "550",
                                                            "Code": "Carry More On board|EXCB",
                                                            "Description": "Carry More On board",
                                                            "Destination": "DEL",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1",
                                                            "category": "BAGGAGE",
                                                            "id": "2145"
                                                            },
                                                            {
                                                            "Amount": "300",
                                                            "Code": "Bag out first  with 3 bags|BOF3",
                                                            "Description": "Bag out first  with 3 bags",
                                                            "Destination": "DEL",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1",
                                                            "category": "BAGOUT",
                                                            "id": "2146"
                                                            },
                                                            {
                                                            "Amount": "200",
                                                            "Code": "Bag out first  with 2 bags|BOF2",
                                                            "Description": "Bag out first  with 2 bags",
                                                            "Destination": "DEL",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1",
                                                            "category": "BAGOUT",
                                                            "id": "2147"
                                                            },
                                                            {
                                                            "Amount": "100",
                                                            "Code": "Bag out first  with 1 bag|BOF1",
                                                            "Description": "Bag out first  with 1 bag",
                                                            "Destination": "DEL",
                                                            "ItinRef": "0",
                                                            "Orgin": "BOM",
                                                            "SegRef": "1",
                                                            "category": "BAGOUT",
                                                            "id": "2148"
                                                            }
                                                            ],
                                                            "Seats": [
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6457",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "1",
                                                            "SeatName": "1A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "5"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6458",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "1",
                                                            "SeatName": "1B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "5"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6459",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "1",
                                                            "SeatName": "1C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "5"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6460",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "1",
                                                            "SeatName": "1D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "5"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6461",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "1",
                                                            "SeatName": "1E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "5"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6462",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "1",
                                                            "SeatName": "1F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "5"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6463",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "2A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "8"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6464",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "2B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "8"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6465",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "2C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "8"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6466",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "2D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "8"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6467",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "2E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "8"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6468",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "2F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "8"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6469",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "3A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "11"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6470",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "3B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "11"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6471",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "3C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "11"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6472",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "3D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "11"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6473",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "3E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "11"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6474",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "3F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "11"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6475",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "4A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "14"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6476",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "4B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "14"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6477",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "4C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "14"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6478",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "4D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "14"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6479",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "4E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "14"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6480",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "4",
                                                            "SeatName": "4F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "14"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6481",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "5D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "16"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6482",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "5E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "16"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6483",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "5F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "16"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6484",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "6A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "18"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6485",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "6B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "18"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6486",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "6C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "18"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6487",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "6D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "18"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6488",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "6E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "18"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6489",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "6F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "18"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6490",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "7A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "20"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6491",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "7B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "20"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6492",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "7C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "20"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6493",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Closed",
                                                            "SeatGroup": "3",
                                                            "SeatName": "7D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "20"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6494",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "7E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "20"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6495",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "7F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "20"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6496",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "8A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "22"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6497",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "8B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "22"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6498",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "8C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "22"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6499",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "8D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "22"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6500",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "8E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "22"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6501",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "8F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "22"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6502",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "9A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "24"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6503",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "9B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "24"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6504",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "9C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "24"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6505",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "9D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "24"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6506",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "9E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "24"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6507",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "9F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "24"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6508",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "10A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "26"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6509",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "10B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "26"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6510",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "10C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "26"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6511",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "10D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "26"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6512",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "10E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "26"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6513",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "10F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "26"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6514",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "11A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "28"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6515",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "11B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "28"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6516",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "11C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "28"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6517",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "11D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "28"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6518",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "11E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "28"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6519",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "11F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "28"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6520",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "12A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "30"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6521",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "12B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "30"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6522",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "12C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "30"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6523",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "12D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "30"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6524",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "12E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "30"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6525",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "12F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "30"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6526",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "13A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "32"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6527",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "13B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "32"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6528",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "13C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "32"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6529",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "13D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "32"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6530",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "6",
                                                            "SeatName": "13E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "32"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6531",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "300",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "3",
                                                            "SeatName": "13F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "32"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6532",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "19",
                                                            "SeatName": "14A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "34"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6533",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "20",
                                                            "SeatName": "14B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "34"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6534",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "19",
                                                            "SeatName": "14C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "34"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6535",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "19",
                                                            "SeatName": "14D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "34"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6536",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "99",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "20",
                                                            "SeatName": "14E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "34"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6537",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "19",
                                                            "SeatName": "14F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "34"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6538",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "5",
                                                            "SeatName": "15A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "37"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6539",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "5",
                                                            "SeatName": "15B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "37"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6540",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "5",
                                                            "SeatName": "15C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "37"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6541",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "5",
                                                            "SeatName": "15D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "37"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6542",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "5",
                                                            "SeatName": "15E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "37"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6543",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "5",
                                                            "SeatName": "15F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "37"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6544",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "9",
                                                            "SeatName": "16A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "40"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6545",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "9",
                                                            "SeatName": "16B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "40"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6546",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "9",
                                                            "SeatName": "16C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "40"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6547",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "9",
                                                            "SeatName": "16D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "40"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6548",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "9",
                                                            "SeatName": "16E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "40"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6549",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "799",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "9",
                                                            "SeatName": "16F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "40"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6550",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "17A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "42"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6551",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "17B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "42"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6552",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "17C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "42"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6553",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "17D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "42"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6554",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "17E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "42"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6555",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "17F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "42"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6556",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "18A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "44"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6557",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "18B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "44"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6558",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "18C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "44"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6559",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "18D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "44"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6560",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "18E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "44"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6561",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "18F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "44"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6562",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "19A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "46"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6563",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "19B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "46"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6564",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "19C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "46"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6565",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "19D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "46"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6566",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "19E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "46"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6567",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "19F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "46"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6568",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "20A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "48"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6569",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "20B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "48"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6570",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "20C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "48"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6571",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "20D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "48"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6572",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "20E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "48"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6573",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "20F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "48"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6574",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "21A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "50"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6575",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "21B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "50"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6576",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "21C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "50"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6577",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "21D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "50"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6578",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "21E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "50"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6579",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "21F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "50"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6580",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "22A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "52"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6581",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "22B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "52"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6582",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "22C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "52"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6583",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "22D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "52"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6584",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "22E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "52"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6585",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "22F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "52"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6586",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "23A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "54"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6587",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "23B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "54"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6588",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "23C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "54"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6589",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "23D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "54"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6590",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "23E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "54"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6591",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "23F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "54"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6592",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "24A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "56"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6593",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "24B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "56"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6594",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "24C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "56"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6595",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "24D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "56"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6596",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "24E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "56"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6597",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "24F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "56"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6598",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "25A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "58"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6599",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "25B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "58"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6600",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "25C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "58"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6601",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "25D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "58"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6602",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "25E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "58"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6603",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "25F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "58"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6604",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "26A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "60"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6605",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "26B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "60"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6606",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "26C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "60"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6607",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "26D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "60"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6608",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "49",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "15",
                                                            "SeatName": "26E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "60"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6609",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "26F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "60"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6610",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "27A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "62"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6611",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "27B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "62"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6612",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "27C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "62"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6613",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "27D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "62"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6614",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "27E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "62"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6615",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "27F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "62"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6616",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "28A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "64"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6617",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "28B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "64"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6618",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "28C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "64"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6619",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "28D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "64"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6620",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "28E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "64"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6621",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "28F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "64"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6622",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "29A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "66"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6623",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "29B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "66"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6624",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "29C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "66"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6625",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "29D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "66"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6626",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "29E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "66"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6627",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "29F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "66"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6628",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "30A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "68"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6629",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "30B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "68"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6630",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "30C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "68"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6631",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "30D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "68"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6632",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "30E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "68"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6633",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "30F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "68"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6634",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "31A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "70"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6635",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "31B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "70"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6636",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "31C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "70"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6637",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "31D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "70"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6638",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "8",
                                                            "SeatName": "31E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "70"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6639",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Open",
                                                            "SeatGroup": "7",
                                                            "SeatName": "31F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "70"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6640",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Closed",
                                                            "SeatGroup": "7",
                                                            "SeatName": "32A",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "1",
                                                            "YAxis": "72"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6641",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Closed",
                                                            "SeatGroup": "8",
                                                            "SeatName": "32B",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "3",
                                                            "YAxis": "72"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6642",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Closed",
                                                            "SeatGroup": "7",
                                                            "SeatName": "32C",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "5",
                                                            "YAxis": "72"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6643",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Closed",
                                                            "SeatGroup": "7",
                                                            "SeatName": "32D",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "9",
                                                            "YAxis": "72"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6644",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "0",
                                                            "SeatAvailability": "Closed",
                                                            "SeatGroup": "8",
                                                            "SeatName": "32E",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "11",
                                                            "YAxis": "72"
                                                            },
                                                            {
                                                            "Destination": "DEL",
                                                            "EXITROW": "",
                                                            "Id": "6645",
                                                            "InfantRow": null,
                                                            "ItinRef": "0",
                                                            "MaxHeight": "16",
                                                            "MaxWidth": "78",
                                                            "Origin": "BOM",
                                                            "SeatAmount": "250",
                                                            "SeatAvailability": "Closed",
                                                            "SeatGroup": "7",
                                                            "SeatName": "32F",
                                                            "SeatStatus": true,
                                                            "SeatType": "NS",
                                                            "SegRef": "1",
                                                            "XAxis": "13",
                                                            "YAxis": "72"
                                                            }
                                                            ]
                                                            },
                                                            "Status": {
                                                            "Error": "",
                                                            "ResultCode": "1",
                                                            "SequenceID": "14361379012320854"
                                                            }
                                                            }
                                                        
15.4 Get Ssr Failure
Copy Code
                                                            {
                                                            "Status": {
                                                            "ResultCode": "0",
                                                            "Error": "Unable to process your SSR request. Kindly reach out to customer support.",
                                                            "SequenceID": "15021663533508147"
                                                            }
                                                            }
                                                        
15.6 Data Format and Details
Field Name	Data Type	Description
AgentInfo.AgentId	String	Your Agent ID
AgentInfo.UserName	String	Your Username
AgentInfo.AppType	String	Default Value: API
AgentInfo.Version	String	API version
Trackid	String	Tracking ID for the request
Airiq PNR	String	Your Airiq PNR
Airline PNR	String	Your Airline PNR
MealsSSR	String	Pass the same value from GetSSR response.
PaxRefNumber	Integer	Unique passenger reference ID starts with 1
BaggageID	String	Pass the same value from GetSSR response.
OtherSSRID	String	Pass the same value from GetSSR response.
SeatID	String	Pass the same value from GetSSR response.
SegmentNo	String	Pass the same value from GetSSR response.
PaymentMode	String	Mode of Payment T- Agent Deposit
Remarks	String	Remarks for the request
15.7 Add Ssr Request
Copy Code
                                                            {
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXX",
                                                            "UserName": "XXXXXXXXX",
                                                            "AppType": "API",
                                                            "Version": "XXX"
                                                            },
                                                            "Remarks": "Testtt",
                                                            "TracKID": "AQ143613790123208541436182601064CGDVYIH6EK0",
                                                            "AirIqPNR": "AF23HC0015",
                                                            "AirlinePNR": "BEK4PX",
                                                            "MealsSSR": [
                                                            {
                                                            "PaxRefId": "1",
                                                            "SegmentNo": "1",
                                                            "MealId": "6785"
                                                            }
                                                            ],
                                                            "BaggSSR": [
                                                            {
                                                            "PaxRefId": "1",
                                                            "BaggId": "9735"
                                                            }
                                                            ],
                                                            "SeatsSSR": [
                                                            {
                                                            "PaxRefId": "1",
                                                            "SeatId": "6600"
                                                            }
                                                            ],
                                                            "OtherSSR": [
                                                            {
                                                            "OtherSSRId": "2142",
                                                            "PaxRefId": "1"
                                                            }
                                                            ],
                                                            "Payment": [
                                                            {
                                                            "PaymentMode": "T",
                                                            "Amount": "5109"
                                                            }
                                                            ]
                                                            }
                                                        
15.8 Add Ssr Responces
Copy Code
                                                            {
                                                            "Retrieveresponse": {
                                                            "ItinearyDetails": [
                                                            {
                                                            "AdultCount": "1",
                                                            "ChildCount": "0",
                                                            "InfantCount": "0",
                                                            "IssuedDate": "23/08/2025 14:35:53",
                                                            "Item": [
                                                            {
                                                            "TicketStatus": "CONFIRMED",
                                                            "Resultcode": "1",
                                                            "BookingTrackId": "AQAG0D956901185230820251335517786980020899",
                                                            "AirIqPNR": "AF23HC0015",
                                                            "CRSPNR": "N/A",
                                                            "BaseOrigin": "BOM",
                                                            "BaseDestination": "DEL",
                                                            "GST_Number": "",
                                                            "TicketingTimeLimit": "",
                                                            "PromoCode": "",
                                                            "Class": "P1",
                                                            "PrintTicket": "",
                                                            "SegmentType": "D",
                                                            "Special": "N",
                                                            "Stock": "SG",
                                                            "TripType": "O",
                                                            "PaymentDetails": {
                                                            "Item": [
                                                            {
                                                            "Amount": "8439.00",
                                                            "CurrencyCode": "INR"
                                                            }
                                                            ]
                                                            },
                                                            "TourCode": "",
                                                            "TravellerInfo": {
                                                            "Item": [
                                                            {
                                                            "Title": "MR",
                                                            "FirstName": "SARATHY",
                                                            "LastName": "PRIYANN",
                                                            "DateOfBirth": "17/12/1998",
                                                            "PaxType": "Adult",
                                                            "TicketNumber": "AF23HC00151-1",
                                                            "SegmentInformation": {
                                                            "Item": [
                                                            {
                                                            "ArrTerminal": null,
                                                            "DepTerminal": null,
                                                            "FareTypeDescription": null,
                                                            "PlatingCarrier": null,
                                                            "AirlinePNR": "BEK4PX",
                                                            "TicketNo": "AF23HC00151-1",
                                                            "FlightNumber": "252",
                                                            "Origin": "BOM",
                                                            "Destination": "DEL",
                                                            "DepartureDateTime": "23/09/2025 06:25",
                                                            "ArrivalDateTime": "23/09/2025 08:45",
                                                            "AirCraftType": "",
                                                            "CarrierCode": "SG",
                                                            "ClassCode": "P1",
                                                            "FareBasis": "P1SALE",
                                                            "FrequentFlyerNumber": "",
                                                            "SpRequest": "",
                                                            "MealsPreference": "VCC2",
                                                            "MealsAmount": "300.00",
                                                            "BaggagePreference": "15KG10KG ",
                                                            "BaggageAmount": "4500.00",
                                                            "SeatPreference": "25C",
                                                            "SeatAmount": "250.00"
                                                            }
                                                            ],
                                                            "MonetaryDetail": {
                                                            "BasicAmount": "1999.00",
                                                            "BasicCurrencyCode": "INR",
                                                            "CurrencyCode": "INR",
                                                            "GrossAmount": "8439.00",
                                                            "PLBAmount": "0.00",
                                                            "ServiceTax": "ServiceTax",
                                                            "ServiceTaxAmount": "0.00",
                                                            "TaxDetails": {
                                                            "item": [
                                                            {
                                                            "Amount": "76.00",
                                                            "CurrencyCode": "INR",
                                                            "TaxCode": "CGST27"
                                                            },
                                                            {
                                                            "Amount": "76.00",
                                                            "CurrencyCode": "INR",
                                                            "TaxCode": "SGST27"
                                                            },
                                                            {
                                                            "Amount": "66.00",
                                                            "CurrencyCode": "INR",
                                                            "TaxCode": "AAT"
                                                            },
                                                            {
                                                            "Amount": "80.00",
                                                            "CurrencyCode": "INR",
                                                            "TaxCode": "TRF"
                                                            },
                                                            {
                                                            "Amount": "142.00",
                                                            "CurrencyCode": "INR",
                                                            "TaxCode": "DF1"
                                                            },
                                                            {
                                                            "Amount": "900.00",
                                                            "CurrencyCode": "INR",
                                                            "TaxCode": "YQ"
                                                            },
                                                            {
                                                            "Amount": "50.00",
                                                            "CurrencyCode": "INR",
                                                            "TaxCode": "RCS"
                                                            }
                                                            ]
                                                            },
                                                            "TransactionFee": "TransactionFee",
                                                            "TransactionFeeAmount": "0.00"
                                                            }
                                                            }
                                                            }
                                                            ]
                                                            }
                                                            }
                                                            ],
                                                            "OtherCharges": "0.00",
                                                            "SegmentType": "D",
                                                            "TerminalContactDetails": {
                                                            "Address1": "chennai",
                                                            "Address2": "",
                                                            "City": "MAA",
                                                            "Country": "CX",
                                                            "Email": "sakthivelapi@gmail.com",
                                                            "Phone": "8855425745",
                                                            "State": "",
                                                            "TerminalName": "API Agent Testing"
                                                            },
                                                            "TotalAmount": "8439.00",
                                                            "TotalSegments": "1",
                                                            "TripType": "O"
                                                            }
                                                            ]
                                                            },
                                                            "Status": {
                                                            "Error": "",
                                                            "ResultCode": "1",
                                                            "SequenceID": "14371202877260315"
                                                            }
                                                            }
                                                        
15.9 Add Ssr Failure
Copy Code
                                                            {
                                                            "Status": {
                                                            "ResultCode": "0",
                                                            "Error": "Unable to process your SSR request. Kindly reach out to customer support.",
                                                            "SequenceID": "15021663533508147"
                                                            }
                                                            }
                                                        
16 Hold Cancel Avail
16.1 Data Format and Details
Field Name	Data Type	Description
AgentInfo.AgentId	String	Your Agent ID
AgentInfo.UserName	String	Your Username
AgentInfo.AppType	String	Default Value: API
AgentInfo.Version	String	API version
Airiq PNR	String	Your Airiq PNR
Airline PNR	String	Your Airline PNR
16.2 Hold Cancel Request
Copy Code
                                                            {
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXXXX",
                                                            "UserName": "XXXXXXXXXXX",
                                                            "AppType": "API",
                                                            "Version": "XXX"
                                                            },
                                                            "AirIqPNR": "AFXXXXX",
                                                            "AirlinePNR" :"XXXXXX"
                                                            }
                                                        
16.3 Hold Cancel Responces
Copy Code
                                                            {
                                                            "CancelStatus": "SUCCESS",
                                                            "Remarks": "Your request to Cancel PNR has been processed successfully.",
                                                            "Status": {
                                                            "ResultCode": "1",
                                                            "Error": "",
                                                            "SequenceID": "12480132846525607"
                                                            }
                                                            }
                                                        
16.4 Hold Cancel Failure
Copy Code
                                                            {
                                                            "CancelStatus": "PENDING",
                                                            "Remarks": "Unable to Cancel the requested PNR. Kindly contact customer care.",
                                                            "Status": {
                                                            "ResultCode": "0",
                                                            "Error": "",
                                                            "SequenceID": "12345653487324561"
                                                            }
                                                            }
                                                        
17 GetMultiClass
17.1 Data Format and Details
Field Name	Data Type	Description
AgentInfo.AgentId	String	Your Agent ID
AgentInfo.UserName	String	Your Username
AgentInfo.AppType	String	Default Value: API
AgentInfo.Version	String	API version
FlightID	String	Pass the same value from Availability response.
AdultCount	Integer	Minimum of 1 and Maximum up to 9
ChildCount	Integer	Total no of Adults and child can be maximum 9
InfantCount	Integer	Minimum of 1 and Maximum up to 4. Infant alone not allowed to travel
TripType	String	Trip Type shows the type of booking. It may be an O-Oneway or R-Roundtrip or Y-Roundtrip Special.
TrackId	String	Unique reference Id from Avail response.
17.2 GetMultiClass Request
Copy Code
                                                            {
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXXXX",
                                                            "UserName": "XXXXXXXXXXX",
                                                            "AppType": "API",
                                                            "Version": "XXX"
                                                            },
                                                            "FlightsInfo": [
                                                            {
                                                            "FlightID": "9603"
                                                            }
                                                            ],
                                                            "PassengersInfo": {
                                                            "AdultCount": 1,
                                                            "ChildCount": 0,
                                                            "InfantCount": 0
                                                            },
                                                            "TripType": "O",
                                                            "Trackid": "AQ144316163728603151443236663904RSCN5INQMIX"
                                                            }
                                                        
17.3 GetMultiClass Responces
Copy Code
                                                            {
                                                            "AvailDetails": [
                                                            {
                                                            "Origin": "BOM",
                                                            "Destination": "DEL",
                                                            "CarrierCode": "AI",
                                                            "FlightNumber": "AI 2986",
                                                            "Classes": [
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "P",
                                                            "FareBasisCode": "P",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "U",
                                                            "FareBasisCode": "U",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "L",
                                                            "FareBasisCode": "L",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "G",
                                                            "FareBasisCode": "G",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "W",
                                                            "FareBasisCode": "W",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "V",
                                                            "FareBasisCode": "V",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "Q",
                                                            "FareBasisCode": "Q",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "K",
                                                            "FareBasisCode": "K",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "H",
                                                            "FareBasisCode": "H",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "M",
                                                            "FareBasisCode": "M",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "B",
                                                            "FareBasisCode": "B",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "Economy",
                                                            "Class": "Y",
                                                            "FareBasisCode": "Y",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "PremiumEconomy",
                                                            "Class": "A",
                                                            "FareBasisCode": "A",
                                                            "Seats": "9"
                                                            },
                                                            {
                                                            "Cabin": "PremiumEconomy",
                                                            "Class": "R",
                                                            "FareBasisCode": "R",
                                                            "Seats": "9"
                                                            }
                                                            ]
                                                            }
                                                            ],
                                                            "Status": {
                                                            "Error": "",
                                                            "ResultCode": "1",
                                                            "SequenceID": "14440165448615750"
                                                            }
                                                            }
                                                        
17.4 GetMultiClass Failure
Copy Code
                                                            {
                                                            "AvailDetails": null,
                                                            "Status": {
                                                            "Error": "The requested token was timed out.",
                                                            "ResultCode": "0",
                                                            "SequenceID": "18331532068625135"
                                                            }
                                                            }
                                                        
18 GetMultiClassFare
18.1 Data Format and Details
Field Name	Data Type	Description
AgentInfo.AgentId	String	Your Agent ID
AgentInfo.UserName	String	Your Username
AgentInfo.AppType	String	Default Value: API
AgentInfo.Version	String	API version
FlightID	String	Pass the same value from Availability response.
AdultCount	Integer	Minimum of 1 and Maximum up to 9
ChildCount	Integer	Total no of Adults and child can be maximum 9
InfantCount	Integer	Minimum of 1 and Maximum up to 4. Infant alone not allowed to travel
TripType	String	Trip Type shows the type of booking. It may be an O-Oneway or R-Roundtrip or Y-Roundtrip Special.
TrackId	String	Unique reference Id from Avail response.
AirlineClass	String	Class reference from Multiclass(Avail) response.
SeatAvailFlag	String	Seats reference from Multiclass(Avail) response.
18.2 GetMultiClassFare Request
Copy Code
                                                            Request:- {
                                                            "AgentInfo": {
                                                            "AgentId": "XXXXXXXX",
                                                            "UserName": "XXXXXXXXXXX",
                                                            "AppType": "API",
                                                            "Version": "XXX"
                                                            },
                                                            "FlightsInfo": [
                                                            {
                                                            "FlightID": "9603"
​
                                                            }
                                                            ],
                                                            "ClassFare": [
                                                            {
                                                            "AirlineClass": "B",
                                                            "SeatAvailFlag": "9"
                                                            }
                                                            ],
                                                            "PassengersInfo": {
                                                            "AdultCount": 1,
                                                            "ChildCount": 0,
                                                            "InfantCount": 0
                                                            },
                                                            "TripType": "O",
                                                            "Trackid": "AQ144316163728603151443236663904RSCN5INQMIX"
                                                            } 
                                                        
18.3 GetMultiClassFare Responces
Copy Code
                                                            {
                                                            "Trackid": "AQ144437042453852611444393406755UA0DH8126OE",
                                                            "FlightDetails": [
                                                            {
                                                            "FlightID": "8495",
                                                            "Stock": "UAI",
                                                            "FlightNumber": "AI 2986",
                                                            "Origin": "BOM",
                                                            "Destination": "DEL",
                                                            "DepartureTerminal": "2",
                                                            "ArrivalTerminal": "3",
                                                            "DepartureDateTime": "30 Sep 2025 22:50",
                                                            "ArrivalDateTime": "01 Oct 2025 01:00",
                                                            "Class": "B",
                                                            "ReferenceToken": "FXOnJJpBQ4R61ZeMWbOoPSIidKtL7uVP5/oO7HumG2HdQT8yiL8ODq7ZQ+N5Nu6GbeKSpIouqVRGoqDW8xSTiohMJs7/edJH5U255Q2r+eZQjdEEadyz90CaqbYnd1bM8YfS+iuuii5FEcspyyE6dMGumLJURfh3qRfGO3dKi/cG6BSGOtRGC97zNdWROFn8CycPceMDt7HBMeR8Wp25mVv33ztfqRToQU4XKScmg5hj1UwbKTTWR/O5dyDGhLyJEdfaH6QGDi/elrd7aod6Tb1+gjKgLVdRkHoi3OAd5ng6UYGWo6e+6Za/1KGoQiukH5Vj7SXUIjIQf+Xng+AbHrT5JC+R+bwtEkvhB610Agsna8iG/DUGbtsxlIjuE3a3iV+3XiJa5IduwImP0FLjbi3pf2JnbcrUK8/9+beKVj1/iWjePFjWrk+ElFPDPXtiJGAZ8QZesfW5geluOEdBj1cO4h+n7xokLVCL/XO9Z5F4xwWWi66cGj+NJlns7YenjQpg6kdjM9JZImuEpENT5oeBHwWwB31pCMqy0WrFTGPneEkuPvKRrDSnKo+3EAY1Z++Y28a8SLzReFFIIIw9/E1qWa/94FGzN/4yODmM8hhC2N4th2KwTRWZYdGKqyWM8PdW4HAaK6O5Z4VPX3jjlq2pUIaaMGAbLNVnXsC3pfGmEHO77GvQzxEqxptwi780xxzrQVffwCJRXVpLzArO8Gr/whgHpFTvQJVlTA/f0Lhy9iN5FiNGbC5afV3W5xJDHlJVLgeXg/ZLLqt4w9rk6cuBzKG0tXVZ8GwnYbXkgBJH8tyuM/rZ7QTajd9zOEDa+erYpmdtiShVs0FooLGHY6N+cOU7W3Tl/p9YjJTtw/V9A8/VAPB/dP7MMox/n1bD7var+8igl6F7EDs8LpGcfpX8h8j0757YkIlpF0tDOtu+jGf9x7oc8etEiF1qLjkbQPeNqaW2yZVIznLB9Pa6+NbdoFWQ7KUyNOxzGodU5JOpyNLZTuyLexhjpaGnoo4+yxMTDQgPs4Ub2QGWHyvP0pWsGoaTn5gy1AlaK41VkxkeSS+w1gW+LIwKYiu0w45Lv22r+NLr79/pjALgGiLCBvrdtju3h1hjPR7m6qBFRfhlWPuqgl63k02cz+5WOCxNe9vqDpRa0Rn5m5s3pxv+owokWf/zL3mlcp8o0cuR3ODVmQbBEhfUNDgRTgQk8gAz2F5fHEVPq2iekuQnBkt8EGnsYZxlc3/FSJJOsl/81DRJBkl3MZw3Y+3J+Gsrx1Jjwicn21ujgbPGORz1kOaXYB0TQdw/vl3wMsY7PlqYloKO7dwt4a98ma4Bkjp/aJsm6thPzEH4JLwNeKq5f6gCKG5BSVGoZeb4MlfeO0Tc6UoODqYN4GveTosSZxhI0tcuVANH/6v8YqxsBzjXbPqTa4CvOj2ubw+Bpt7vs1fBsT6SslWzROuux5yE84oYWXMbEyHW41kJWOhFhTqqgik0uLYIoln/aLGv82lJz8l2Jn/qTSwOObTAgdsHG/g7vKOkW32Wzgm7SgK8wMTMTp7HT8G2pbYGv/aoIW9O56JSOg5KLN6/IgoBHMNEiHaq3+nCDCkn4Zb0o0BzdURHEx6kWkB8qc4tqUAjnlyYag6hNwO9XFBOS+Vn5ZG5baFUyARlk1SVKVAioPuMFDUjQzrHsgGnHBNedgavqQWEZsuuT7UjuQ931ISt2D6/slaDuKp620GSy4hh1pPAPCyvr3tCW3uBp2z/cx1GKyVFxPCDLSvulg4dNEgzmRQeheE9I68+jMVjTxz04RAP7yyHvCCWTZkZDcbwr427rlqGIAoI2ASDGQ3O15BJNmKkDTRJaEptR9ctMTCFdAt9nIx/T0aL0SRA39jARsZvRzYyXjvATtUdYY0H5D8jSlCeRRAm24aknzcsxiFBRWfGNGY/zMXbZWr5QNsdtpaMWWUPXjoymmpXSqrsr88fN17p6wNfAhrhmgBrSEZoCAnNZTpkYWHVVm1V5EhSeJJ+WY72FKtDuiVz95kJUHydAw5l3/LXa44K41zNTL0OytnhkOaNwpfnmA==",
                                                            "SegRef": "1",
                                                            "ItinRef": "0",
                                                            "FareId": "UAI_N_0",
                                                            "Cabin": "E",
                                                            "FareBasisCode": "BU1YXSII",
                                                            "Stops": "",
                                                            "AirlineCategory": "FSC",
                                                            "CNX": "N",
                                                            "PlatingCarrier": "AI",
                                                            "OperatingCarrier": "",
                                                            "SegmentDetails": "Aircraft Type : \r\nJourney Time : \r\nStart Terminal : \r\nEndTerminal : \r\nBaggage : 15 KG",
                                                            "FlyingTime": "",
                                                            "AvailSeat": "9",
                                                            "FareTypeDescription": "ECO VALUE",
                                                            "FareDescription": "ECO VALUE",
                                                            "Baggage": "15 KG"
                                                            }
                                                            ],
                                                            "Fares": [
                                                            {
                                                            "Faredescription": [
                                                            {
                                                            "Paxtype": "ADT",
                                                            "BaseAmount": "21811",
                                                            "TotalTaxAmount": "1778",
                                                            "GrossAmount": "23589",
                                                            "Commission": "0",
                                                            "Incentive": null,
                                                            "Servicecharge": null,
                                                            "TDS": "0",
                                                            "Discount": "0",
                                                            "PLBAmount": "0",
                                                            "SF": "0",
                                                            "SFGST": "0",
                                                            "Taxes": [
                                                            {
                                                            "Amount": "170",
                                                            "Code": "YR"
                                                            },
                                                            {
                                                            "Amount": "170",
                                                            "Code": "YR"
                                                            },
                                                            {
                                                            "Amount": "170",
                                                            "Code": "YR"
                                                            }
                                                            ]
                                                            }
                                                            ],
                                                            "FlightId": "UAI_N_0",
                                                            "FareType": "N",
                                                            "Currency": "INR"
                                                            }
                                                            ],
                                                            "Status": {
                                                            "Error": "",
                                                            "ResultCode": "1",
                                                            "SequenceID": "14443704245385261"
                                                            }
                                                            }
                                                        
18.4 GetMultiClassFare Failure
Copy Code
                                                            {
                                                            "Trackid": null,
                                                            "FlightDetails": null,
                                                            "Fares": null,
                                                            "Status": {
                                                            "Error": "Unable to get the FareClass. Kindly try again.",
                                                            "ResultCode": "0",
                                                            "SequenceID": "18360188573140862"
                                                            }
                                                            }
                                                        
19 Support
Customers are required to send an email outlining their observation and question first. The Airiq team will review and respond to the email within 24 hours of receiving it. According to the escalation structure listed below, the client may raise the issue regarding any ongoing problems. In any of these situations, it is mandatory to send a first-level email with the request and response in JSON format as well as a detailed description of the problem being experienced to the appropriate contact, ensuring that the team will be in touch as soon as possible.


Ⅰ

Level

Name:
Biki

Email ID:
biki.mandal@airiq.in

Contact No.:
7477791072

20 Annexure
20.1 Customized Ticket Copy (For Airline Indigo)
Implementation of Barcode workflow Process

The suggested text should be “Your Airlines Reference:” followed by the code.
This should have a 10-pixel margin at top and at right to ensure that codes do not overflow page
Below the sample ticket copy for your reference
To make this easy and minimize effort, can use the attached “itextsharp” dll and use below code to generate the Barcode as Image which will be saved in the desired folder

#region For PDF417 itextsharp change
Copy Code
                                                            private byte[] generateBarCode(string strBarCode)
                                                            {
                                                            string ImagePath = "D:\\" + strBarCode + "BarCode" + ".jpg";
                                                            iTextSharp.text.pdf.BarcodePDF417 barcode = new iTextSharp.text.pdf.BarcodePDF417();
                                                            barcode.SetText(strBarCode);
                                                            System.Drawing.Image img = barcode.CreateDrawingImage(Color.Black, Color.White);
                                                            if (!File.Exists(ImagePath))
                                                            img.Save(ImagePath);
                                                            byte[] m_Bytes = File.ReadAllBytes(ImagePath);
                                                            return m_Bytes;
                                                            }
                                                        
#endregion
Below is the Itinerary Barcode method detail
Type: 1D Bar Code
Used iTextSharp third Party DLL to create the PNR Barcode image
Specifically used the method “iTextSharp.text.pdf.Barcode128()”
iTextSharp.text.pdf.Barcode128 barcode = new iTextSharp.text.pdf.Barcode128();
barcode.Code = "." + BarCode;
Values: dot(.) and then PNR No. Example: CP24JQ
Refer the attached dll detail for reference
18.2 GST Format
Following validations/requirements will need to be applied on the keyed values


System should not allow user to partially fill the GSTN information, implying that user should fill all 5 fields or none.
Only 1 GST Registration Number and 1 Company Name is allowed per PNR, even if PNR has multiple passengers.
A GST Registration Number is not required to proceed with a booking, but if a GST Registration Number is entered, the system needs to validate that the format of the entered number is correct.
The GST Registration Number will be composed of 15 alpha-numeric characters.
Character Position	Data Type
1st	Numeric
2nd	Numeric
3rd	Alpha
4th	Alpha
5th	Alpha
6th	Alpha
7th	Alpha
8th	Numeric
9th	Numeric
10th	Numeric
11th	Numeric
12th	Alpha
13th	Alpha/Numeric
14th	Alpha/Numeric
15th	Alpha/Numeric
