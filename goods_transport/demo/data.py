"""Demo dataset for a Pakistani goods-transport company (own fleet + market vehicles).

All figures are in PKR and sized to be plausible for 2026 long-haul freight.
"""

LOCATIONS = [
	("Karachi", "Sindh"), ("Port Qasim", "Sindh"), ("Hyderabad", "Sindh"),
	("Sukkur", "Sindh"), ("Multan", "Punjab"), ("Lahore", "Punjab"),
	("Faisalabad", "Punjab"), ("Islamabad", "Federal"), ("Rawalpindi", "Punjab"),
	("Peshawar", "Khyber Pakhtunkhwa"), ("Quetta", "Balochistan"),
]

# (origin, destination, km, hours, toll, fuel litres)
ROUTES = [
	("Karachi", "Lahore", 1210, 26, 9500, 420),
	("Karachi", "Islamabad", 1420, 30, 11000, 495),
	("Karachi", "Faisalabad", 1080, 24, 8600, 375),
	("Karachi", "Multan", 890, 19, 7200, 310),
	("Karachi", "Hyderabad", 165, 4, 1400, 60),
	("Karachi", "Sukkur", 470, 10, 3900, 165),
	("Karachi", "Peshawar", 1600, 34, 12500, 560),
	("Karachi", "Quetta", 690, 16, 5400, 265),
	("Port Qasim", "Lahore", 1235, 27, 9700, 430),
	("Lahore", "Karachi", 1210, 26, 9500, 420),
	("Faisalabad", "Karachi", 1080, 24, 8600, 375),
]

# (name, payload kg, volume m3)
VEHICLE_TYPES = [
	("22-Wheeler Trailer", 55000, 90),
	("18-Wheeler Trailer", 45000, 80),
	("40ft Flatbed Trailer", 30000, 65),
	("10-Wheeler Truck", 25000, 45),
	("6-Wheeler Truck", 16000, 30),
	("Mazda Truck", 8000, 18),
]

# (plate, type, ownership, make, model, owner supplier or None)
VEHICLES = [
	("TLA-1188", "22-Wheeler Trailer", "Company Owned", "Hino", "SS 700", None),
	("TLB-2244", "22-Wheeler Trailer", "Company Owned", "Hino", "SS 700", None),
	("TKC-3390", "18-Wheeler Trailer", "Company Owned", "Nissan", "CWA 260", None),
	("TKD-4417", "40ft Flatbed Trailer", "Company Owned", "Mercedes", "Actros 2640", None),
	("JW-5521", "10-Wheeler Truck", "Company Owned", "Isuzu", "FVZ 34", None),
	("JX-6602", "10-Wheeler Truck", "Company Owned", "Hino", "FM 260", None),
	("LES-7788", "6-Wheeler Truck", "Company Owned", "Mazda", "Titan T4000", None),
	("TMA-9001", "22-Wheeler Trailer", "Market Vehicle", "Hino", "SS 700", "Al-Madina Goods Transport"),
	("TMB-9102", "18-Wheeler Trailer", "Market Vehicle", "Nissan", "CWA 260", "Shaheen Carriers"),
	("TMC-9233", "40ft Flatbed Trailer", "Attached", "Mercedes", "Actros 2640", "Pak Sohni Transport"),
	("TMD-9344", "10-Wheeler Truck", "Attached", "Isuzu", "FVZ 34", "Bismillah Goods Carrier"),
]

TRANSPORTERS = [
	"Al-Madina Goods Transport",
	"Shaheen Carriers",
	"Pak Sohni Transport",
	"Bismillah Goods Carrier",
]

CUSTOMERS = [
	("Lucky Cement Ltd", "Karachi"),
	("Engro Fertilizers Ltd", "Karachi"),
	("Nishat Textile Mills", "Faisalabad"),
	("Tariq Glass Industries", "Lahore"),
	("Pak Steel Traders", "Karachi"),
	("Unilever Pakistan Ltd", "Karachi"),
	("Fauji Foods Ltd", "Islamabad"),
]

# (full name, cell, licence, base salary PKR, is company driver)
DRIVERS = [
	("Muhammad Aslam", "0300-2214567", "SD-KHI-44821", 62000, True),
	("Ghulam Rasool", "0301-3345612", "SD-KHI-51203", 58000, True),
	("Zafar Iqbal", "0302-4456789", "SD-LHR-33471", 60000, True),
	("Allah Ditta", "0333-5567890", "SD-MUL-29845", 55000, True),
	("Noor Muhammad", "0345-6678901", "SD-QTA-18732", 57000, True),
	("Sajid Hussain", "0321-7789012", "SD-KHI-60119", 59000, True),
	("Abdul Sattar", "0311-8890123", "SD-PSH-40255", 54000, True),
	("Rehmat Ali", "0308-9901234", "SD-KHI-71904", 0, False),
	("Karim Bakhsh", "0334-1012345", "SD-SUK-22660", 0, False),
]

# Cargo mix: (cargo item code, customer, description)
CARGO_MIX = [
	("CARGO-CEMENT", "Lucky Cement Ltd", "Ordinary Portland cement, 50 kg bags"),
	("CARGO-CHEMICALS", "Engro Fertilizers Ltd", "Urea fertiliser, bagged"),
	("CARGO-TEXTILE-GOODS", "Nishat Textile Mills", "Baled cotton yarn"),
	("CARGO-GENERAL", "Tariq Glass Industries", "Float glass crates, fragile"),
	("CARGO-STEEL-COIL", "Pak Steel Traders", "Hot rolled steel coils"),
	("CARGO-FOOD-PRODUCTS", "Unilever Pakistan Ltd", "Packaged food cartons"),
	("CARGO-CONTAINER", "Fauji Foods Ltd", "40-foot high-cube container"),
]
