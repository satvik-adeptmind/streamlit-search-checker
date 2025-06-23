import streamlit as st
import requests
import json
import pandas as pd

# --- Page Configuration ---
st.set_page_config(
    page_title="Search Assortment Quality Checker",
    page_icon="🤖",
    layout="wide"
)

# --- Core Logic Function ---
# I've moved your script's logic into this function.
# It now takes parameters from the UI and returns the results.
def run_analysis(shop_id, environment, search_keyword, check_variations, result_size):
    """
    Calls the search API and analyzes the relevance of the results.

    Args:
        shop_id (str): The shop ID.
        environment (str): The environment (prod/dev/stg).
        search_keyword (str): The keyword to search for.
        check_variations (list): A list of lowercase keywords to check for in the results.
        result_size (int): The number of results to fetch.

    Returns:
        dict: A dictionary containing the analysis results or an error message.
    """
    url = f"http://dlp-{environment}-search-api.retail.adeptmind.ai:4000/search?shop_id={shop_id}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "query": search_keyword,
        "size": result_size,
        "force_exploding_variants": False,
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status() # Raises an exception for bad status codes (4xx or 5xx)

        products = response.json().get("products", [])

        if not products:
            return {"status": "error", "message": f"No products were returned for the search term '{search_keyword}'."}

        # --- Analysis ---
        relevant_count = 0
        irrelevant_products_data = []

        for i, product_payload in enumerate(products):
            position = i + 1
            product_as_string = json.dumps(product_payload).lower()

            is_relevant = any(variation in product_as_string for variation in check_variations)

            if is_relevant:
                relevant_count += 1
            else:
                irrelevant_products_data.append({
                    "Position": position,
                    "Product ID": product_payload.get('product_id', 'N/A'),
                    "Product Name": product_payload.get('title', 'N/A')
                })
        
        return {
            "status": "success",
            "total_products": len(products),
            "relevant_count": relevant_count,
            "irrelevant_products": irrelevant_products_data
        }

    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"API Error (Status Code: {e.response.status_code}): {e.response.text}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Network Error: Could not connect to the API. Details: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}

# --- Streamlit User Interface ---

st.title("🤖 Search Assortment Quality Checker")
st.markdown("Only use this tool to check for the word that you would have to search in payload of each product for keywords with large number of products")

# --- 1. CONFIGURATION (in the sidebar) ---
st.sidebar.header("⚙️ Configuration")
shop_id = st.sidebar.text_input("Shop ID", value="croma")
environment = st.sidebar.selectbox("Environment", ["prod", "staging"], index=0)
search_result_size = st.sidebar.number_input("Search Result Size", min_value=1, max_value=1000, value=400)

# --- 2. USER INPUT (in a form) ---
# Using a form prevents the app from re-running on every keystroke
with st.form("search_form"):
    st.subheader("🔍 Search Parameters")
    search_keyword_input = st.text_input(
        "Enter the keyword to SEARCH on the API",
        placeholder="e.g., ai laptops"
    )
    check_keyword_input = st.text_input(
        "Enter keywords to CHECK FOR in the results (comma-separated)",
        placeholder="e.g., hdr10+, hdr 10 plus, hdr10plus"
    )
    
    submitted = st.form_submit_button("Analyze Assortment")

# --- 3. EXECUTE AND DISPLAY RESULTS ---
if submitted:
    # Basic validation
    if not all([shop_id, search_keyword_input, check_keyword_input]):
        st.warning("Please fill in all the required fields: Shop ID, Search Keyword, and Check Keywords.")
    else:
        # Process inputs
        search_keyword = search_keyword_input.strip()
        check_variations = [kw.strip().lower() for kw in check_keyword_input.split(',')]

        # Show a spinner while the analysis is running
        with st.spinner(f"Fetching top {search_result_size} results for '{search_keyword}'..."):
            analysis_result = run_analysis(
                shop_id.strip(), 
                environment, 
                search_keyword, 
                check_variations, 
                search_result_size
            )

        st.subheader("📊 Assortment Quality Report")
        
        # Display results or errors
        if analysis_result["status"] == "error":
            st.error(f"**Error:** {analysis_result['message']}")
        
        elif analysis_result["status"] == "success":
            # --- 5. DISPLAY THE REPORT ---
            total = analysis_result['total_products']
            relevant = analysis_result['relevant_count']
            irrelevant_list = analysis_result['irrelevant_products']
            
            relevance_percentage = (relevant / total * 100) if total > 0 else 0
            
            st.markdown(f"**Search Term:** `{search_keyword}`")
            st.markdown(f"**Checked For Variations Of:** `{check_keyword_input}`")

            col1, col2 = st.columns(2)
            col1.metric(
                label="Relevance Score", 
                value=f"{relevant} / {total}",
                help="The number of products containing at least one of the 'check for' keywords."
            )
            col2.metric(
                label="Relevance Percentage", 
                value=f"{relevance_percentage:.1f}%"
            )

            if irrelevant_list:
                st.markdown(f"---")
                st.error(f"🚨 Found {len(irrelevant_list)} irrelevant products (out of {total} results):")
                
                # Use pandas DataFrame for a clean, sortable table
                df = pd.DataFrame(irrelevant_list)
                st.dataframe(df, use_container_width=True)
            else:
                st.success("🌟 Perfect! All returned products were relevant.")