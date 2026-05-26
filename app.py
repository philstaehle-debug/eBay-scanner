import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io

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

def identify_item(image_bytes):
    model = genai.GenerativeModel('gemini-1.5-flash')
    img = Image.open(io.BytesIO(image_bytes))
    prompt = "Analyze this image. Identify exactly what it is. Provide a concise, 4-7 word search query optimized to find matching items on eBay. Include brand/model. Return ONLY the search query text."
    response = model.generate_content([prompt, img])
    return response.text.strip()

def get_ebay_comps(query):
    formatted_query = query.replace(" ", "+")
    url = f"https://www.ebay.com/sch/i.html?_nkw={formatted_query}&_sacat=0&LH_Sold=1&LH_Complete=1"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_spans = soup.find_all("span", class_="s-item__price")
        prices = []
        for span in price_spans:
            text = span.get_text().replace("$", "").replace(",", "")
            if "to" in text:
                text = text.split("to")[0].strip()
            try:
                price_float = float(text)
                if price_float > 0: prices.append(price_float)
            except ValueError: continue
        return sorted(prices[:15])
    except:
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
        market_prices = get_ebay_comps(search_query)
        
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
                
            ebay_link = f"https://www.ebay.com/sch/i.html?_nkw={search_query.replace(' ', '+')}"
            st.markdown(f"[👉 Click here to view live eBay listings]({ebay_link})")
        else:
            st.warning("Could not automatically pull precise eBay pricing. Use the link below to check manually.")
            st.markdown(f"[Check Live eBay Results](https://www.ebay.com/sch/i.html?_nkw={search_query.replace(' ', '+')})")