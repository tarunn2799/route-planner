# Customer Route Planner

A Streamlit app that helps optimize routes between multiple customer locations using Google Maps APIs.

## Features

- **Import customer data from Google Sheets**: Load customer names and addresses directly from a Google Spreadsheet
- **Select customers to visit**: Choose which customers to include in your route
- **Optimize route order**: Automatically determine the most efficient route between customer locations
- **Generate navigation link**: Open the optimized route directly in Google Maps for navigation

## Setup Instructions

### 1. Clone the repository

```bash
git clone <repository-url>
cd route-planner
```

### 2. Create a virtual environment (optional but recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up Google Cloud credentials

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the following APIs:
   - Google Maps Geocoding API
   - Google Maps Routes API
   - Google Sheets API
3. Create an API key for Google Maps APIs
4. Create a Service Account for Google Sheets access:
   - Go to "IAM & Admin" > "Service Accounts"
   - Create a new service account
   - Grant the necessary permissions (at least "Viewer" access to the spreadsheet)
   - Create and download a JSON key for the service account
   - Rename the downloaded file to `service_account.json` and place it in the project directory

### 5. Create a .env file

Create a `.env` file in the project directory with the following content:

```
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

### 6. Prepare your Google Sheet

Create a Google Sheet with at least the following columns:
- `Name`: Customer/location name
- `Address`: Full address of the customer/location

Share your Google Sheet with the email address of the service account created in step 4.

## Usage

1. Run the Streamlit app:

```bash
streamlit run app.py
```

2. Open the provided URL in your browser

3. In the app:
   - Enter your Google Sheet key (found in the sheet URL between /d/ and /edit)
   - Enter your starting address
   - Select the customers you want to visit
   - Click "Optimize Route"
   - View the optimized route and open in Google Maps for navigation

## Configuration

You can modify the following settings in the app:
- **Starting address**: Your home or starting point
- **Google Sheet key**: The key from your Google Sheet URL

## Requirements

- Python 3.7+
- Streamlit
- Pandas
- Google Maps client library
- Google Sheets API client library

See `requirements.txt` for all dependencies.

## License

[MIT License](LICENSE) 