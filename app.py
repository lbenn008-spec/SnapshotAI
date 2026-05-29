import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import io
from PIL import Image
import base64
import os

# Initialize OpenAI Client (Ensure your API key is set in your environment variables)
# os.environ["OPENAI_API_KEY"] = "your-api-key-here"
client = OpenAI()

# Room options directly matching your prefilled worksheet categories
ROOM_OPTIONS = [
    "Apartment", "Attic", "Auto", "Basement", "Bathroom", "Bedroom", "Closet", 
    "Dining", "Entry", "Exterior", "Family", "Foyer", "Game", "Garage", "Hall", 
    "Kitchen", "Laundry", "Living", "Master Bath", "Master Bedroom", "Mud", 
    "Nursery", "Office", "Pantry", "Patio", "Play", "Pool", "Porch", "Shop", 
    "Storage", "Theater", "Utility", "Workout"
]

# Updated columns based on your structural requirements
COLUMNS = [
    "Item #", "Room", "Brand or Manufacturer", "Model#", 
    "Item Description", "Original Vendor", "Quantity Lost", 
    "Item Age (Years)", "Item Age (Months)", "Condition", 
    "Cost to Replace Pre-Tax (each)", "Highest Cost Vendor Link", "Notes"
]

st.set_page_config(page_title="Insurance Contents Worksheet Automation", layout="wide")
st.title("📋 Insurance Claims: Contents Worksheet Generator")
st.write("Upload a photo of an inventory item to extract detailed specs, estimate maximum pre-tax replacement costs, generate vendor links, and append claim notes.")

# Initialize session state to hold dataframe rows across uploads
if "inventory_df" not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame(columns=COLUMNS)

# Sidebar configurations
st.sidebar.header("📍 Item Claims Context")
selected_room = st.sidebar.selectbox("Select Room:", ROOM_OPTIONS)
quantity = st.sidebar.number_input("Quantity Lost", min_value=1, value=1, step=1)
condition = st.sidebar.selectbox("Condition Pre-Loss", ["New", "Above Avg.", "Average", "Below Avg.", "Poor"])
user_notes = st.sidebar.text_area("Additional Item Notes (Optional)", placeholder="e.g., Set of 2, water damaged, purchased on sale, etc.")

# File uploader
uploaded_file = st.file_uploader("Upload Item Photo (JPG, PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Display the image preview
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Item Preview", width=300)
    
    if st.button("Analyze Item & Process to Worksheet"):
        with st.spinner("Analyzing image, fetching max retail value data, and generating links..."):
            # Convert image to bytes for the API
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_bytes = buffered.getvalue()
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            
            # Formulate the prompt prioritizing max pricing and exact URL sources
            prompt = f"""
            You are an expert insurance adjuster and property claims valuation specialist. 
            Analyze this image of a household item and optimize its value details for a Replacement Cost Value (RCV) claim.
            
            Find or estimate the highest common retail pricing (max price) for this specific tier/brand of item to maximize claim accuracy.
            
            Return data STRICTLY as a valid JSON object with these keys:
            - brand: (Identified brand or manufacturer)
            - model_num: (Model number, style number, or exact name variant; 'N/A' if unknown)
            - description: (Detailed descriptive paragraph highlighting materials, premium features, and size to justify premium pricing)
            - vendor: (The retail vendor or marketplace associated with the maximum retail or standard pricing)
            - age_years: (Estimated age in years based on visual wear or model lifecycle)
            - age_months: (Estimated remaining months for age calculation)
            - max_cost: (The highest defensive pre-tax replacement retail cost as a float number, without currency symbols)
            - vendor_link: (A direct website domain or standard search URL string to the product page on that vendor's platform, e.g., 'https://www.homedepot.com/s/...')
            """
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    response_format={ "type": "json_object" },
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ],
                        }
                    ],
                    max_tokens=600,
                )
                
                # Parse JSON output
                result = json.loads(response.choices[0].message.content)
                
                # Determine sequential Item #
                next_item_num = len(st.session_state.inventory_df) + 1
                
                # Construct updated row structure
                new_row = {
                    "Item #": next_item_num,
                    "Room": selected_room,
                    "Brand or Manufacturer": result.get("brand", "Unknown"),
                    "Model#": result.get("model_num", "N/A"),
                    "Item Description": result.get("description", ""),
                    "Original Vendor": result.get("vendor", "Unknown"),
                    "Quantity Lost": quantity,
                    "Item Age (Years)": result.get("age_years", 0),
                    "Item Age (Months)": result.get("age_months", 0),
                    "Condition": condition,
                    "Cost to Replace Pre-Tax (each)": f"${result.get('max_cost', 0.00):.2f}",
                    "Highest Cost Vendor Link": result.get("vendor_link", ""),
                    "Notes": user_notes if user_notes else "Extracted via automated vision capture tool."
                }
                
                # Concat row into worksheet session state
                st.session_state.inventory_df = pd.concat([st.session_state.inventory_df, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Item parsed! Added to your Contents Worksheet below.")
                
            except Exception as e:
                st.error(f"Error executing AI analysis: {e}")

# Display Spreadsheet Preview
st.write("---")
st.subheader("📋 Contents Worksheet Inventory Summary")
st.dataframe(st.session_state.inventory_df, use_container_width=True)

# Export Functionality
if not st.session_state.inventory_df.empty:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        st.session_state.inventory_df.to_excel(writer, index=False, sheet_name="Inventory")
    
    st.download_button(
        label="📥 Download Updated Excel Sheet (.xlsx)",
        data=buffer.getvalue(),
        file_name="Contents_Worksheet_With_Links.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.button("Reset Entire Worksheet"):
        st.session_state.inventory_df = pd.DataFrame(columns=COLUMNS)
        st.rerun()
