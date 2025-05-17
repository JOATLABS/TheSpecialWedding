import streamlit as st
import pandas as pd
import requests
import io
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# In Docker networking, 'api' is the service name defined in docker-compose.all.yml
# This allows containers to communicate with each other
API_BASE_URL = "http://api:8000" if os.environ.get("DOCKER_ENV") == "true" else "http://localhost:8000"
EMAIL = os.getenv("PRIMARY_ADMIN_EMAIL")
PASSWORD = os.getenv("PRIMARY_ADMIN_PASSWORD")

# Page config
st.set_page_config(page_title="Wedding Admin", layout="wide")

# Main title
st.title("Wedding Web App Admin")

# Sidebar
st.sidebar.title("Admin Menu")
page = st.sidebar.radio("Navigate", ["Dashboard", "RSVP Management", "Import Guests"])

# Check API Connection
try:
    health_resp = requests.get(f"{API_BASE_URL}/health/")
    if health_resp.status_code == 200 and health_resp.json().get("status") == "ok":
        st.sidebar.success("API Connected")
    else:
        st.sidebar.error("API Connection Error")
except:
    st.sidebar.error("API Connection Failed")

# Basic auth credentials
with st.sidebar.expander("Authentication"):
    email = st.text_input("Email", value=EMAIL if EMAIL else "")
    password = st.text_input("Password", type="password", value=PASSWORD if PASSWORD else "")

# Function to get all RSVPs
def get_rsvps():
    try:
        response = requests.get(
            f"{API_BASE_URL}/admin/rsvps",
            auth=(email, password)
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch RSVPs: Status {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Error fetching RSVPs: {str(e)}")
        return []

# Function to import guests
def import_guest_csv(file, wedding_id):
    try:
        files = {"file": file}
        params = {"wedding_id": wedding_id}
        response = requests.post(
            f"{API_BASE_URL}/admin/guests/import",
            params=params,
            files=files,
            auth=(email, password)
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Import failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

# Function to export RSVPs
def export_rsvps_csv():
    try:
        response = requests.get(
            f"{API_BASE_URL}/admin/rsvps/export",
            auth=(email, password)
        )
        if response.status_code == 200:
            return response.content
        else:
            st.error(f"Export failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

# Page content
if page == "Dashboard":
    st.header("Dashboard")
    
    # Get RSVPs
    rsvps = get_rsvps()
    
    # Display stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Guests", len(rsvps))
    
    with col2:
        attending_count = sum(1 for r in rsvps if r.get('attending'))
        st.metric("Responses Received", attending_count)
    
    with col3:
        plus_ones = sum(1 for r in rsvps if r.get('plus_one'))
        st.metric("Plus Ones", plus_ones)
    
    # Export button
    if st.button("Export RSVPs to CSV"):
        csv_data = export_rsvps_csv()
        if csv_data:
            st.download_button(
                "Download CSV", 
                csv_data, 
                "wedding_rsvps.csv", 
                "text/csv"
            )

elif page == "RSVP Management":
    st.header("RSVP Management")
    
    # Get RSVPs
    rsvps = get_rsvps()
    
    if not rsvps:
        st.info("No RSVPs found")
    else:
        # Convert to DataFrame
        data = []
        for r in rsvps:
            row = {
                "Name": r.get('name', 'Unknown'),
                "Email/Phone": r.get('phone', ''),
                "Attending": ', '.join(r.get('attending', [])),
                "Dietary": r.get('dietary', 'None'),
            }
            if r.get('plus_one'):
                row["Plus One"] = r['plus_one'].get('name', '')
                row["Plus One Dietary"] = r['plus_one'].get('dietary', 'None')
            data.append(row)
        
        df = pd.DataFrame(data)
        st.dataframe(df)

elif page == "Import Guests":
    st.header("Import Guests")
    
    wedding_id = st.text_input("Wedding ID", "wedding1")
    uploaded_file = st.file_uploader("Upload CSV", type="csv")
    
    if uploaded_file is not None:
        # Preview the CSV
        df = pd.read_csv(uploaded_file)
        st.subheader("Preview")
        st.dataframe(df.head())
        
        # Import button
        if st.button("Import Guests"):
            uploaded_file.seek(0)  # Reset file pointer
            result = import_guest_csv(uploaded_file, wedding_id)
            if result:
                st.success(f"Successfully imported {result.get('imported_count', 0)} guests.")
                
    st.info("CSV should contain columns: name, email, phone, table_number")