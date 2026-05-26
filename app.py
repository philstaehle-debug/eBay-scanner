import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import urllib.parse

# Page Setup - Forced clean mobile layout
st.set_page_config(page_title="Snap & Value", page_icon="📸", layout="centered")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stButton>button {width: 100%; border-radius: 12px; height: 3em; font-size: 16px; background-color: #007aff; color: white;}
    </style>
    """, unsafe_allow_html=True)

st.title("📸 Snap & Value")
st.write("Take a photo of any item to see what it's selling for on eBay.")

# Securely pull the key directly from the hidden Cloud Vault
if "GEMINI_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_KEY"])
else:
    st.error("Missing API Key configuration in backend cloud settings.")

def get_best_available_model():
    """Dynamically asks Google what active models this key can use to avoid hardcoding errors."""
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for model_name in ["models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-flash"]:
            if model_name in available_models:
                return model_name
        flash_fallback = [m for m in available_models if 'flash' in m.lower()]
        if flash_fallback:
            return flash_fallback[0]
        return available_models[0]
    except Exception:
        return "models/gemini-2.5-flash"

def identify_item(image_bytes):
    active_model = get_best_available_model()
    model = genai.GenerativeModel(active_model)
    img = Image.open(io.BytesIO(image_bytes))
    prompt = "Analyze this image. Identify exactly what it is. Provide a concise, 4-7 word search query optimized to find matching items on eBay. Include brand/model. Return ONLY the search query text."
    response = model.generate_content([prompt, img])
    return response.text.strip()

def get_ebay_comps_rss(query):
    """
    Pulls eBay comps using their native public RSS feed. 
    This avoids anti-bot data center blockades completely.
    """
    encoded_query = urllib.parse.quote_plus(query)
    
    # eBay RSS feed URL pattern for Completed + Sold Listings
    url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&_sacat=0&LH_Sold=1&LH_Complete=1&_rss=1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
            
        # Parse XML feed content
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.find_all("item")
        
        prices = []
        for item in items:
            description = item.find("description")
            if description:
                desc_text = description.get_text()
                # Extract the price value string from the feed element (e.g., "Price: $34.99")
                if "Price:" in desc_text:
                    try:
                        price_part = desc_text.split("Price:")[1].split("<")[0].strip()
                        cleaned_price = price_part.replace("$", "").replace(",", "")
                        if "to" in cleaned_price:
                            cleaned_price = cleaned_price.split("to")[0].strip()
                        
                        price_float = float(cleaned_price)
                        if price_float > 0:
                            prices.append(price_float)
                    except (IndexError, ValueError):
                        continue
                        
        return sorted(prices[:15])
    except Exception:
        return []

# Simplified UX for your Dad
source_choice = st.radio("Choose Photo Source:", ["📷 Use Camera", "🖼️ Choose from Gallery"], horizontal=True)

uploaded_file = None
if source_choice == "📷 Use Camera":
    uploaded_file = st.camera_input("Take a photo of the item")
else:
    uploaded_file = st.file_uploader("Select an image from photos", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    bytes_data = uploaded_file.getvalue()
    
    st.info("🤖 AI is identifying the item...")
    search_query = identify_item(bytes_data)
    
    if search_query:
        st.success(f"**Identified as:** {search_query}")
        st.info("🔍 Fetching recent eBay sales data...")
        market_prices = get_ebay_comps_rss(search_query)
        
        if market_prices:
            avg_value = sum(market_prices) / len(market_prices)
            low_end = market_prices[0]
            high_end = market_prices[-1]
            
            st.markdown("---")
            st.metric(label="🎯 Estimated Average Value", value=f"${avg_value:.2f}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="📉 Recent Low", value=f"${low_end:.2f}")
            with col2:
                st.metric(label="📈 Recent High", value=f"${high_end:.2f}")
                
            ebay_link = f"https://www.ebay.com/sch/i.html?_nkw={search_query.replace(' ', '+')}&LH_Sold=1&LH_Complete=1"
            st.markdown(f"[👉 Click here to view live sold listings]({ebay_link})")
        else:
            st.warning("Could not automatically pull precise eBay pricing. Use the link below to check manually.")
            ebay_link = f"https://www.ebay.com/sch/i.html?_nkw={search_query.replace(' ', '+')}&LH_Sold=1&LH_Complete=1"
            st.markdown(f"[Check Live eBay Results]({ebay_link})")