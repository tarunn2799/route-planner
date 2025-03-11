"""
Route Planner Streamlit App
This app reads customer data from a Google Sheet and optimizes routes for selected customers.
"""

import streamlit as st
import pandas as pd
import os
import gspread
import numpy as np
from datetime import datetime, date
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

# Function to format date for sheet name (MMDDYYYY)
def format_date_for_sheet(selected_date):
    return selected_date.strftime("%m%d%Y")

# Function to load data from Google Sheets
def load_customer_data(spreadsheet_key, sheet_name):
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
            
            # Try to get the worksheet by name
            try:
                worksheet = sh.worksheet(sheet_name)
                st.success(f"Found sheet for {sheet_name}")
            except gspread.exceptions.WorksheetNotFound:
                st.error(f"Sheet for date {sheet_name} not found. Please check if the date is correct.")
                return None
            
            # Get all records as a list of dictionaries
            records = worksheet.get_all_records()
            
            # Create dataframe
            if records:
                df = pd.DataFrame(records)
                return df
            else:
                st.warning(f"No data found in sheet {sheet_name}")
                return None
        else:
            st.error("Service account credentials not found. Please upload 'service_account.json'.")
            return None
    except Exception as e:
        st.error(f"Error loading Google Sheet: {str(e)}")
        return None

# Function to process customer data
def process_customer_data(df):
    # Check if dataframe is not empty
    if df is None or df.empty:
        return None, None
    
    # Fixed columns (always present)
    fixed_columns = ['#', 'Name', 'Address', 'Phone Number', 'Notes']
    
    # Check if all required fixed columns exist
    missing_cols = [col for col in fixed_columns if col not in df.columns]
    if missing_cols:
        st.error(f"Missing required columns: {', '.join(missing_cols)}")
        return None, None
    
    # All columns after Notes are item columns
    item_columns = [col for col in df.columns if col not in fixed_columns]
    
    if not item_columns:
        st.warning("No item columns found in the sheet")
        return None, None
    
    # Filter rows where at least one item column has a non-NaN value
    # Convert columns to numeric where possible
    for col in item_columns:
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        except:
            # Keep as is if conversion fails
            pass
    
    # Check if at least one item column has a value
    item_mask = df[item_columns].notna().any(axis=1)
    customers_with_orders = df[item_mask].copy()
    
    if customers_with_orders.empty:
        st.warning("No customers with orders found for this date")
        return None, None
    
    # Check for missing addresses
    customers_missing_address = customers_with_orders[
        customers_with_orders['Address'].isna() | 
        (customers_with_orders['Address'] == '')
    ].copy()
    
    # Filter out customers with missing addresses
    valid_customers = customers_with_orders[
        customers_with_orders['Address'].notna() & 
        (customers_with_orders['Address'] != '')
    ].copy()
    
    return valid_customers, customers_missing_address

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
    
    # Date selector (default to today)
    selected_date = st.date_input(
        "Delivery Date",
        value=date.today(),
        help="Select the delivery date (sheet name will be formatted as MMDDYYYY)"
    )
    
    # Format date for sheet name
    sheet_name = format_date_for_sheet(selected_date)
    st.caption(f"Sheet name: {sheet_name}")
    
    # Starting address (home)
    home_address = st.text_input("Starting Address (Home)", value="24116 NE 27th PL sammamish WA")
    
    # Upload service account if needed
    if not os.path.exists('service_account.json'):
        upload_service_account()

# Main App Flow
if api_key and spreadsheet_key and home_address:
    # Load customer data
    with st.spinner(f"Loading customer data for {sheet_name}..."):
        df = load_customer_data(spreadsheet_key, sheet_name)
        
    if df is not None and not df.empty:
        # Process the data to get valid customers and those with missing addresses
        valid_customers, missing_address_customers = process_customer_data(df)
        
        if valid_customers is not None and not valid_customers.empty:
            # Display customer selection
            st.subheader("Select Customers to Visit")
            
            # Display count of customers with orders
            st.info(f"Found {len(valid_customers)} customers with orders for {selected_date.strftime('%B %d, %Y')}")
            
            # Use a multiselect for better mobile experience
            selected_customers = st.multiselect(
                "Select customers",
                options=valid_customers["Name"].tolist(),
                default=valid_customers["Name"].tolist(),  # Default to all customers
                help="Select one or more customers to visit"
            )
            
            # Show customers with missing addresses if any
            if missing_address_customers is not None and not missing_address_customers.empty:
                with st.expander(f"⚠️ {len(missing_address_customers)} Customers with Missing Addresses"):
                    st.warning("The following customers have orders but no delivery address:")
                    missing_address_df = missing_address_customers[['Name', 'Phone Number']]
                    st.dataframe(missing_address_df)
            
            # Filter dataframe for selected customers
            selected_df = valid_customers[valid_customers["Name"].isin(selected_customers)].copy()
            
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
                            
                            # Create customer list with their addresses and orders
                            customers_in_order = []
                            
                            # Add starting point
                            customers_in_order.append({
                                "Stop #": "Start",
                                "Location": "Home",
                                "Address": home_address,
                                "Phone": "-",
                                "Distance": "-",
                                "Duration": "-"
                            })
                            
                            # Map optimized waypoints back to customer names
                            optimized_addresses = result['optimized_destinations']
                            address_to_info = dict(zip(
                                selected_df["Address"],
                                zip(selected_df["Name"], selected_df["Phone Number"])
                            ))
                            
                            # Add customer stops
                            for i, address in enumerate(optimized_addresses):
                                # Find the matching waypoint for this address
                                waypoint_info = next((wp for wp in result['waypoints'] if wp['end_location'] == address), {})
                                
                                # Get distance and duration
                                distance = waypoint_info.get('distance_km', 0)
                                duration = waypoint_info.get('duration_mins', 0)
                                
                                # Get customer name and phone
                                customer_info = address_to_info.get(address, ("Unknown", "-"))
                                customer_name = customer_info[0]
                                customer_phone = customer_info[1]
                                
                                customers_in_order.append({
                                    "Stop #": str(i + 1),  # Convert to string for consistency
                                    "Location": customer_name,
                                    "Address": address,
                                    "Phone": customer_phone,
                                    "Distance": f"{distance:.2f} km",
                                    "Duration": f"{duration} mins"
                                })
                            
                            # Add return to home
                            customers_in_order.append({
                                "Stop #": "End",
                                "Location": "Home",
                                "Address": home_address,
                                "Phone": "-",
                                "Distance": f"{result['waypoints'][-1]['distance_km'] if result['waypoints'] else 0:.2f} km",
                                "Duration": f"{result['waypoints'][-1]['duration_mins'] if result['waypoints'] else 0} mins"
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
            st.error(f"No valid customers with orders and addresses found for {selected_date.strftime('%B %d, %Y')}")
    else:
        st.error(f"Could not load data from the Google Sheet for {sheet_name}. Check your spreadsheet key and service account.")
else:
    # Show instructions if initial setup is not complete
    st.info("Please provide the required configuration in the sidebar:")
    st.markdown("""
    1. Enter your Google Maps API Key
    2. Enter the Google Sheet Key containing your customer data
    3. Select the delivery date (sheet name will be in format MMDDYYYY)
    4. Enter your starting address
    5. Upload your service account JSON file if prompted
    """)
    
    # Show example of expected Google Sheet format
    st.subheader("Expected Google Sheet Format")
    example_data = {
        "#": [1, 2, 3, 4],
        "Name": ["John Doe", "Jane Smith", "Acme Corp", "Tech Solutions"],
        "Address": [
            "123 Main St, Seattle, WA", 
            "456 Oak Ave, Bellevue, WA", 
            "789 Pine St, Redmond, WA", 
            "321 Cedar Blvd, Kirkland, WA"
        ],
        "Phone Number": ["206-555-1234", "425-555-5678", "425-555-9012", "206-555-3456"],
        "Notes": ["", "Delivery instructions", "", "Leave at door"],
        "Veg Paniyaram": [1, 2, "", 1],
        "Paneer Paratha": [2, "", 1, ""],
        "Sambar": ["", 1, 2, 1],
    }
    st.dataframe(pd.DataFrame(example_data))

# Footer
st.markdown("---")
st.caption("Powered by Google Maps APIs | Built with Streamlit") 