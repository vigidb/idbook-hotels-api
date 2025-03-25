IMAGE_TYPE_CHOICES = (
    ('DELUXE', 'DELUXE'),
    ('CLASSIC', 'CLASSIC'),
    ('PREMIUM', 'PREMIUM'),
    ('HOTEL', 'HOTEL'),
    ('BATHROOM', 'BATHROOM'),
    ('SURROUNDING', 'SURROUNDING'),
)

PROPERTY_TYPE = (
    ('Hotel', 'Hotel'),
    ('Cottage', 'Cottage'),
    ('Villa', 'Villa'),
    ('Cabin', 'Cabin'),
    ('Farmstay', 'Farmstay'),
    ('Houseboat', 'Houseboat'),
    ('Lighthouse', 'Lighthouse'),
)

RENTAL_FORM = (
    ('entire place', 'entire place'),
    ('private room', 'private room'),
    ('share room', 'share room'),
)
    

ROOM_CHOICES = (
    ('DELUXE', 'DELUXE'),
    ('CLASSIC', 'CLASSIC'),
    ('PREMIUM', 'PREMIUM'),
)

ROOM_VIEW_CHOICES = (
    ('SEA VIEW', 'SEA VIEW'),
    ('RIVER VIEW', 'RIVER VIEW'),
    ('VALLEY VIEW', 'VALLEY VIEW'),
    ('CITY VIEW', 'CITY VIEW'),
    ('POOL VIEW', 'POOL VIEW'),
    ('SWIMMING POOL VIEW', 'SWIMMING POOL VIEW'),
    ('BEACH VIEW', 'BEACH VIEW'),
    ('MOUNTAIN VIEW', 'MOUNTAIN VIEW'),
    ('LAKE VIEW', 'LAKE VIEW'),
    ('TEMPLE VIEW', 'TEMPLE VIEW'),
    ('GARDEN VIEW', 'GARDEN VIEW'),
    ('HILL VIEW', 'HILL VIEW'),
    ('FOREST VIEW', 'FOREST VIEW'),
    ('TERRACE VIEW', 'TERRACE VIEW'),
    ('BALCONY VIEW', 'BALCONY VIEW'),
    ('JUNGLE VIEW', 'JUNGLE VIEW'),
    ('COURTYARD VIEW', 'COURTYARD VIEW'),
    ('NON VIEW', 'NON VIEW'),
    
)

ROOM_MEASUREMENT = (
    ('square feet', 'square feet'),
    ('square meter', 'square meter'),
)

BED_TYPE_CHOICES = (
    ('KING', 'KING'),
    ('QUEEN', 'QUEEN'),
    ('SINGLE', 'SINGLE'),
)

BOOKING_TYPE = (
    ('HOLIDAYPACK', 'HOLIDAYPACK'),
    ('HOTEL', 'HOTEL'),
    ('VEHICLE', 'VEHICLE'),
    ('FLIGHT', 'FLIGHT'),
)

VEHICLE_TYPE = (
    ('CAR', 'CAR'),
    ('TRAVELLER', 'TRAVELLER'),
    ('BUS', 'BUS')
)

FLIGHT_TRIP = (
    ('ONE-WAY', 'ONE-WAY'),
    ('ROUND', 'ROUND'),
)

FLIGHT_CLASS = (
    ('ECONOMY', 'ECONOMY'),
    ('BUSINESS', 'BUSINESS'),
    ('FIRST', 'FIRST'),
) 

TIME_SLOTS = (
    ('4 Hrs', '4 Hrs'),
    ('8 Hrs', '8 Hrs'),
    ('12 Hrs', '12 Hrs'),
    ('24 Hrs', '24 Hrs'),
    # ('NIGHTLY', 0),
)

BLOOD_GROUP_CHOICES = (
    ("A+", "A+"),
    ("A-", "A-"),
    ("B+", "B+"),
    ("B-", "B-"),
    ("AB+", "AB+"),
    ("AB-", "AB-"),
    ("O+", "O+"),
    ("O-", "O-"),
)

GENDER_CHOICES = (
    ("Male", "Male"),
    ("Female", "Female"),
    ("Other", "Other"),
)

BOOKING_STATUS_CHOICES = STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('canceled', 'Canceled'),
        ('completed', 'Completed'),
        ('no_show', 'No Show'),
        ('on_hold', 'On Hold')
    )
##TOUR_DURATION_CHOICES = (
##    ("1N/2D", '1N/2D'),
##    (2, "2N/3D"),
##    (3, "3N/4D"),
##    (4, "4N/5D"),
##    (5, "5N/6D"),
##    (6, "6N/7D"),
##    (7, "7N/8D"),
##    (8, "8N/9D"),
##    (9, "9N/10D"),
##    (10, "10N/11D"),
##    (11, "11N/12D"),
##    (12, "12N/13D"),
##    (13, "13N/14D"),
##    (14, "14N/15D"),
##    (15, "15N/16D"),
##    (16, "16N/17D"),
##    (17, "17N/18D"),
##)

TOUR_DURATION_CHOICES = (
    ("1N/2D", '1N/2D'),
    ("2N/3D", "2N/3D"),
    ("3N/4D", "3N/4D"),
    ("4N/5D", "4N/5D"),
    ("5N/6D", "5N/6D"),
    ("6N/7D", "6N/7D"),
    ("7N/8D", "7N/8D"),
    ("8N/9D", "8N/9D"),
    ("9N/10D", "9N/10D"),
    ("10N/11D", "10N/11D"),
    ("11N/12D", "11N/12D"),
    ("12N/13D", "12N/13D"),
    ("13N/13D", "13N/14D"),
    ("14N/13D", "14N/15D"),
    ("15N/13D", "15N/16D"),
    ("16N/13D", "16N/17D"),
    ("17N/13D", "17N/18D"),
)

INCLUSION_EXCLUSION_CHOICES = (
    ("INCLUSION", "Inclusion"),
    ("EXCLUSION", "Exclusion"),
)

APPOINTMENT_STATUS_CHOICES = (
    ("Accepted", "Accepted"),
    ("Waiting", "Waiting"),
    ("Cancelled", "Cancelled"),
)

TXN_TYPE_CHOICES = (
    ("Credit", "Credit"),
    ("Debit", "Debit"),
)

COUPON_TYPES = (
        ('all', 'All Customers'),
        ('flat', 'Flat Discount'),
        ('employee', 'Employee Discount'),
        ('bulk', 'Bulk Booking Discount'),
        # Add more types as needed
)

PAYMENT_TYPE = (
    ('PAYMENT GATEWAY', 'PAYMENT GATEWAY'),
    ('WALLET', 'WALLET'),
    ('NBFC', 'NBFC'),
)

PAYMENT_MEDIUM = (
    ('PHONE PAY', 'PHONE PAY'),
    ('Idbook', 'Idbook'),
)

PAYMENT_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("On Process", "On Process"),
    ("Complete", "Complete"),
    ("Suspend", "Suspend"),
    ("Others", "Others"),
)

PAYMENT_METHOD_CHOICES = (
    ("Online", "Online"),
    ("Direct", "Direct"),
    ("Wallet Top up", "Wallet Top up"),
    ("Account Withdraw", "Account Withdraw"),
    ("Others", "Others"),
)

TRANSACTION_FOR = (
    ("booking_confirmed", "booking_confirmed"),
    ("booking_refund", "booking_refund"),
    ("referral_booking", "referral_booking"),
    ("booking_refund", "booking_refund"),
    ("others", "others")
)

KYC_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("On Process", "On Process"),
    ("Complete", "Complete"),
    ("Suspend", "Suspend"),
    ("Others", "Others"),
)
LANGUAGES_CHOICES = (
    ("English", "English"),
    ("Hindi", "Hindi"),
)

SERVICE_CATEGORY_TYPE_CHOICES = (
    ("Hotel", "Hotel"),
    ("Hotel & Restaurant", "Hotel & Restaurant"),
    ("Hotel, Bar & Restaurant", "Hotel, Bar & Restaurant"),
    ("Hotel & Bar", "Hotel & Bar"),
    ("Hotel, Bar, Spa & Restaurant", "Hotel, Bar, Spa & Restaurant"),
)
EDUCATION_CHOICES = (
    ("Some High School", "Some High School"),
    ("High School Diploma", "High School Diploma"),
    ("Some College", "Some College"),
    ("Associate Degree", "Associate Degree"),
    ("Bachelor's Degree", "Bachelor's Degree"),
    ("Master's Degree", "Master's Degree"),
    ("Doctorate or Higher", "Doctorate or Higher"),
    ("Others", "Others"),
)

KYC_DOCUMENT_CHOICES = (
    ("ADHAR CARD", "ADHAR CARD"),
    ("VOTER ID CARD", "VOTER ID CARD"),
    ("DRIVING LICENCE", "DRIVING LICENCE"),
    ("Others", "Others"),
)

BONUS_STATUS_CHOICES = (
    ("Signup Bonus", "Signup Bonus"),
    ("Referral Bonus", "Referral Bonus"),
)

DEPOSIT_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("On Process", "On Process"),
    ("Completed", "Completed"),
    ("Suspend", "Suspend"),
    ("Others", "Others"),
)

PAYMENT_GATEWAY_STATUS_CHOICES = (
    ("Enabled", "Enabled"),
    ("Disabled", "Disabled"),
)

WORKING_DAYS = (
    ('Monday', 'Monday'),
    ('Tuesday', 'Tuesday'),
    ('Wednesday', 'Wednesday'),
    ('Thursday', 'Thursday'),
    ('Friday', 'Friday'),
    ('Saturday', 'Saturday'),
    ('Sunday', 'Sunday'),
)

FCM_TOKEN_CHOICE = (("android", "Android"), ("ios", "IOS"), ("web", "Web"))

ENQUIRY_CHOICES = (("Transaction", "Transaction"),("Withdrawal", "Withdrawal"),
                   # ("Contest", "Contest"),
                   # ("Mega Contest", "Mega Contest"),
                   ("Referral", "Referral"),
                   # ("Mega Referral", "Mega Referral"),
                   ("Other", "Other"))


DISTRICT_DATA = [
      {
         "state":"Andhra Pradesh",
         "districts":[
            "Anantapur",
            "Chittoor",
            "East Godavari",
            "Guntur",
            "Krishna",
            "Kurnool",
            "Nellore",
            "Prakasam",
            "Srikakulam",
            "Visakhapatnam",
            "Vizianagaram",
            "West Godavari",
            "YSR Kadapa"
         ]
      },
      {
         "state":"Arunachal Pradesh",
         "districts":[
            "Tawang",
            "West Kameng",
            "East Kameng",
            "Papum Pare",
            "Kurung Kumey",
            "Kra Daadi",
            "Lower Subansiri",
            "Upper Subansiri",
            "West Siang",
            "East Siang",
            "Siang",
            "Upper Siang",
            "Lower Siang",
            "Lower Dibang Valley",
            "Dibang Valley",
            "Anjaw",
            "Lohit",
            "Namsai",
            "Changlang",
            "Tirap",
            "Longding"
         ]
      },
      {
         "state":"Assam",
         "districts":[
            "Baksa",
            "Barpeta",
            "Biswanath",
            "Bongaigaon",
            "Cachar",
            "Charaideo",
            "Chirang",
            "Darrang",
            "Dhemaji",
            "Dhubri",
            "Dibrugarh",
            "Goalpara",
            "Golaghat",
            "Hailakandi",
            "Hojai",
            "Jorhat",
            "Kamrup Metropolitan",
            "Kamrup",
            "Karbi Anglong",
            "Karimganj",
            "Kokrajhar",
            "Lakhimpur",
            "Majuli",
            "Morigaon",
            "Nagaon",
            "Nalbari",
            "Dima Hasao",
            "Sivasagar",
            "Sonitpur",
            "South Salmara-Mankachar",
            "Tinsukia",
            "Udalguri",
            "West Karbi Anglong"
         ]
      },
      {
         "state":"Bihar",
         "districts":[
            "Araria",
            "Arwal",
            "Aurangabad",
            "Banka",
            "Begusarai",
            "Bhagalpur",
            "Bhojpur",
            "Buxar",
            "Darbhanga",
            "East Champaran (Motihari)",
            "Gaya",
            "Gopalganj",
            "Jamui",
            "Jehanabad",
            "Kaimur (Bhabua)",
            "Katihar",
            "Khagaria",
            "Kishanganj",
            "Lakhisarai",
            "Madhepura",
            "Madhubani",
            "Munger (Monghyr)",
            "Muzaffarpur",
            "Nalanda",
            "Nawada",
            "Patna",
            "Purnia (Purnea)",
            "Rohtas",
            "Saharsa",
            "Samastipur",
            "Saran",
            "Sheikhpura",
            "Sheohar",
            "Sitamarhi",
            "Siwan",
            "Supaul",
            "Vaishali",
            "West Champaran"
         ]
      },
      {
         "state":"Chandigarh (UT)",
         "districts":[
            "Chandigarh"
         ]
      },
      {
         "state":"Chhattisgarh",
         "districts":[
            "Balod",
            "Baloda Bazar",
            "Balrampur",
            "Bastar",
            "Bemetara",
            "Bijapur",
            "Bilaspur",
            "Dantewada (South Bastar)",
            "Dhamtari",
            "Durg",
            "Gariyaband",
            "Janjgir-Champa",
            "Jashpur",
            "Kabirdham (Kawardha)",
            "Kanker (North Bastar)",
            "Kondagaon",
            "Korba",
            "Korea (Koriya)",
            "Mahasamund",
            "Mungeli",
            "Narayanpur",
            "Raigarh",
            "Raipur",
            "Rajnandgaon",
            "Sukma",
            "Surajpur  ",
            "Surguja"
         ]
      },
      {
         "state":"Dadra and Nagar Haveli (UT)",
         "districts":[
            "Dadra & Nagar Haveli"
         ]
      },
      {
         "state":"Daman and Diu (UT)",
         "districts":[
            "Daman",
            "Diu"
         ]
      },
      {
         "state":"Delhi (NCT)",
         "districts":[
            "Central Delhi",
            "East Delhi",
            "New Delhi",
            "North Delhi",
            "North East  Delhi",
            "North West  Delhi",
            "Shahdara",
            "South Delhi",
            "South East Delhi",
            "South West  Delhi",
            "West Delhi"
         ]
      },
      {
         "state":"Goa",
         "districts":[
            "North Goa",
            "South Goa"
         ]
      },
      {
         "state":"Gujarat",
         "districts":[
            "Ahmedabad",
            "Amreli",
            "Anand",
            "Aravalli",
            "Banaskantha (Palanpur)",
            "Bharuch",
            "Bhavnagar",
            "Botad",
            "Chhota Udepur",
            "Dahod",
            "Dangs (Ahwa)",
            "Devbhoomi Dwarka",
            "Gandhinagar",
            "Gir Somnath",
            "Jamnagar",
            "Junagadh",
            "Kachchh",
            "Kheda (Nadiad)",
            "Mahisagar",
            "Mehsana",
            "Morbi",
            "Narmada (Rajpipla)",
            "Navsari",
            "Panchmahal (Godhra)",
            "Patan",
            "Porbandar",
            "Rajkot",
            "Sabarkantha (Himmatnagar)",
            "Surat",
            "Surendranagar",
            "Tapi (Vyara)",
            "Vadodara",
            "Valsad"
         ]
      },
      {
         "state":"Haryana",
         "districts":[
            "Ambala",
            "Bhiwani",
            "Charkhi Dadri",
            "Faridabad",
            "Fatehabad",
            "Gurgaon",
            "Hisar",
            "Jhajjar",
            "Jind",
            "Kaithal",
            "Karnal",
            "Kurukshetra",
            "Mahendragarh",
            "Mewat",
            "Palwal",
            "Panchkula",
            "Panipat",
            "Rewari",
            "Rohtak",
            "Sirsa",
            "Sonipat",
            "Yamunanagar"
         ]
      },
      {
         "state":"Himachal Pradesh",
         "districts":[
            "Bilaspur",
            "Chamba",
            "Hamirpur",
            "Kangra",
            "Kinnaur",
            "Kullu",
            "Lahaul &amp; Spiti",
            "Mandi",
            "Shimla",
            "Sirmaur (Sirmour)",
            "Solan",
            "Una"
         ]
      },
      {
         "state":"Jammu and Kashmir",
         "districts":[
            "Anantnag",
            "Bandipore",
            "Baramulla",
            "Budgam",
            "Doda",
            "Ganderbal",
            "Jammu",
            "Kargil",
            "Kathua",
            "Kishtwar",
            "Kulgam",
            "Kupwara",
            "Leh",
            "Poonch",
            "Pulwama",
            "Rajouri",
            "Ramban",
            "Reasi",
            "Samba",
            "Shopian",
            "Srinagar",
            "Udhampur"
         ]
      },
      {
         "state":"Jharkhand",
         "districts":[
            "Bokaro",
            "Chatra",
            "Deoghar",
            "Dhanbad",
            "Dumka",
            "East Singhbhum",
            "Garhwa",
            "Giridih",
            "Godda",
            "Gumla",
            "Hazaribag",
            "Jamtara",
            "Khunti",
            "Koderma",
            "Latehar",
            "Lohardaga",
            "Pakur",
            "Palamu",
            "Ramgarh",
            "Ranchi",
            "Sahibganj",
            "Seraikela-Kharsawan",
            "Simdega",
            "West Singhbhum"
         ]
      },
      {
         "state":"Karnataka",
         "districts":[
            "Bagalkot",
            "Ballari (Bellary)",
            "Belagavi (Belgaum)",
            "Bengaluru (Bangalore) Rural",
            "Bengaluru (Bangalore) Urban",
            "Bidar",
            "Chamarajanagar",
            "Chikballapur",
            "Chikkamagaluru (Chikmagalur)",
            "Chitradurga",
            "Dakshina Kannada",
            "Davangere",
            "Dharwad",
            "Gadag",
            "Hassan",
            "Haveri",
            "Kalaburagi (Gulbarga)",
            "Kodagu",
            "Kolar",
            "Koppal",
            "Mandya",
            "Mysuru (Mysore)",
            "Raichur",
            "Ramanagara",
            "Shivamogga (Shimoga)",
            "Tumakuru (Tumkur)",
            "Udupi",
            "Uttara Kannada (Karwar)",
            "Vijayapura (Bijapur)",
            "Yadgir"
         ]
      },
      {
         "state":"Kerala",
         "districts":[
            "Alappuzha",
            "Ernakulam",
            "Idukki",
            "Kannur",
            "Kasaragod",
            "Kollam",
            "Kottayam",
            "Kozhikode",
            "Malappuram",
            "Palakkad",
            "Pathanamthitta",
            "Thiruvananthapuram",
            "Thrissur",
            "Wayanad"
         ]
      },
      {
         "state":"Lakshadweep (UT)",
         "districts":[
            "Agatti",
            "Amini",
            "Androth",
            "Bithra",
            "Chethlath",
            "Kavaratti",
            "Kadmath",
            "Kalpeni",
            "Kilthan",
            "Minicoy"
         ]
      },
      {
         "state":"Madhya Pradesh",
         "districts":[
            "Agar Malwa",
            "Alirajpur",
            "Anuppur",
            "Ashoknagar",
            "Balaghat",
            "Barwani",
            "Betul",
            "Bhind",
            "Bhopal",
            "Burhanpur",
            "Chhatarpur",
            "Chhindwara",
            "Damoh",
            "Datia",
            "Dewas",
            "Dhar",
            "Dindori",
            "Guna",
            "Gwalior",
            "Harda",
            "Hoshangabad",
            "Indore",
            "Jabalpur",
            "Jhabua",
            "Katni",
            "Khandwa",
            "Khargone",
            "Mandla",
            "Mandsaur",
            "Morena",
            "Narsinghpur",
            "Neemuch",
            "Panna",
            "Raisen",
            "Rajgarh",
            "Ratlam",
            "Rewa",
            "Sagar",
            "Satna",
            "Sehore",
            "Seoni",
            "Shahdol",
            "Shajapur",
            "Sheopur",
            "Shivpuri",
            "Sidhi",
            "Singrauli",
            "Tikamgarh",
            "Ujjain",
            "Umaria",
            "Vidisha"
         ]
      },
      {
         "state":"Maharashtra",
         "districts":[
            "Ahmednagar",
            "Akola",
            "Amravati",
            "Aurangabad",
            "Beed",
            "Bhandara",
            "Buldhana",
            "Chandrapur",
            "Dhule",
            "Gadchiroli",
            "Gondia",
            "Hingoli",
            "Jalgaon",
            "Jalna",
            "Kolhapur",
            "Latur",
            "Mumbai City",
            "Mumbai Suburban",
            "Nagpur",
            "Nanded",
            "Nandurbar",
            "Nashik",
            "Osmanabad",
            "Palghar",
            "Parbhani",
            "Pune",
            "Raigad",
            "Ratnagiri",
            "Sangli",
            "Satara",
            "Sindhudurg",
            "Solapur",
            "Thane",
            "Wardha",
            "Washim",
            "Yavatmal"
         ]
      },
      {
         "state":"Manipur",
         "districts":[
            "Bishnupur",
            "Chandel",
            "Churachandpur",
            "Imphal East",
            "Imphal West",
            "Jiribam",
            "Kakching",
            "Kamjong",
            "Kangpokpi",
            "Noney",
            "Pherzawl",
            "Senapati",
            "Tamenglong",
            "Tengnoupal",
            "Thoubal",
            "Ukhrul"
         ]
      },
      {
         "state":"Meghalaya",
         "districts":[
            "East Garo Hills",
            "East Jaintia Hills",
            "East Khasi Hills",
            "North Garo Hills",
            "Ri Bhoi",
            "South Garo Hills",
            "South West Garo Hills ",
            "South West Khasi Hills",
            "West Garo Hills",
            "West Jaintia Hills",
            "West Khasi Hills"
         ]
      },
      {
         "state":"Mizoram",
         "districts":[
            "Aizawl",
            "Champhai",
            "Kolasib",
            "Lawngtlai",
            "Lunglei",
            "Mamit",
            "Saiha",
            "Serchhip"
         ]
      },
      {
         "state":"Nagaland",
         "districts":[
            "Dimapur",
            "Kiphire",
            "Kohima",
            "Longleng",
            "Mokokchung",
            "Mon",
            "Peren",
            "Phek",
            "Tuensang",
            "Wokha",
            "Zunheboto"
         ]
      },
      {
         "state":"Odisha",
         "districts":[
            "Angul",
            "Balangir",
            "Balasore",
            "Bargarh",
            "Bhadrak",
            "Boudh",
            "Cuttack",
            "Deogarh",
            "Dhenkanal",
            "Gajapati",
            "Ganjam",
            "Jagatsinghapur",
            "Jajpur",
            "Jharsuguda",
            "Kalahandi",
            "Kandhamal",
            "Kendrapara",
            "Kendujhar (Keonjhar)",
            "Khordha",
            "Koraput",
            "Malkangiri",
            "Mayurbhanj",
            "Nabarangpur",
            "Nayagarh",
            "Nuapada",
            "Puri",
            "Rayagada",
            "Sambalpur",
            "Sonepur",
            "Sundargarh"
         ]
      },
      {
         "state":"Puducherry (UT)",
         "districts":[
            "Karaikal",
            "Mahe",
            "Pondicherry",
            "Yanam"
         ]
      },
      {
         "state":"Punjab",
         "districts":[
            "Amritsar",
            "Barnala",
            "Bathinda",
            "Faridkot",
            "Fatehgarh Sahib",
            "Fazilka",
            "Ferozepur",
            "Gurdaspur",
            "Hoshiarpur",
            "Jalandhar",
            "Kapurthala",
            "Ludhiana",
            "Mansa",
            "Moga",
            "Muktsar",
            "Nawanshahr (Shahid Bhagat Singh Nagar)",
            "Pathankot",
            "Patiala",
            "Rupnagar",
            "Sahibzada Ajit Singh Nagar (Mohali)",
            "Sangrur",
            "Tarn Taran"
         ]
      },
      {
         "state":"Rajasthan",
         "districts":[
            "Ajmer",
            "Alwar",
            "Banswara",
            "Baran",
            "Barmer",
            "Bharatpur",
            "Bhilwara",
            "Bikaner",
            "Bundi",
            "Chittorgarh",
            "Churu",
            "Dausa",
            "Dholpur",
            "Dungarpur",
            "Hanumangarh",
            "Jaipur",
            "Jaisalmer",
            "Jalore",
            "Jhalawar",
            "Jhunjhunu",
            "Jodhpur",
            "Karauli",
            "Kota",
            "Nagaur",
            "Pali",
            "Pratapgarh",
            "Rajsamand",
            "Sawai Madhopur",
            "Sikar",
            "Sirohi",
            "Sri Ganganagar",
            "Tonk",
            "Udaipur"
         ]
      },
      {
         "state":"Sikkim",
         "districts":[
            "East Sikkim",
            "North Sikkim",
            "South Sikkim",
            "West Sikkim"
         ]
      },
      {
         "state":"Tamil Nadu",
         "districts":[
            "Ariyalur",
            "Chennai",
            "Coimbatore",
            "Cuddalore",
            "Dharmapuri",
            "Dindigul",
            "Erode",
            "Kanchipuram",
            "Kanyakumari",
            "Karur",
            "Krishnagiri",
            "Madurai",
            "Nagapattinam",
            "Namakkal",
            "Nilgiris",
            "Perambalur",
            "Pudukkottai",
            "Ramanathapuram",
            "Salem",
            "Sivaganga",
            "Thanjavur",
            "Theni",
            "Thoothukudi (Tuticorin)",
            "Tiruchirappalli",
            "Tirunelveli",
            "Tiruppur",
            "Tiruvallur",
            "Tiruvannamalai",
            "Tiruvarur",
            "Vellore",
            "Viluppuram",
            "Virudhunagar"
         ]
      },
      {
         "state":"Telangana",
         "districts":[
            "Adilabad",
            "Bhadradri Kothagudem",
            "Hyderabad",
            "Jagtial",
            "Jangaon",
            "Jayashankar Bhoopalpally",
            "Jogulamba Gadwal",
            "Kamareddy",
            "Karimnagar",
            "Khammam",
            "Komaram Bheem Asifabad",
            "Mahabubabad",
            "Mahabubnagar",
            "Mancherial",
            "Medak",
            "Medchal",
            "Nagarkurnool",
            "Nalgonda",
            "Nirmal",
            "Nizamabad",
            "Peddapalli",
            "Rajanna Sircilla",
            "Rangareddy",
            "Sangareddy",
            "Siddipet",
            "Suryapet",
            "Vikarabad",
            "Wanaparthy",
            "Warangal (Rural)",
            "Warangal (Urban)",
            "Yadadri Bhuvanagiri"
         ]
      },
      {
         "state":"Tripura",
         "districts":[
            "Dhalai",
            "Gomati",
            "Khowai",
            "North Tripura",
            "Sepahijala",
            "South Tripura",
            "Unakoti",
            "West Tripura"
         ]
      },
      {
         "state":"Uttarakhand",
         "districts":[
            "Almora",
            "Bageshwar",
            "Chamoli",
            "Champawat",
            "Dehradun",
            "Haridwar",
            "Nainital",
            "Pauri Garhwal",
            "Pithoragarh",
            "Rudraprayag",
            "Tehri Garhwal",
            "Udham Singh Nagar",
            "Uttarkashi"
         ]
      },
      {
         "state":"Uttar Pradesh",
         "districts":[
            "Agra",
            "Aligarh",
            "Allahabad",
            "Ambedkar Nagar",
            "Amethi (Chatrapati Sahuji Mahraj Nagar)",
            "Amroha (J.P. Nagar)",
            "Auraiya",
            "Azamgarh",
            "Baghpat",
            "Bahraich",
            "Ballia",
            "Balrampur",
            "Banda",
            "Barabanki",
            "Bareilly",
            "Basti",
            "Bhadohi",
            "Bijnor",
            "Budaun",
            "Bulandshahr",
            "Chandauli",
            "Chitrakoot",
            "Deoria",
            "Etah",
            "Etawah",
            "Faizabad",
            "Farrukhabad",
            "Fatehpur",
            "Firozabad",
            "Gautam Buddha Nagar",
            "Ghaziabad",
            "Ghazipur",
            "Gonda",
            "Gorakhpur",
            "Hamirpur",
            "Hapur (Panchsheel Nagar)",
            "Hardoi",
            "Hathras",
            "Jalaun",
            "Jaunpur",
            "Jhansi",
            "Kannauj",
            "Kanpur Dehat",
            "Kanpur Nagar",
            "Kanshiram Nagar (Kasganj)",
            "Kaushambi",
            "Kushinagar (Padrauna)",
            "Lakhimpur - Kheri",
            "Lalitpur",
            "Lucknow",
            "Maharajganj",
            "Mahoba",
            "Mainpuri",
            "Mathura",
            "Mau",
            "Meerut",
            "Mirzapur",
            "Moradabad",
            "Muzaffarnagar",
            "Pilibhit",
            "Pratapgarh",
            "RaeBareli",
            "Rampur",
            "Saharanpur",
            "Sambhal (Bhim Nagar)",
            "Sant Kabir Nagar",
            "Shahjahanpur",
            "Shamali (Prabuddh Nagar)",
            "Shravasti",
            "Siddharth Nagar",
            "Sitapur",
            "Sonbhadra",
            "Sultanpur",
            "Unnao",
            "Varanasi"
         ]
      },
      {
         "state":"West Bengal",
         "districts":[
            "Alipurduar",
            "Bankura",
            "Birbhum",
            "Burdwan (Bardhaman)",
            "Cooch Behar",
            "Dakshin Dinajpur (South Dinajpur)",
            "Darjeeling",
            "Hooghly",
            "Howrah",
            "Jalpaiguri",
            "Kalimpong",
            "Kolkata",
            "Malda",
            "Murshidabad",
            "Nadia",
            "North 24 Parganas",
            "Paschim Medinipur (West Medinipur)",
            "Purba Medinipur (East Medinipur)",
            "Purulia",
            "South 24 Parganas",
            "Uttar Dinajpur (North Dinajpur)"
         ]
      }
   ]

STATE_CHOICES = [(data["state"], data["state"]) for data in DISTRICT_DATA]

COUNTRY_CHOICES = (
   ("INDIA", "INDIA"), ("NEPAL", "NEPAL"), ("BHUTAN", "BHUTAN"), ("CHINA", "CHINA"), ("UAE", "UAE"),
   ("MALDIVES", "MALDIVES"),
)
OTP_TYPE_CHOICES = (
    ('MOBILE', 'MOBILE'),
    ('EMAIL', 'EMAIL'),
)

CUSTOMER_GROUP = (
    ('ORG', 'ORG'),
    ('ADMIN', 'ADMIN'),
    ('DEFAULT', 'DEFAULT'),
)

NOTIFICATION_TYPE = (
    ('GENERAL', 'GENERAL'),
    ('OFFERS', 'OFFERS'),
    ('BOOKING', 'BOOKING')
)

GST_TYPE = (
    ('', ''),
    ('IGST', 'IGST'),
    ('CGST/SGST', 'CGST/SGST')
)

DISCOUNT_TYPE = (
    ('AMOUNT', 'AMOUNT'),
    ('PERCENT', 'PERCENT')
)

MATH_COMPARE_SYMBOLS = (
    ('EQUALS', 'EQUALS'),
    ('LESS-THAN', 'LESS-THAN'),
    ('LESS-THAN-OR-EQUALS', 'LESS-THAN-OR-EQUALS'),
    ('GREATER-THAN', 'GREATER-THAN'),
    ('GREATER-THAN-OR-EQUALS', 'GREATER-THAN-OR-EQUALS'),
    ('BETWEEN', 'BETWEEN')  
)

HOTEL_STATUS = (
    ('Active', 'Active'),
    ('In-Active', 'In-Active'),
    ('In-Progress','In-Progress'),
    ('Completed','Completed'),
)

MEAL_OPTIONS = (
    ('Accomodation only', 'Accomodation only'),
    ('Free Breakfast','Free Breakfast'),
    ('Free Breakfast and Lunch', 'Free Breakfast and Lunch'),
    ('Free Breakfast and Dinner', 'Free Breakfast and Dinner'),
    ('Free Breakfast, Lunch and Dinner', 'Free Breakfast, Lunch and Dinner'),
    ('Free Breakfast, Lunch, Dinner and Custom Inclusions', 'Free Breakfast, Lunch, Dinner and Custom Inclusions'),
)

EXTRA_BED_TYPE = (
    ('Mattress', 'Mattress'),
    ('Cot', 'Cot'),
    ('Sofa cum bed', 'Sofa cum bed'),
)
    
OTP_FOR_CHOICES = (
    ('LOGIN', 'LOGIN'),
    ('SIGNUP', 'SIGNUP'),
    ('VERIFY', 'VERIFY'),
    ('VERIFY-GUEST', 'VERIFY-GUEST'),
    ('OTHER', 'OTHER')
)

SUBSCRIPTION_TYPE = (
    ('Monthly', 'Monthly'),
    ('Yearly', 'Yearly')
)

    
    
