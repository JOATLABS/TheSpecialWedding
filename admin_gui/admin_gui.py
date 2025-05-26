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

# Wedding selector
if 'selected_wedding' not in st.session_state:
    st.session_state.selected_wedding = None

# Get available weddings
wedding_options = {}
try:
    weddings_response = requests.get(f"{API_BASE_URL}/weddings")
    if weddings_response.status_code == 200:
        weddings = weddings_response.json()
        if weddings:
            wedding_options = {w['_id']: f"{w['couple_names']} ({w['date']})" for w in weddings}
            selected_wedding_id = st.sidebar.selectbox(
                "Select Wedding",
                options=list(wedding_options.keys()),
                format_func=lambda x: wedding_options[x]
            )
            st.session_state.selected_wedding = selected_wedding_id
        else:
            st.sidebar.warning("No weddings found. Create one first.")
except:
    st.sidebar.error("Failed to load weddings")

page = st.sidebar.radio("Navigate", ["Dashboard", "Wedding Management", "RSVP Management", "Import Guests", "Check-in Management", "Gallery Management", "SMS Reminders", "System Management"])

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
    email = st.text_input("Email", value=EMAIL if EMAIL else "", key="auth_email")
    password = st.text_input("Password", type="password", value=PASSWORD if PASSWORD else "", key="auth_password")

# Get JWT token for new endpoints
def get_jwt_token():
    try:
        # Get credentials from session state (from the text inputs)
        auth_email = st.session_state.get("auth_email", EMAIL)
        auth_password = st.session_state.get("auth_password", PASSWORD)
        
        response = requests.post(
            f"{API_BASE_URL}/admin/token",
            json={"email": auth_email, "password": auth_password}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            st.error(f"Auth failed: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        st.error(f"Auth error: {str(e)}")
        return None

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
    
    if st.session_state.selected_wedding:
        st.subheader(f"Wedding: {wedding_options.get(st.session_state.selected_wedding, 'Unknown')}")
    
    # Get RSVPs
    rsvps = get_rsvps()
    
    # Display stats
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Guests", len(rsvps))
    
    with col2:
        attending_count = sum(1 for r in rsvps if r.get('attending'))
        st.metric("Responses Received", attending_count)
    
    with col3:
        plus_ones = sum(1 for r in rsvps if r.get('plus_one'))
        st.metric("Plus Ones Registered", plus_ones)
    
    with col4:
        total_allowed = sum(r.get('number_of_plus_ones_allowed', 0) for r in rsvps)
        st.metric("Total Plus Ones Allowed", total_allowed)
    
    with col5:
        checked_in = sum(1 for r in rsvps if r.get('checked_in', False))
        st.metric("Checked In", checked_in)
    
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

elif page == "Wedding Management":
    st.header("Wedding Management")
    
    # Create new wedding
    with st.expander("Create New Wedding"):
        wedding_id = st.text_input("Wedding ID", placeholder="wedding_001")
        couple_names = st.text_input("Couple Names", placeholder="John & Jane")
        wedding_date = st.date_input("Main Wedding Date")
        slug = st.text_input("URL Slug", placeholder="john-jane-wedding")
        
        st.subheader("Events")
        num_events = st.number_input("Number of Events", min_value=1, max_value=5, value=3)
        
        events = []
        for i in range(num_events):
            col1, col2 = st.columns(2)
            with col1:
                event_type = st.selectbox(f"Event {i+1} Type", ["traditional", "white_wedding", "reception"], key=f"type_{i}")
            with col2:
                event_date = st.date_input(f"Event {i+1} Date", key=f"date_{i}")
            events.append({"type": event_type, "date": str(event_date)})
        
        if st.button("Create Wedding"):
            if wedding_id and couple_names and slug:
                wedding_data = {
                    "_id": wedding_id,
                    "couple_names": couple_names,
                    "date": str(wedding_date),
                    "slug": slug,
                    "events": events
                }
                response = requests.post(
                    f"{API_BASE_URL}/weddings",
                    auth=(email, password),  # Use Basic Auth like RSVP endpoints
                    json=wedding_data
                )
                if response.status_code == 200:
                    st.success("Wedding created successfully!")
                    st.rerun()
                else:
                    st.error(f"Failed to create wedding: {response.text}")
            else:
                st.warning("Please fill all required fields")
    
    # List existing weddings
    st.subheader("Existing Weddings")
    if st.button("Refresh Weddings"):
        st.rerun()
    
    try:
        response = requests.get(f"{API_BASE_URL}/weddings")
        if response.status_code == 200:
            weddings = response.json()
            if weddings:
                for wedding in weddings:
                    with st.expander(f"{wedding['couple_names']} - {wedding['date']}"): 
                        st.write(f"**ID:** {wedding['_id']}")
                        st.write(f"**Slug:** {wedding['slug']}")
                        st.write(f"**Events:**")
                        for event in wedding.get('events', []):
                            st.write(f"- {event['type']}: {event['date']}")
                        
                        if st.button(f"Delete {wedding['_id']}", key=f"del_{wedding['_id']}"):
                            del_response = requests.delete(
                                f"{API_BASE_URL}/weddings/{wedding['_id']}",
                                auth=(email, password)  # Use Basic Auth
                            )
                            if del_response.status_code == 200:
                                st.success("Wedding deleted")
                                st.rerun()
                            else:
                                st.error(f"Failed to delete: {del_response.text}")
            else:
                st.info("No weddings found")
        else:
            st.error("Failed to fetch weddings")
    except:
        st.error("Error loading weddings")

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
                "Plus One Allowed": "Yes" if r.get('plus_one_allowed') else "No",
                "# Plus Ones Allowed": r.get('number_of_plus_ones_allowed', 0),
                "Plus One Submitted": "Yes" if r.get('plus_one_submitted') else "No",
                "Checked In": "Yes" if r.get('checked_in') else "No"
            }
            if r.get('plus_one'):
                row["Plus One Name"] = r['plus_one'].get('name', '')
                row["Plus One Dietary"] = r['plus_one'].get('dietary', 'None')
            data.append(row)
        
        df = pd.DataFrame(data)
        st.dataframe(df)

elif page == "Import Guests":
    st.header("Import Guests")
    
    wedding_id = st.text_input("Wedding ID", value=st.session_state.selected_wedding or "wedding_001")
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
                
    st.info("CSV must contain: name (required), phone OR email (at least one required for contact), role, plus_one_allowed, number_of_plus_ones_allowed, group_id")

elif page == "Check-in Management":
    st.header("Check-in Management")
    
    # Search for guest
    col1, col2 = st.columns(2)
    with col1:
        search_token = st.text_input("Guest Token", placeholder="Enter guest token")
    with col2:
        search_phone = st.text_input("Or Search by Phone", placeholder="Phone number")
    
    if search_token:
        # Check-in by token
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Check In Guest"):
                response = requests.post(
                    f"{API_BASE_URL}/admin/checkin/{search_token}",
                    auth=(email, password)
                )
                if response.status_code == 200:
                    st.success("Guest checked in successfully!")
                else:
                    st.error(f"Check-in failed: {response.text}")
        
        with col2:
            if st.button("Check Status"):
                response = requests.get(
                    f"{API_BASE_URL}/admin/checkin/status/{search_token}",
                    auth=(email, password)
                )
                    if response.status_code == 200:
                        data = response.json()
                        st.info(f"Check-in Status: {'Checked In' if data.get('checked_in') else 'Not Checked In'}")
                        if data.get('checked_in_at'):
                            st.info(f"Checked in at: {data['checked_in_at']}")
                    else:
                        st.error(f"Failed to get status: {response.text}")
                else:
                    st.error("Authentication failed")
    
    elif search_phone:
        # Search by phone
        response = requests.get(
            f"{API_BASE_URL}/guest/invite/search",
            params={"phone": search_phone}
        )
        if response.status_code == 200:
            guest = response.json()
            st.success(f"Found guest: {guest.get('name')}")
            st.info(f"Token: {guest.get('token')}")
        else:
            st.error("Guest not found")

elif page == "Gallery Management":
    st.header("Gallery Management")
    
    # Upload section
    st.subheader("Upload Photos")
    uploaded_file = st.file_uploader("Choose a photo", type=["jpg", "jpeg", "png", "gif"])
    
    if uploaded_file is not None:
        if st.button("Upload Photo"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            response = requests.post(
                f"{API_BASE_URL}/gallery/upload",
                auth=(email, password),
                files=files
            )
            if response.status_code == 200:
                st.success("Photo uploaded successfully!")
            else:
                st.error(f"Upload failed: {response.text}")
    
    # List uploaded files
    st.subheader("Uploaded Photos")
    if st.button("Refresh Gallery"):
        response = requests.get(
            f"{API_BASE_URL}/gallery/list",
            auth=(email, password)
        )
            if response.status_code == 200:
                files = response.json()
                if files:
                    for file in files:
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.text(file.get('Key', 'Unknown'))
                        with col2:
                            st.text(f"{file.get('Size', 0) / 1024:.1f} KB")
                        with col3:
                            if st.button("Delete", key=file.get('Key')):
                                del_response = requests.delete(
                                    f"{API_BASE_URL}/gallery",
                                    auth=(email, password),
                                    params={"key": file.get('Key')}
                                )
                                if del_response.status_code == 200:
                                    st.success("File deleted")
                                    st.rerun()
                else:
                    st.info("No photos uploaded yet")
            else:
                st.error("Failed to fetch gallery")
        else:
            st.error("Authentication failed")

elif page == "SMS Reminders":
    st.header("SMS Reminders")
    
    # Send reminders
    st.subheader("Send SMS Reminders")
    
    event_type = st.selectbox("Event Type", ["wedding", "pre_wedding", "custom"])
    target_group = st.selectbox("Target Group", ["all", "attending", "not_responded", "specific_tables"])
    
    message = st.text_area(
        "Message", 
        placeholder="Enter your reminder message...",
        help="Use {name} for guest name, {date} for event date, {location} for venue"
    )
    
    if st.button("Send Reminders"):
        if message:
            data = {
                "event_type": event_type,
                "message": message,
                "target_group": target_group
            }
            response = requests.post(
                f"{API_BASE_URL}/admin/reminders/send",
                auth=(email, password),
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                st.success(f"Sent {result.get('sent_count', 0)} reminders successfully!")
            else:
                st.error(f"Failed to send reminders: {response.text}")
        else:
            st.warning("Please enter a message")
    
    # View logs
    st.subheader("Reminder Logs")
    if st.button("View Logs"):
        response = requests.get(
            f"{API_BASE_URL}/admin/reminders/logs",
            auth=(email, password)
        )
            if response.status_code == 200:
                logs = response.json()
                if logs:
                    df = pd.DataFrame(logs)
                    st.dataframe(df)
                else:
                    st.info("No reminder logs found")
            else:
                st.error("Failed to fetch logs")
        else:
            st.error("Authentication failed")

elif page == "System Management":
    st.header("System Management")
    
    # Only allow if authenticated
    if not email or not password:
        st.warning("Please enter authentication credentials in the sidebar")
    else:
        try:
            import docker
            client = docker.from_env()
            
            # Container Management
            st.subheader("Docker Container Management")
            
            # Get wedding app containers
            containers = []
            for container in client.containers.list(all=True):
                if any(name in container.name for name in ['wedding-api', 'wedding-mongo', 'wedding-admin-gui']):
                    containers.append(container)
            
            if containers:
                for container in containers:
                    with st.expander(f"🐳 {container.name} - {container.status}"):
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            if container.status == 'running':
                                if st.button(f"Stop", key=f"stop_{container.id}"):
                                    container.stop()
                                    st.success(f"Stopped {container.name}")
                                    st.rerun()
                            else:
                                if st.button(f"Start", key=f"start_{container.id}"):
                                    container.start()
                                    st.success(f"Started {container.name}")
                                    st.rerun()
                        
                        with col2:
                            if st.button(f"Restart", key=f"restart_{container.id}"):
                                container.restart()
                                st.success(f"Restarted {container.name}")
                                st.rerun()
                        
                        with col3:
                            if st.button(f"View Logs", key=f"logs_{container.id}"):
                                st.session_state[f"show_logs_{container.id}"] = True
                        
                        with col4:
                            st.write(f"Status: {container.status}")
                        
                        # Show logs if requested
                        if st.session_state.get(f"show_logs_{container.id}", False):
                            st.subheader(f"Logs for {container.name}")
                            
                            # Log options
                            col1, col2 = st.columns(2)
                            with col1:
                                lines = st.slider("Number of lines", 10, 500, 100, key=f"lines_{container.id}")
                            with col2:
                                if st.button("Hide Logs", key=f"hide_logs_{container.id}"):
                                    st.session_state[f"show_logs_{container.id}"] = False
                                    st.rerun()
                            
                            # Get logs
                            try:
                                logs = container.logs(tail=lines).decode('utf-8')
                                st.code(logs, language='log')
                            except Exception as e:
                                st.error(f"Error fetching logs: {str(e)}")
            else:
                st.info("No wedding app containers found")
            
            # System Info
            st.subheader("System Information")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Containers", len(client.containers.list(all=True)))
            
            with col2:
                st.metric("Running Containers", len(client.containers.list()))
            
            with col3:
                st.metric("Docker Version", client.version()['Version'])
            
        except ImportError:
            st.error("Docker Python library not installed. Rebuilding container...")
        except Exception as e:
            st.error(f"Docker error: {str(e)}")
            st.info("Make sure Docker socket is accessible and you have permissions")