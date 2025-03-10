"""
Route Planner Streamlit App
This app reads customer data from a Google Sheet and optimizes routes for selected customers.
"""

import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from route_planner import RouteOptimizer

# Load environment variables
load_dotenv()

# Set page config for mobile-friendly design
st.set_page_config(
    page_title="Route Planner",
    page_icon="🗺️",
    layout="centered"
)

# Function to load data from Google Sheets
def load_customer_data(spreadsheet_key):
    try:
        # Define the scope
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']

        # Check if we have credentials
        if os.path.exists('service_account.json'):
            credentials = Credentials.from_service_account_file(
                'service_account.json', scopes=scope)
            gc = gspread.authorize(credentials)
            
            # Open the spreadsheet
            sh = gc.open_by_key(spreadsheet_key)
            
            # Get the first worksheet
            worksheet = sh.get_worksheet(0)
            
            # Get all records as a list of dictionaries
            records = worksheet.get_all_records()
            
            # Create dataframe
            df = pd.DataFrame(records)
            
            return df
        else:
            st.error("Service account credentials not found. Please upload 'service_account.json'.")
            return None
    except Exception as e:
        st.error(f"Error loading Google Sheet: {str(e)}")
        return None

# Function to upload service account JSON
def upload_service_account():
    st.subheader("Upload Service Account JSON")
    uploaded_file = st.file_uploader("Upload your Google Service Account JSON", type="json")
    if uploaded_file is not None:
        with open('service_account.json', 'wb') as f:
            f.write(uploaded_file.getbuffer())
        st.success("Service account JSON uploaded successfully!")
        st.rerun()

# App title and description
st.title("🗺️ Customer Route Planner")
st.markdown("Select customers and generate an optimized route")

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    
    # Get API key from environment or let user input
    default_api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    api_key = st.text_input("Google Maps API Key", 
                         value=default_api_key,
                         type="password",
                         help="Enter your Google Maps API key.")
    
    # Google Sheet Key
    spreadsheet_key = st.text_input(
        "Google Sheet Key", 
        help="Enter the key from your Google Sheet URL (the long string after /d/ and before /edit)"
    )
    
    # Starting address (home)
    home_address = st.text_input("Starting Address (Home)", value="24116 NE 27th PL sammamish WA")
    
    # Upload service account if needed
    if not os.path.exists('service_account.json'):
        upload_service_account()

# Main App Flow
if api_key and spreadsheet_key and home_address:
    # Load customer data
    with st.spinner("Loading customer data..."):
        df = load_customer_data(spreadsheet_key)
    
    if df is not None and not df.empty:
        # Check if the required columns exist
        required_columns = ["Name", "Address"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"Missing required columns in Google Sheet: {', '.join(missing_columns)}")
            st.info("Your Google Sheet must contain 'Name' and 'Address' columns.")
        else:
            # Display customer selection
            st.subheader("Select Customers to Visit")
            
            # Use a multiselect for better mobile experience
            selected_customers = st.multiselect(
                "Select customers",
                options=df["Name"].tolist(),
                help="Select one or more customers to visit"
            )
            
            # Filter dataframe for selected customers
            selected_df = df[df["Name"].isin(selected_customers)].copy()
            
            # Button to optimize route
            if st.button("Optimize Route", type="primary", use_container_width=True):
                if selected_customers:
                    with st.spinner("Calculating optimal route..."):
                        try:
                            # Get addresses for selected customers
                            destinations = selected_df["Address"].tolist()
                            
                            # Initialize the optimizer
                            optimizer = RouteOptimizer(api_key)
                            
                            # Optimize the route
                            result = optimizer.optimize_route(home_address, destinations)
                            
                            # Display results
                            st.success("Route optimization complete!")
                            
                            # Show route summary
                            st.subheader("Route Summary")
                            summary_data = {
                                "Starting Point": result['origin'],
                                "Total Distance": f"{result['total_distance_km']:.2f} km",
                                "Total Duration": f"{result['total_duration_mins']} minutes",
                                "Number of Stops": len(selected_customers)
                            }
                            st.write(pd.DataFrame([summary_data]))
                            
                            # Create optimized customer list
                            st.subheader("Customers in Optimized Order")
                            
                            # Create customer list with their addresses
                            customers_in_order = []
                            
                            # Add starting point
                            customers_in_order.append({
                                "Stop #": "Start",
                                "Location": "Home",
                                "Address": home_address,
                                "Distance": "-",
                                "Duration": "-"
                            })
                            
                            # Map optimized waypoints back to customer names
                            optimized_addresses = result['optimized_destinations']
                            address_to_name = dict(zip(selected_df["Address"], selected_df["Name"]))
                            
                            # Add customer stops
                            for i, address in enumerate(optimized_addresses):
                                # Find the matching waypoint for this address
                                waypoint_info = next((wp for wp in result['waypoints'] if wp['end_location'] == address), {})
                                
                                # Get distance and duration
                                distance = waypoint_info.get('distance_km', 0)
                                duration = waypoint_info.get('duration_mins', 0)
                                
                                # Get customer name
                                customer_name = address_to_name.get(address, "Unknown")
                                
                                customers_in_order.append({
                                    "Stop #": str(i + 1),  # Convert to string for consistency
                                    "Location": customer_name,
                                    "Address": address,
                                    "Distance": f"{distance:.2f} km",
                                    "Duration": f"{duration} mins"
                                })
                            
                            # Add return to home
                            customers_in_order.append({
                                "Stop #": "End",
                                "Location": "Home",
                                "Address": home_address,
                                "Distance": f"{result['waypoints'][-1]['distance_km']:.2f} km",
                                "Duration": f"{result['waypoints'][-1]['duration_mins']} mins"
                            })
                            
                            # Display as a table
                            st.dataframe(pd.DataFrame(customers_in_order))
                            
                            # Google Maps button
                            st.subheader("Open in Google Maps")
                            maps_url = result['google_maps_url']
                            st.markdown(f'<a href="{maps_url}" target="_blank"><button style="background-color:#4285F4; color:white; border:none; border-radius:10px; padding:15px; cursor:pointer; font-size:16px; width:100%;">Open in Google Maps</button></a>', unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            st.error("Make sure all addresses are valid and your API key has access to the required APIs.")
                else:
                    st.warning("Please select at least one customer.")
    else:
        st.error("Could not load data from the Google Sheet. Check your spreadsheet key and service account.")
else:
    # Show instructions if initial setup is not complete
    st.info("Please provide the required configuration in the sidebar:")
    st.markdown("""
    1. Enter your Google Maps API Key
    2. Enter the Google Sheet Key containing your customer data
    3. Enter your starting address
    4. Upload your service account JSON file if prompted
    """)
    
    # Show example of expected Google Sheet format
    st.subheader("Google Sheet Format")
    example_data = {
        "Name": ["John Doe", "Jane Smith", "Acme Corp", "Tech Solutions"],
        "Address": [
            "123 Main St, Seattle, WA", 
            "456 Oak Ave, Bellevue, WA", 
            "789 Pine St, Redmond, WA", 
            "321 Cedar Blvd, Kirkland, WA"
        ]
    }
    st.dataframe(pd.DataFrame(example_data))

# Footer
st.markdown("---")
st.caption("Powered by Google Maps APIs | Built with Streamlit") 