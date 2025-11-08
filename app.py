import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from docxtpl import DocxTemplate
from io import BytesIO
import openpyxl
import datetime
import requests 
import google.generativeai as genai 

# --- 1. SET UP PAGE CONFIGURATION ---
st.set_page_config(
    page_title="TruKKer Quoting Tool",
    page_icon="🚚",
    layout="wide"
)

# --- 2. GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def get_gspread_client():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["google_credentials"], scopes=scopes
    )
    client = gspread.authorize(creds)
    return client

# --- 3. LOAD DATA FUNCTIONS (WITH NEW CLEANING) ---
@st.cache_data(ttl=600)
def load_data(_client):
    try:
        sheet_name = "price_list"
        spreadsheet = _client.open(sheet_name)
        worksheet = spreadsheet.worksheet("Sheet1") # Your price list tab
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            return pd.DataFrame()
            
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        df.columns = df.columns.str.strip() # Clean headers too
        
        if 'Price' in df.columns:
            df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"An error occurred while loading price_list data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_rates(_client):
    try:
        sheet_name = "price_list"
        spreadsheet = _client.open(sheet_name)
        worksheet = spreadsheet.worksheet("rate_list") # Your new rate card tab
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            return pd.DataFrame(columns=['Truck_Type', 'Rate_per_KM', 'Currency'])
            
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        df.columns = df.columns.str.strip() # Clean headers too
        
        if 'Rate_per_KM' in df.columns:
            df['Rate_per_KM'] = pd.to_numeric(df['Rate_per_KM'], errors='coerce')
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error("Error: 'rate_list' tab not found in your Google Sheet. Estimation is disabled.")
        return pd.DataFrame(columns=['Truck_Type', 'Rate_per_KM', 'Currency'])
    except Exception as e:
        st.error(f"An error occurred while loading rate_list data: {e}")
        return pd.DataFrame(columns=['Truck_Type', 'Rate_per_KM', 'Currency'])

@st.cache_data(ttl=600)
def load_distance_cache(_client):
    try:
        sheet_name = "price_list"
        spreadsheet = _client.open(sheet_name)
        worksheet = spreadsheet.worksheet("distance_cache") # Your new cache tab
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            df = pd.DataFrame(columns=['From_Country', 'From_City', 'To_Country', 'To_City', 'Distance_KM'])
        
        df.columns = df.columns.str.strip()
        
        if 'Distance_KM' in df.columns:
            df['Distance_KM'] = pd.to_numeric(df['Distance_KM'], errors='coerce')
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error("Error: 'distance_cache' tab not found in your Google Sheet. Cache is disabled.")
        return pd.DataFrame(columns=['From_Country', 'From_City', 'To_Country', 'To_City', 'Distance_KM'])
    except Exception as e:
        st.error(f"An error occurred while loading distance_cache data: {e}")
        return pd.DataFrame(columns=['From_Country', 'From_City', 'To_Country', 'To_City', 'Distance_KM'])

@st.cache_data(ttl=600)
def load_client_summary_cache(_client):
    try:
        sheet_name = "price_list"
        spreadsheet = _client.open(sheet_name)
        worksheet = spreadsheet.worksheet("client_summary_cache") # Your new cache tab
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            df = pd.DataFrame(columns=['Client_Company_Name', 'Summary_Text'])
        
        df.columns = df.columns.str.strip()
        
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error("Error: 'client_summary_cache' tab not found in your Google Sheet. AI Cache is disabled.")
        return pd.DataFrame(columns=['Client_Company_Name', 'Summary_Text'])
    except Exception as e:
        st.error(f"An error occurred while loading client_summary_cache data: {e}")
        return pd.DataFrame(columns=['Client_Company_Name', 'Summary_Text'])

# --- THIS IS NEW: LOAD T&Cs ---
@st.cache_data(ttl=600)
def load_terms(_client):
    try:
        sheet_name = "price_list"
        spreadsheet = _client.open(sheet_name)
        worksheet = spreadsheet.worksheet("terms_list") # Your new T&C tab
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            df = pd.DataFrame(columns=['From_Country', 'To_Country', 'Terms_Text'])
        
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        df.columns = df.columns.str.strip()
        
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error("Error: 'terms_list' tab not found in your Google Sheet. Default T&Cs will be used.")
        return pd.DataFrame(columns=['From_Country', 'To_Country', 'Terms_Text'])
    except Exception as e:
        st.error(f"An error occurred while loading T&Cs data: {e}")
        return pd.DataFrame(columns=['From_Country', 'To_Country', 'Terms_Text'])

# --- 4. FUNCTION TO GET LOG SHEET ---
@st.cache_resource
def get_log_sheet(_client):
    try:
        spreadsheet = _client.open("price_list")
        log_sheet = spreadsheet.worksheet("request_log")
        return log_sheet
    except Exception as e:
        st.error(f"Error connecting to log sheet: {e}")
        return None

# --- 5. CACHE-SAVING FUNCTIONS ---
def save_to_distance_cache(client, row_data):
    try:
        spreadsheet = client.open("price_list")
        cache_sheet = spreadsheet.worksheet("distance_cache")
        cache_sheet.append_row(row_data)
        load_distance_cache.clear()
    except Exception as e:
        st.warning(f"Failed to save to distance cache: {e}")

def save_to_client_summary_cache(client, row_data):
    try:
        spreadsheet = client.open("price_list")
        cache_sheet = spreadsheet.worksheet("client_summary_cache")
        cache_sheet.append_row(row_data)
        load_client_summary_cache.clear()
    except Exception as e:
        st.warning(f"Failed to save to AI summary cache: {e}")

# --- 6. AI & ESTIMATION FUNCTIONS ---
def configure_gemini(api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-flash-latest') 
    return model

@st.cache_data(ttl=3600)
def get_ai_client_summary(_model, company_name):
    if not company_name:
        return "Client details as provided by user."
    try:
        prompt = f"Briefly summarize the company '{company_name}' in 2-3 professional lines, focusing on their industry."
        response = _model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.warning(f"AI client summary failed: {e}")
        return "Client details as provided by user."

COUNTRY_MAP = {
    "UAE": "United Arab Emirates",
    "KSA": "Saudi Arabia",
    "Oman": "Oman",
    "Bahrain": "Bahrain",
    "Jordan": "Jordan",
    "Egypt": "Egypt",
    "Qatar": "Qatar",
    "Kuwait": "Kuwait"
}

@st.cache_data(ttl=3600)
def get_driving_distance(from_city, from_country, to_city, to_country, api_key):
    try:
        geocode_base_url = "https://api.geoapify.com/v1/geocode/search"
        
        full_from_country = COUNTRY_MAP.get(from_country, from_country)
        full_to_country = COUNTRY_MAP.get(to_country, to_country)
        
        geocode_params_from = {
            "text": f"{from_city}, {full_from_country}",
            "apiKey": api_key
        }
        resp_from = requests.get(geocode_base_url, params=geocode_params_from)
        resp_from.raise_for_status()
        data_from = resp_from.json()

        geocode_params_to = {
            "text": f"{to_city}, {full_to_country}",
            "apiKey": api_key
        }
        resp_to = requests.get(geocode_base_url, params=geocode_params_to)
        resp_to.raise_for_status()
        data_to = resp_to.json()
        
        if not data_from.get("features") or not data_to.get("features"):
            st.error("Could not find coordinates for one or more cities. Check spelling.")
            return None

        from_lon, from_lat = data_from["features"][0]["geometry"]["coordinates"]
        to_lon, to_lat = data_to["features"][0]["geometry"]["coordinates"]

        routing_base_url = "https://api.geoapify.com/v1/routing"
        routing_params = {
            "waypoints": f"{from_lat},{from_lon}|{to_lat},{to_lon}",
            "mode": "drive", "format": "json", "apiKey": api_key
        }
        resp_matrix = requests.get(routing_base_url, params=routing_params)
        resp_matrix.raise_for_status()
        data_matrix = resp_matrix.json()

        results = data_matrix.get("results")
        if not results: return None
        route = results[0]
        distance_meters = route.get("distance")
        if distance_meters is None: return None
        distance_km = distance_meters / 1000
        return round(distance_km, 2)
    except Exception as e:
        st.error(f"Error during geocoding: {e}")
        return None

# Load all data
client = get_gspread_client()
df = load_data(client)
rates_df = load_rates(client) 
distance_cache_df = load_distance_cache(client) 
client_summary_cache_df = load_client_summary_cache(client)
terms_df = load_terms(client) # <-- NEW
log_sheet = get_log_sheet(client)

# --- THIS IS THE FIX: A new callback function ---
def update_terms():
    # Get current values from session state using their keys
    from_country = st.session_state.single_from_country
    to_country = st.session_state.single_to_country
    
    # Perform the lookup
    default_terms_text = "1. Price is valid for 7 days. 2. Standard T&Cs apply." # Fallback
    if not terms_df.empty:
        terms_lookup = terms_df[
            (terms_df['From_Country'] == from_country) &
            (terms_df['To_Country'] == to_country)
        ]
        if not terms_lookup.empty:
            default_terms_text = terms_lookup.iloc[0]['Terms_Text']
        else:
            # If no specific match, find the DEFAULT
            default_lookup = terms_df[terms_df['From_Country'] == 'DEFAULT']
            if not default_lookup.empty:
                default_terms_text = default_lookup.iloc[0]['Terms_Text']
    
    # Programmatically update the session state for the text area
    st.session_state.single_terms = default_terms_text

# --- 7. BUILD THE USER INTERFACE (UI) ---

st.title("🚚 TruKKer Internal Quoting Tool")
st.markdown("---")

tab1, tab2 = st.tabs(["Single Lane Quote", "Batch Excel Upload"])

# --- THIS IS THE FIX: Initialize Session State for T&Cs ---
if 'single_terms' not in st.session_state:
    default_terms_text = "1. Price is valid for 7 days. 2. Standard T&Cs apply."
    if not terms_df.empty:
        # On first load, find T&Cs for UAE -> UAE (or default)
        terms_lookup = terms_df[
            (terms_df['From_Country'] == 'UAE') &
            (terms_df['To_Country'] == 'UAE')
        ]
        if not terms_lookup.empty:
            default_terms_text = terms_lookup.iloc[0]['Terms_Text']
        else:
            default_lookup = terms_df[terms_df['From_Country'] == 'DEFAULT']
            if not default_lookup.empty:
                default_terms_text = default_lookup.iloc[0]['Terms_Text']
    st.session_state.single_terms = default_terms_text

# --- TAB 1: SINGLE QUOTE ---
with tab1:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("Step 1: Enter Request Details")
        
        # --- Client Details ---
        st.subheader("Client Details")
        req_client_type = st.radio("Client Type", ("Existing Client", "New Client"), key="single_client_type")
        
        req_client_company_name = ""
        req_client_contact_name = ""
        req_client_contact_email = ""
        req_client_contact_phone = ""
        
        if req_client_type == "Existing Client":
            req_client_company_name = st.text_input("Client Company Name", key="single_company")
            req_client_contact_name = st.text_input("Client Employee Name", key="single_contact_name")
        else: # New Client
            req_client_company_name = st.text_input("New Client Company Name", key="single_new_company") 
            req_client_contact_name = st.text_input("New Client Contact Name", key="single_new_name")
            req_client_contact_email = st.text_input("New Client Email", key="single_new_email")
            req_client_contact_phone = st.text_input("New Client Phone", key="single_new_phone")
        
        st.markdown("---")
        
        # --- Lane Details ---
        st.subheader("Lane Details")
        if df.empty or rates_df.empty:
            st.warning("Could not load price data or rate data. Check Google Sheet tabs.")
        else:
            country_list = ["UAE", "KSA", "Oman", "Bahrain", "Jordan", "Egypt", "Qatar", "Kuwait"]
            
            # --- THIS IS THE FIX: Add on_change callback ---
            req_from_country = st.selectbox("From Country", country_list, 
                                        key="single_from_country",
                                        on_change=update_terms)
            req_to_country = st.selectbox("To Country", country_list, 
                                        key="single_to_country",
                                        on_change=update_terms)
            
            req_from_city = st.text_input("From City", key="single_from_city")
            req_to_city = st.text_input("To City", key="single_to_city")
            
            truck_list = [
                "Box - 2 Axle 12M", "Flatbed - 2 Axle 12M", "Flatbed - 3 Axle 12M", "Lorry 5 Ton", "Lowbed - 3 Axle 15 M",
                "Box - 2 Axle 13.6M", "Flatbed - 2 Axle 13.6M", "Flatbed - 3 Axle 13.6M", "Lorry 7 Ton", "Lowbed 3 Axle 12.9M",
                "Box - 2 Axle 15M", "Flatbed - 2 Axle 15M", "Flatbed - 3 Axle 15M", "Dyna 5 Ton", "Lowbed 3 Axle 12M",
                "Box - 3 Axle 12M", "Flatbed - 2 Axle 18M", "Flatbed - 3 Axle 18M", "Dyna 7 Ton", "Lowbed 3 Axle 13.6M",
                "Box - 3 Axle 13.6M", "Flatbed - 2 Axle 24M", "Flatbed - 3 Axle 24M", "Side Grill 1 Ton", "Lowbed 3 Axle 14M",
                "Box - 3 Axle 15M", "Flatbed SideGrill - 2 Axle 12M", "Flatbed 13.6M", "Side Grill 10 Ton", "Lowbed 4 Axle 16M",
                "Box 10 Ton", "Flatbed SideGrill - 2 Axle 13.6M", "Flatbed SideGrill - 3 Axle 12M", "Side Grill 3 Ton", "Lowbed 5 Axle 17M",
                "Box 3 Ton", "Flatbed SideGrill - 2 Axle 15M", "Flatbed SideGrill - 3 Axle 13.6M", "Side Grill 4.2 Ton", "Lowbed 8 Axle 16M",
                "Box 4.2 Ton", "Lowbed 2 Axle 12.9M", "Flatbed SideGrill - 3 Axle 15M", "Side Grill 5 Ton", "Reefer 10 Ton",
                "Tipper 12M", "Reefer - 2 Axle 13.6M", "Curtain Side - 3 Axle 13.6M", "Side Grill 7 Ton", "Reefer 3 Ton",
                "Tipper 2 Axle", "Curtain Side - 2 Axle 10 Ton", "Curtain Side - 3 Axle 15M", "Curtain Side - 2 Axle 15M",
                "Tipper 3 Axle", "Curtain Side - 2 Axle 13.6M", "Reefer - 3 Axle 13.6M"
            ]
            req_truck_type = st.selectbox("Truck Type", truck_list, key="single_truck_type")
            
            currency_list = rates_df['Currency'].unique()
            req_currency = st.selectbox("Desired Currency", currency_list, key="single_currency")
            
            st.markdown("---")
            st.subheader("Quote Details")
            req_prepared_by = st.text_input("Quote Prepared by:", key="single_prepared_by")
            
            st.subheader("Custom Text (for Word Doc)")
            st.info("The 'Client Company Summary' will be auto-generated or pulled from cache.")
            req_scope_summary = st.text_area("Understanding of Scope (Manual)", 
                f"Standard {req_truck_type} transport from {req_from_city} to {req_to_city}.")

            st.markdown("---") 
            req_client_ops = st.text_area("Client Operations Description (Manual)", "...", key="single_client_ops")
            
            # --- THIS IS THE FIX: We just use the key. The value is set by the callback. ---
            req_terms = st.text_area("Applicable Terms & Conditions", 
                key="single_terms",
                height=150)
            
            lookup_button = st.button("Generate Quote / Estimate", type="primary", key="single_button")

    with col2:
        st.header("Step 2: Generated Quote")
        
        if 'lookup_button' in locals() and lookup_button:
            if df.empty or not all([req_from_city, req_to_city, req_prepared_by, req_from_country, req_to_country]):
                st.warning("Please fill in all details (Client, Lane, and Prepared by).")
            else:
                gemini_api_key = st.secrets.get("gemini_api_key")
                client_company_summary = "Client details as provided by user." 
                
                if gemini_api_key and req_client_company_name:
                    cache_result = client_summary_cache_df[
                        client_summary_cache_df['Client_Company_Name'].str.lower() == req_client_company_name.lower()
                    ]
                    
                    if not cache_result.empty:
                        client_company_summary = cache_result.iloc[0]['Summary_Text']
                        st.info("AI client summary found in cache.")
                    else:
                        st.warning("Client summary not in cache. Calling AI API...")
                        ai_model = configure_gemini(gemini_api_key)
                        with st.spinner("Generating AI Client Summary..."):
                            client_company_summary = get_ai_client_summary(ai_model, req_client_company_name)
                            cache_data = [req_client_company_name, client_company_summary]
                            save_to_client_summary_cache(client, cache_data)
                            st.success("New summary saved to cache.")
                            
                elif gemini_api_key and not req_client_company_name:
                    st.info("No company name entered, skipping AI summary.")
                else:
                    st.warning("Gemini API key not found. AI summary will be disabled.")

                result = df[
                    (df['From_Country'].str.lower() == req_from_country.lower()) &
                    (df['To_Country'].str.lower() == req_to_country.lower()) &
                    (df['Truck_Type'] == req_truck_type) &
                    (df['From_City'].str.lower() == req_from_city.lower()) &
                    (df['To_City'].str.lower() == req_to_city.lower()) &
                    (df['Currency'] == req_currency)
                ]
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_data = [
                    timestamp, "Single", req_prepared_by,
                    req_client_type, req_client_company_name, req_client_contact_name, 
                    req_client_contact_email, req_client_contact_phone,
                    req_from_country, req_from_city, req_to_country, req_to_city,
                    req_truck_type
                ]
                
                # --- THIS IS THE FIX: We get the edited T&Cs from session_state ---
                final_terms = st.session_state.single_terms

                if not result.empty:
                    # --- 1. PRICE FOUND ---
                    matched_price = result.iloc[0]['Price']
                    st.success(f"**Exact Price Found!**")
                    st.metric(label="Calculated Price", value=f"{matched_price} {req_currency}")
                    
                    if log_sheet:
                        log_data.extend(["Price Found", float(matched_price), req_currency])
                        try: log_sheet.append_row(log_data); st.info("Request logged.")
                        except Exception as e: st.warning(f"Failed to log request: {e}")
                    
                    try:
                        doc = DocxTemplate("quote_template.docx")
                        context = {
                            'client_company_summary': client_company_summary, 
                            'scope_summary': req_scope_summary,          
                            'client_ops_details': req_client_ops,
                            'prepared_by': req_prepared_by.title(),
                            'lane': f"{req_from_city.title()}, {req_from_country} to {req_to_city.title()}, {req_to_country}",
                            'truck_type': req_truck_type, 'currency': req_currency,
                            'price': f"{matched_price:,.2f}", 
                            'terms_and_conditions': final_terms # <-- Use the final edited text
                        }
                        doc.render(context)
                        file_stream = BytesIO()
                        doc.save(file_stream)
                        file_stream.seek(0)
                        st.download_button(
                            label="⬇️ Download Quote as .docx", data=file_stream,
                            file_name=f"Quote_{req_from_city}_to_{req_to_city}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    except Exception as e: st.error(f"Error generating Word document: {e}")

                else:
                    # --- 2. PRICE NOT FOUND -> RUN ESTIMATION ---
                    st.warning("No exact price found. Running estimation...")
                    API_KEY = st.secrets.get("geoapify_api_key")
                    
                    rate_result = rates_df[
                        (rates_df['Truck_Type'] == req_truck_type) &
                        (rates_df['Currency'] == req_currency)
                    ]
                    
                    if not API_KEY:
                        st.error("Geoapify API key not found. Estimation is disabled.")
                        if log_sheet:
                            log_data.extend(["Not Found (No API Key)", 0, "N/A"])
                            log_sheet.append_row(log_data)
                    elif rate_result.empty:
                        st.error(f"No rate found for '{req_truck_type}' in '{req_currency}' in rate_list. Estimation failed.")
                        if log_sheet:
                            log_data.extend(["Estimation Failed (No Rate)", 0, "N/A"])
                            log_sheet.append_row(log_data)
                    else:
                        rate_per_km = rate_result.iloc[0]['Rate_per_KM']
                        distance_km = None
                        
                        cache_result = distance_cache_df[
                            (distance_cache_df['From_Country'].str.lower() == req_from_country.lower()) &
                            (distance_cache_df['From_City'].str.lower() == req_from_city.lower()) &
                            (distance_cache_df['To_Country'].str.lower() == req_to_country.lower()) &
                            (distance_cache_df['To_City'].str.lower() == req_to_city.lower())
                        ]
                        
                        if not cache_result.empty:
                            distance_km = cache_result.iloc[0]['Distance_KM']
                            st.info(f"Distance found in cache: **{distance_km:,.0f} KM**")
                        else:
                            with st.spinner("Calculating driving distance (API)..."):
                                distance_km = get_driving_distance(
                                    req_from_city, req_from_country,
                                    req_to_city, req_to_country,
                                    API_KEY
                                )
                            if distance_km:
                                st.success("API call successful. Saving to cache.")
                                cache_data = [req_from_country, req_from_city, req_to_country, req_to_city, float(distance_km)]
                                save_to_distance_cache(client, cache_data)
                        
                        if distance_km:
                            estimated_price = distance_km * rate_per_km
                            st.success(f"**Estimation Complete!**")
                            st.info(f"Distance: **{distance_km:,.0f} KM**")
                            st.metric(label="Estimated Price", value=f"{estimated_price:,.2f} {req_currency}")

                            if log_sheet:
                                log_data.extend(["Estimated", float(estimated_price), req_currency])
                                log_sheet.append_row(log_data)
                            
                            try:
                                doc = DocxTemplate("quote_template.docx")
                                context = {
                                    'client_company_summary': client_company_summary,
                                    'scope_summary': req_scope_summary,
                                    'client_ops_details': req_client_ops,
                                    'prepared_by': req_prepared_by.title(),
                                    'lane': f"{req_from_city.title()}, {req_from_country} to {req_to_city.title()}, {req_to_country}",
                                    'truck_type': req_truck_type, 'currency': req_currency,
                                    'price': f"{estimated_price:,.2f} (Estimated)", 
                                    'terms_and_conditions': final_terms # <-- Use the final edited text
                                }
                                doc.render(context)
                                file_stream = BytesIO()
                                doc.save(file_stream)
                                file_stream.seek(0)
                                st.download_button(
                                    label="⬇️ Download *Estimated* Quote as .docx", data=file_stream,
                                    file_name=f"ESTIMATE_{req_from_city}_to_{req_to_city}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                )
                            except Exception as e:
                                st.error(f"Error generating Word doc: {e}")
                        else:
                            st.error("Estimation failed. Could not calculate distance.")
                            if log_sheet:
                                log_data.extend(["Estimation Failed (API Error)", 0, "N/A"])
                                log_sheet.append_row(log_data)

# --- TAB 2: BATCH UPLOAD ---
with tab2:
    st.header("Batch Price Upload")
    
    # --- Client Details ---
    st.subheader("Client Details")
    batch_client_type = st.radio("Client Type", ("Existing Client", "New Client"), key="batch_client_type")
    
    batch_client_company_name = ""
    batch_client_contact_name = ""
    batch_client_contact_email = ""
    batch_client_contact_phone = ""

    if batch_client_type == "Existing Client":
        batch_client_company_name = st.text_input("Client Company Name", key="batch_company")
        batch_client_contact_name = st.text_input("Client Employee Name", key="batch_contact_name")
    else: # New Client
        batch_client_company_name = st.text_input("New Client Company Name", key="batch_new_company")
        batch_client_contact_name = st.text_input("New Client Contact Name", key="batch_new_name")
        batch_client_contact_email = st.text_input("New Client Email", key="batch_new_email")
        batch_client_contact_phone = st.text_input("New Client Phone", key="batch_new_phone")

    st.markdown("---")
    
    st.subheader("Batch Upload Details")
    st.info("""
        **Instructions:**
        1. Upload an Excel file (`.xlsx`) with: `From_Country`, `From_City`, `To_Country`, `To_City`, `Truck_Type`
        2. Select **one** currency below for all estimations.
        3. The tool will find exact prices or *estimate* using your 'rate_list' and 'distance_cache' sheets.
    """)
    
    currency_list_batch = rates_df['Currency'].unique()
    batch_currency = st.selectbox("Desired Currency (for all estimations)", currency_list_batch, key="batch_currency")
    
    batch_prepared_by = st.text_input("Quote Prepared by:", key="batch_prepared_by")
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])
    
    if uploaded_file and batch_prepared_by and log_sheet:
        
        gemini_api_key = st.secrets.get("gemini_api_key")
        API_KEY = st.secrets.get("geoapify_api_key") 
        ai_model = None
        client_company_summary = "Client details as provided by user." 
        
        if gemini_api_key and batch_client_company_name:
            cache_result = client_summary_cache_df[
                client_summary_cache_df['Client_Company_Name'].str.lower() == batch_client_company_name.lower()
            ]
            if not cache_result.empty:
                client_company_summary = cache_result.iloc[0]['Summary_Text']
                st.info("AI client summary found in cache.")
            else:
                st.warning("Client summary not in cache. Calling AI API...")
                ai_model = configure_gemini(gemini_api_key)
                with st.spinner("Generating AI Client Summary..."):
                    client_company_summary = get_ai_client_summary(ai_model, batch_client_company_name)
                    cache_data = [batch_client_company_name, client_company_summary]
                    save_to_client_summary_cache(client, cache_data)
                    st.success("New summary saved to cache.")
                    
        elif gemini_api_key and not batch_client_company_name:
            st.info("No company name entered, skipping AI summary.")
        else:
            st.warning("Gemini/Geoapify API key not found. AI/Estimation will be disabled.")
            
        try:
            upload_df = pd.read_excel(uploaded_file)
            required_cols = ['From_Country', 'From_City', 'To_Country', 'To_City', 'Truck_Type']
            
            if not all(col in upload_df.columns for col in required_cols):
                st.error(f"File is missing one of the required columns: {required_cols}")
            else:
                price_results = []
                currency_results = []
                status_results = []
                logs_to_append = []
                new_cache_entries = [] 
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with st.spinner(f"Processing {len(upload_df)} rows... This may take time."):
                    for index, row in upload_df.iterrows():
                        
                        price = 0
                        currency = "N/A"
                        status = "Not Found"
                        
                        result = df[
                            (df['From_Country'].str.lower() == str(row['From_Country']).lower()) &
                            (df['To_Country'].str.lower() == str(row['To_Country']).lower()) &
                            (df['Truck_Type'] == row['Truck_Type']) &
                            (df['From_City'].str.lower() == str(row['From_City']).lower()) &
                            (df['To_City'].str.lower() == str(row['To_City']).lower()) &
                            (df['Currency'] == batch_currency)
                        ]
                        
                        if not result.empty:
                            price = result.iloc[0]['Price']
                            currency = result.iloc[0]['Currency']
                            status = "Price Found"
                            price_results.append(price)
                            currency_results.append(currency)
                            status_results.append(status)
                        else:
                            rate_result = rates_df[
                                (rates_df['Truck_Type'] == row['Truck_Type']) &
                                (rates_df['Currency'] == batch_currency)
                            ]
                            
                            if not API_KEY:
                                status = "Not Found (No API Key)"
                            elif rate_result.empty:
                                status = f"Estimation Failed (No Rate for {batch_currency})"
                            else:
                                rate_per_km = rate_result.iloc[0]['Rate_per_KM']
                                currency = batch_currency 
                                distance_km = None

                                cache_result = distance_cache_df[
                                    (distance_cache_df['From_Country'].str.lower() == str(row['From_Country']).lower()) &
                                    (distance_cache_df['From_City'].str.lower() == str(row['From_City']).lower()) &
                                    (distance_cache_df['To_Country'].str.lower() == str(row['To_Country']).lower()) &
                                    (distance_cache_df['To_City'].str.lower() == str(row['To_City']).lower())
                                ]
                                
                                if not cache_result.empty:
                                    distance_km = cache_result.iloc[0]['Distance_KM']
                                    status = "Estimated (Cache)"
                                else:
                                    distance_km = get_driving_distance(
                                        row['From_City'], row['From_Country'],
                                        row['To_City'], row['To_Country'], API_KEY
                                    )
                                    if distance_km:
                                        status = "Estimated (API)"
                                        new_cache_entries.append([
                                            row['From_Country'], row['From_City'],
                                            row['To_Country'], row['To_City'],
                                            float(distance_km)
                                        ])
                                    else:
                                        status = "Estimation Failed (API Error)"
                                
                                if "Estimated" in status:
                                    price = distance_km * rate_per_km
                                    
                            price_results.append(price if "Estimated" in status else "NOT FOUND")
                            currency_results.append(currency)
                            status_results.append(status)
                        
                        logs_to_append.append([
                            timestamp, "Batch", batch_prepared_by,
                            batch_client_type, batch_client_company_name, batch_client_contact_name,
                            batch_client_contact_email, batch_client_contact_phone,
                            row['From_Country'], row['From_City'], row['To_Country'], row['To_City'],
                            row['Truck_Type'], status, float(price), currency
                        ])
                
                if new_cache_entries:
                    st.info(f"Saving {len(new_cache_entries)} new lanes to distance cache...")
                    try:
                        spreadsheet = client.open("price_list")
                        cache_sheet = spreadsheet.worksheet("distance_cache")
                        cache_sheet.append_rows(new_cache_entries)
                        load_distance_cache.clear() 
                    except Exception as e:
                        st.warning(f"Failed to save new cache entries: {e}")

                upload_df['Price'] = price_results
                upload_df['Currency'] = currency_results
                upload_df['Status'] = status_results
                
                st.success("File processing complete!")
                st.dataframe(upload_df)
                
                try:
                    log_sheet.append_rows(logs_to_append)
                    st.info(f"Successfully logged {len(logs_to_append)} requests.")
                except Exception as e:
                    st.warning(f"Failed to log batch requests: {e}")

                output_excel = BytesIO()
                with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
                    upload_df.to_excel(writer, index=False, sheet_name='Priced_Lanes')
                st.download_button(
                    label="⬇️ Download Priced Excel File", data=output_excel.getvalue(),
                    file_name=f"Priced_Lanes_{uploaded_file.name}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                try:
                    doc = DocxTemplate("quote_template.docx")
                    
                    # --- THIS IS THE LOGIC ---
                    # Find the default T&Cs to pass to the batch cover letter
                    default_terms = "1. Price is valid for 7 days." # Fallback
                    if not terms_df.empty:
                        default_lookup = terms_df[terms_df['From_Country'] == 'DEFAULT']
                        if not default_lookup.empty:
                            default_terms = default_lookup.iloc[0]['Terms_Text']

                    context = {
                        'client_company_summary': client_company_summary, 
                        'scope_summary': "Pricing for multiple lanes as requested.", 
                        'client_ops_details': "As per the attached batch pricing file.",
                        'prepared_by': batch_prepared_by.title(),
                        'lane': "Multiple - See attached Excel", 'truck_type': "Multiple - See attached Excel",
                        'currency': "See attached Excel", 'price': "See attached Excel", 
                        'terms_and_conditions': default_terms # <-- Use default T&Cs
                    }
                    doc.render(context)
                    file_stream = BytesIO()
                    doc.save(file_stream)
                    file_stream.seek(0)
                    st.download_button(
                        label="⬇️ Download Quote Cover Letter (.docx)", data=file_stream,
                        file_name=f"Quote_Cover_Letter_{batch_prepared_by}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="word_batch_download"
                    )
                except Exception as e:
                    st.error(f"Error generating Word cover letter: {e}")
                    
        except Exception as e:
            st.error(f"An error occurred during file processing: {e}")

# (The optional data tables at the bottom are now commented out)

# st.markdown("---")
# st.subheader("Price List Database (Read-Only)")
# if not df.empty:
#     st.dataframe(df)
# ... (all other hidden tables) ...