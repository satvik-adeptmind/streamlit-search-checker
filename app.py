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
## NEW: The function now accepts 'check_groups' (a list of lists)
def run_analysis(shop_id, environment, search_keyword, check_groups, result_size):
    """
    Calls the search API and analyzes the relevance of the results.
    A product is considered relevant only if it contains a match from EACH check group.

    Args:
        shop_id (str): The shop ID.
        environment (str): The environment (prod/dev/stg).
        search_keyword (str): The keyword to search for.
        check_groups (list of lists): A list where each inner list contains
                                      variations of a concept to check for.
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
        response.raise_for_status()

        products = response.json().get("products", [])

        if not products:
            return {"status": "error", "message": f"No products were returned for the search term '{search_keyword}'."}

        # --- Analysis ---
        relevant_count = 0
        irrelevant_products_data = []

        for i, product_payload in enumerate(products):
            product_as_string = json.dumps(product_payload).lower()

            ## NEW: The core logic change is here!
            # We use all() to ensure that every group has a match.
            # We use any() inside to check if any variation within a group matches.
            # "A product is relevant if for ALL of the check_groups, ANY variation in that group is in the product string."
            is_relevant = all(
                any(variation in product_as_string for variation in group)
                for group in check_groups
            )

            if is_relevant:
                relevant_count += 1
            else:
                irrelevant_products_data.append({
                    "Position": i + 1,
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
st.markdown("Use this tool to check if search results contain **all** the required concepts.")

# --- 1. CONFIGURATION (in the sidebar) ---
st.sidebar.header("⚙️ Configuration")
shop_id = st.sidebar.text_input("Shop ID", value="croma")
environment = st.sidebar.selectbox("Environment", ["prod", "dev", "stg"], index=0)
search_result_size = st.sidebar.number_input("Search Result Size", min_value=1, max_value=1000, value=400)

## NEW: UI logic to add/remove check groups dynamically
st.sidebar.header("Check Group Management")

# Initialize the number of check groups in session state if it doesn't exist
if 'num_check_groups' not in st.session_state:
    st.session_state.num_check_groups = 1

def add_check_group():
    st.session_state.num_check_groups += 1

def reset_check_groups():
    # We need to clear the old text input values before reducing the count
    for i in range(st.session_state.num_check_groups):
        if f"check_group_{i}" in st.session_state:
            del st.session_state[f"check_group_{i}"]
    st.session_state.num_check_groups = 1

st.sidebar.button("Add another check group", on_click=add_check_group, use_container_width=True)
st.sidebar.button("Reset to 1 check group", on_click=reset_check_groups, use_container_width=True)

# --- 2. USER INPUT (in a form) ---
with st.form("search_form"):
    st.subheader("🔍 Search Parameters")
    search_keyword_input = st.text_input(
        "Enter the keyword to SEARCH on the API",
        placeholder="e.g., samsung hdr10+ laptops"
    )

    st.markdown("---")
    st.subheader("✅ Required Concepts")
    st.markdown("A product will be marked relevant **only if it contains a match from EACH group below**.")

    ## NEW: Dynamically create text inputs based on session state
    check_group_inputs = []
    for i in range(st.session_state.num_check_groups):
        input_value = st.text_input(
            f"**Check Group {i+1}**: Enter comma-separated variations",
            placeholder="e.g., laptop, laptops" if i > 0 else "e.g., samsung",
            key=f"check_group_{i}" # Unique key is crucial for dynamic widgets
        )
        check_group_inputs.append(input_value)
    
    submitted = st.form_submit_button("Analyze Assortment", type="primary")

# --- 3. EXECUTE AND DISPLAY RESULTS ---
if submitted:
    # Basic validation
    if not all([shop_id, search_keyword_input] + check_group_inputs):
        st.warning("Please fill in all the required fields: Shop ID, Search Keyword, and all Check Groups.")
    else:
        # Process inputs
        search_keyword = search_keyword_input.strip()

        ## NEW: Process the group inputs into a list of lists
        check_groups = [
            [kw.strip().lower() for kw in group_str.split(',')]
            for group_str in check_group_inputs if group_str.strip()
        ]

        with st.spinner(f"Fetching top {search_result_size} results for '{search_keyword}'..."):
            analysis_result = run_analysis(
                shop_id.strip(),
                environment,
                search_keyword,
                check_groups,
                search_result_size
            )

        st.subheader("📊 Assortment Quality Report")

        if analysis_result["status"] == "error":
            st.error(f"**Error:** {analysis_result['message']}")

        elif analysis_result["status"] == "success":
            st.markdown(f"**Search Term:** `{search_keyword}`")

            ## NEW: Display the check groups that were used in the analysis
            st.markdown("**Checked For Products Containing ALL of these concepts:**")
            for i, group in enumerate(check_groups):
                # Format for display: ' OR '.join(...)
                st.markdown(f"- **Group {i+1}:** `{'` OR `'.join(group)}`")

            total = analysis_result['total_products']
            relevant = analysis_result['relevant_count']
            irrelevant_list = analysis_result['irrelevant_products']

            relevance_percentage = (relevant / total * 100) if total > 0 else 0

            col1, col2 = st.columns(2)
            col1.metric("Relevance Score", f"{relevant} / {total}")
            col2.metric("Relevance Percentage", f"{relevance_percentage:.1f}%")

            if irrelevant_list:
                st.markdown("---")
                st.error(f"🚨 Found {len(irrelevant_list)} irrelevant products:")
                df = pd.DataFrame(irrelevant_list)
                st.dataframe(df, use_container_width=True)
            else:
                st.success("🌟 Perfect! All returned products were relevant.")