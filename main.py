from flask import Flask, request, jsonify
import pytesseract
from PIL import Image
import re
from pyzbar.pyzbar import decode
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from io import BytesIO
from flask_cors import CORS
import json
from pdf2image import convert_from_path
import os
import tempfile

app = Flask(__name__)
CORS(app)

# Set the Tesseract executable path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

@app.route('/validate-certificate', methods=['POST'])
def validate_certificate():
    try:
        # Get the uploaded file and predefined details
        file = request.files['certificate']
        predefined_details = request.form.get('predefined_details')
        # print("Predefined Details (raw):", predefined_details)

        # Parse predefined details as JSON
        predefined_details = json.loads(predefined_details)
        # print("Predefined Details (parsed):", predefined_details)

        # Determine the file type and load the image(s)
        if file.filename.lower().endswith('.pdf'):
            # Save the PDF to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(file.read())
                temp_pdf_path = temp_pdf.name
            # Convert PDF to images
            images = convert_from_path(temp_pdf_path)
            # Remove the temporary file
            os.remove(temp_pdf_path)
        else:
            # Load the image directly
            images = [Image.open(file.stream)]

        extracted_text = ""
        for image in images:
            # Perform OCR
            extracted_text += pytesseract.image_to_string(image)
        # print("Extracted Text:\n", extracted_text)

        # Compare extracted text with predefined details
        extracted_data = {}
        reasons = []
        for key, predefined_value in predefined_details.items():
            # print(f"Searching for {key}: {predefined_value}")
            pattern = re.escape(predefined_value)
            match = re.search(pattern, extracted_text, re.IGNORECASE)
            if match:
                extracted_data[key] = match.group(0).strip().lower()
            else:
                # Extract the closest match or relevant data for provided value
                closest_match = re.search(r'\b' + key + r'\b.*?(\d+)', extracted_text, re.IGNORECASE)
                provided_value = closest_match.group(1) if closest_match else 'None'
                extracted_data[key] = provided_value
                reasons.append(f"{key} does not match the predefined value. Expected: '{predefined_value}', Provided: '{provided_value}'")
        
        # If there are reasons, return rejected status
        if reasons:
            # print("Reasons for rejection:", reasons)
            return jsonify({'status': 'rejected', 'reasons': reasons})

        # Check for QR code
        qr_results = {}
        for image in images:
            qr_codes = decode(image)
            if qr_codes:
                qr_data = qr_codes[0].data.decode('utf-8')
                qr_results['qr_data'] = qr_data
                # print("QR Code Data:", qr_data)

                # Fetch and analyze QR URL
                try:
                    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
                    driver.get(qr_data)
                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                    img_tag = soup.find('img')
                    if img_tag and 'src' in img_tag.attrs:
                        img_url = img_tag['src']
                        driver.get(img_url)
                        screenshot_path = 'screenshot.png'
                        driver.save_screenshot(screenshot_path)
                        driver.quit()

                        # Perform OCR on the screenshot
                        screenshot_image = Image.open(screenshot_path)
                        qr_extracted_text = pytesseract.image_to_string(screenshot_image)
                        qr_extracted_text = qr_extracted_text.replace(',', '.')  # Replace all commas with dots
                        qr_results['qr_extracted_text'] = qr_extracted_text
                        # print("Extracted Text from QR Code URL Image:\n", qr_extracted_text)

                        # Compare the extracted text from the QR code URL with predefined details
                        for key, predefined_value in predefined_details.items():
                            if predefined_value.lower() not in qr_extracted_text.lower():
                                reasons.append(f"{key} from QR code does not match the predefined value. Expected: '{predefined_value}', Provided: '{qr_extracted_text}'")
                    else:
                        qr_results['error'] = 'No image tag found in the HTML.'
                except Exception as e:
                    qr_results['error'] = str(e)

        # If there are reasons, return rejected status
        if reasons:
            # print("Reasons for rejection after QR code check:", reasons)
            return jsonify({'status': 'rejected', 'reasons': reasons})

        # Prepare response
        response = {
            'extracted_data': extracted_data,
            'qr_results': qr_results,
            'status': 'success'
        }
        # print("Response:", response)
        return jsonify(response)

    except Exception as e:
        # print("Error:", str(e))
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
