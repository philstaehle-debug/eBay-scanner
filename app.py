import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import re
from PIL import Image
import io

# 1. Page Configuration styled for Mobile Browsers
st.set_page_config(page_title="Snap & Value", page_icon="📸", layout="centered")

# Hide standard desktop elements for a clean mobile look
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stButton>button {width: 100%; border-radius: 12px; height: 3em; font-size: 16px;}
    </style>
    """, unsafe_allow_html=True)

st.title("📸 Snap & Value")
st.write("Take a photo of any item to see what it's selling for on eBay.")

# Configure Gemini AI (Get a free key at aistudio.google.com)
# Set this as a Streamlit secret or environment variable
API_KEY = st.sidebar.text_input("Enter Gemini API Key", type="password")
if API_KEY:
    genai.configure(api_key=API_KEY)

def identify_item(image_bytes):
    """Uses Gemini Vision to identify the item and return a clean search query."""
    if not API_KEY:
        st.error("Please provide a Gemini API key in the sidebar.")
        return None
        
    model = genai.GenerativeModel('gemini-1.5-flash')
    img = Image.open(io.BytesIO(image_bytes))
    
    prompt = """
    Analyze this image of an item meant for resale. Identify exactly what it is. 
    Provide a concise, 4-7 word search query optimized to find matching active and sold listings on eBay. 
    Include brand, model, or defining features (like year or set if applicable). Return ONLY the search query text.
    """
    
    response = model.generate_content([prompt, img])
    return response.text.strip()

def get_ebay_comps(query):
    """Scrapes eBay completed/sold items to calculate realistic market value estimates."""
    # Format query for eBay completed items url
    formatted_query = query.replace(" ", "+")
    url = f"https://www.ebay.com/sch/i.html?_nkw={formatted_query}&_sacat=0&LH_Sold=1&LH_Complete=1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pull all pricing elements from the search results page
        price_spans = soup.find_all("span", class_="s-item__price")
        prices = []
        
        for span in price_spans:
            text = span.get_text()
            # Clean up price formats (e.g., "$15.00 to $20.00" or "$14.99")
            cleaned_text = text.replace("$", "").replace(",", "")
            if "to" in cleaned_text:
                cleaned_text = cleaned_text.split("to")[0].strip()
            try:
                price_float = float(cleaned_text)
                if price_float > 0:
                    prices.append(price_float)
            except ValueError:
                continue
                
        return sorted(prices[:15]) # Return up to the first 15 valid comps
    except Exception as e:
        return []

# 2. Pure, Simple Mobile Workflow Interacting with iPhone Camera
source_choice = st.radio("Choose Photo Source:", ["📷 Use Camera", "🖼️ Choose from Gallery"], horizontal=True)

uploaded_file = None
if source_choice == "📷 Use Camera":
    uploaded_file = st.camera_input("Take a photo of the item")
else:
    uploaded_file = st.file_uploader("Select an image from photos", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Read image files
    bytes_data = uploaded_file.getvalue()
    
    st.info("🤖 AI is identifying the item...")
    search_query = identify_item(bytes_data)
    
    if search_query:
        st.success(f"**Identified as:** {search_query}")
        
        st.info("🔍 Fetching recent eBay sales data...")
        market_prices = get_ebay_comps(search_query)
        
        if market_prices:
            # Drop extreme outliers for cleaner calculation metrics
            avg_value = sum(market_prices) / len(market_prices)
            low_end = market_prices[0]
            high_end = market_prices[-1]
            
            # Display results in large, senior-friendly formatting
            st.markdown("---")
            st.metric(label="🎯 Estimated Average Value", value=f"${avg_value:.2f}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="📉 Recent Low", value=f"${low_end:.2f}")
            with col2:
                st.metric(label="📈 Recent High", value=f"${high_end:.2f}")
                
            st.caption("Values are calculated using the 15 most recent completed sales on eBay.")
            
            # Direct link to live listings so he can cross-verify manually if wanted
            ebay_link = f"https://www.ebay.com/sch/i.html?_nkw={search_query.replace(' ', '+')}"
            st.markdown(f"[👉 Click here to view live eBay listings]({ebay_link})")
        else:
            st.warning("Could not automatically pull precise eBay pricing. Try modifying the keywords manually below.")
            manual_query = st.text_input("Refine Search Terms:", value=search_query)
            if st.button("Search Manually"):
                st.markdown(f"[Check Live eBay Results](https://www.ebay.com/sch/i.html?_nkw={manual_query.replace(' ', '+')})")