import base64
import numpy as np
import pytesseract
from django.contrib import messages
from django.shortcuts import render
from PIL import Image
import re
from datetime import datetime
import qrcode
import io
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse

# Set the path to Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_aadhaar_info(text):
    # Define patterns to extract information from Aadhaar card
    aadhaar_patterns = {
        "aadhaar_no": r"Your Aadhaar No\.\s*:\s*([0-9\s]*)",
        "dob": r"DOB:\s*([0-9/]+)"
    }
    info = {}

    # Extract Aadhaar number and DOB using defined patterns
    for key, pattern in aadhaar_patterns.items():
        match = re.search(pattern, text)
        if match:
            info[key] = match.group(1).strip()

    # Extract name using provided regular expression
    name_match_aadhaar = re.search(r'To\s*([^\s]+ [A-Z].+)', text)
    if name_match_aadhaar:
        info['name'] = name_match_aadhaar.group(1).strip()

    return info

def extract_pan_info(text):
    # Define patterns to extract information from PAN card
    pan_patterns = {
        "pan": r"Permanent Account Number Card\s*([A-Z0-9]+)"
    }
    
    info = {}

    # Extract PAN information using defined patterns
    for key, pattern in pan_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info[key] = match.group(1).strip()

    # Extract name using provided regular expression
    name_match_pan = re.search(r'Name\s*([^\s]+ [A-Z].+)', text, re.IGNORECASE)
    if name_match_pan:
        info['name'] = name_match_pan.group(1).strip()

    # Extract date of birth using date pattern
    date_pattern = re.compile(r'\b(\d{1,2}[/]\d{1,2}[/]\d{4})\b')
    dates = date_pattern.findall(text)
    if dates:
        # Convert dates to datetime objects to find the most probable one
        dob_candidates = [datetime.strptime(date, '%d/%m/%Y') for date in dates]
        # Select the most recent date as date of birth
        info['dob'] = max(dob_candidates).strftime('%d/%m/%Y')

    return info

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert PIL image to base64 encoded string
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

def calculate_age(dob):
    today = datetime.now()
    dob = datetime.strptime(dob, "%d/%m/%Y")
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age

def validate_phone_number(phone):
    if not phone.isdigit() or len(phone) != 10:
        raise ValidationError("Invalid phone number")

def age_restriction(request):
    return render(request, "age_restriction.html")

def invalid_phone(request):
    return render(request, "invalid_phone.html")

def homepage(request):
    if request.method == "POST":
        try:
            image = request.FILES.get("imagefile")
            lang = request.POST.get("language")
            img = np.array(Image.open(image))
            text = pytesseract.image_to_string(img, lang=lang)

            # Fetch user input from form
            phone = request.POST.get("phone")
            
            # Extract date of birth from Aadhaar text
            date_pattern = re.compile(r'\b(\d{1,2}[/]\d{1,2}[/]\d{4})\b')
            dob_matches = date_pattern.findall(text)
            if not dob_matches:
                raise ValueError("Please provide date of birth")

            dob = max(dob_matches)  # Choose the latest date as date of birth

            # Validate phone number
            validate_phone_number(phone)
            
            age = calculate_age(dob)
            if age < 18:
                return age_restriction(request)

            # Get current date and time
            current_date_time = datetime.now()
            date = current_date_time.strftime("%d/%m/%Y")
            time = current_date_time.strftime("%H:%M:%S")

            # Check if the text contains Aadhaar or PAN information
            if "Aadhaar" in text:
                info = extract_aadhaar_info(text)
                template = "aadhaar_output.html"
            elif "INCOME TAX DEPARTMENT" in text:
                info = extract_pan_info(text)
                if age < 18:  # Age restriction for PAN card
                    raise ValueError("You must be at least 25 years old for PAN card")
                template = "pan_output.html"
            else:
                raise ValueError("Unknown card type")

            # Generate QR code
            qr_code = generate_qr_code("VisiOCR")

            info['phone'] = phone
            info['age'] = age
            info['date'] = date
            info['time'] = time
            info['qr_code'] = qr_code

            return render(request, template, info)
        
        except ValidationError:
            return invalid_phone(request)
        except ValueError as e:
            messages.add_message(request, messages.ERROR, str(e))
            return render(request, "home.html")

    return render(request, "home.html")
