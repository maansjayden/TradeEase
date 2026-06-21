import streamlit as st
from dotenv import load_dotenv
from gemini_client import GeminiClient

load_dotenv()

st.set_page_config(
    page_title="TradeEase — AI Trade Compliance",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] { background: linear-gradient(160deg, #0a4f7a 0%, #0e7490 100%); }
    [data-testid="stSidebar"] * { color: #fff !important; }
    [data-testid="stSidebar"] .stRadio label { font-size: 1rem; padding: 6px 0; }
    .block-container { padding-top: 2rem; }
    .hs-code { font-size: 2rem; font-weight: 700; color: #0e7490; }
    .caution-box { background: #fef3c7; border-left: 4px solid #f59e0b;
                   padding: 12px 16px; border-radius: 6px; margin-top: 8px; }
    .compliance-note { background: #dbeafe; border-left: 4px solid #3b82f6;
                       padding: 12px 16px; border-radius: 6px; margin-top: 8px; }
    .confidence-high { background: #d1fae5; color: #065f46;
                       padding: 2px 10px; border-radius: 99px; font-size: 0.8rem; font-weight: 600; }
    .confidence-low  { background: #fee2e2; color: #991b1b;
                       padding: 2px 10px; border-radius: 99px; font-size: 0.8rem; font-weight: 600; }
    .confidence-med  { background: #fef3c7; color: #92400e;
                       padding: 2px 10px; border-radius: 99px; font-size: 0.8rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

PAGES = ["🏠 Home", "🔎 Classify HS Code", "🧾 Generate Invoice", "🧭 Guidance & Mentor"]

if "page" not in st.session_state:
    st.session_state.page = PAGES[0]


def go_to(page_name: str):
    st.session_state.page = page_name
    st.rerun()


@st.cache_resource
def get_client():
    try:
        return GeminiClient()
    except ValueError:
        return None


client = get_client()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌊 TradeEase")
    st.markdown("*AI Trade Compliance Assistant*")
    st.divider()
    selected = st.radio(
        "Navigate",
        PAGES,
        index=PAGES.index(st.session_state.page),
        label_visibility="collapsed",
        key="sidebar_nav",
    )
    if selected != st.session_state.page:
        st.session_state.page = selected
        st.rerun()
    st.divider()
    st.caption("Powered by Google Gemini · MVP build")

page = st.session_state.page

if client is None:
    st.error("⚠️ No GEMINI_API_KEY found. Add it to a .env file next to app.py.")


# ── Home ──────────────────────────────────────────────────────────────────────
if page == "🏠 Home":
    st.title("Hi there 👋")
    st.subheader("Ready to Simplify Trade Compliance?")
    st.markdown(
        "Tia the AI mentor says: *Describe a product in the search bar below "
        "or pick a feature to get started.*"
    )
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 🔎 Classify HS Code")
        st.markdown("Describe your product and get the right tariff code in seconds.")
        st.caption("AI Classification")
    with col2:
        st.markdown("### 🧾 Generate Invoice")
        st.markdown("Turn shipment details into a compliant commercial invoice.")
        st.caption("Auto Document")
    with col3:
        st.markdown("### 🧭 Guidance & Mentor")
        st.markdown("Ask a quick question — get a clear, friendly answer from Tia.")
        st.caption("AI Mentor")

    st.divider()
    st.markdown("#### Quick classify")
    quick = st.text_input(
        "Describe a product to classify",
        placeholder='e.g. "100% cotton men\'s t-shirts, for export to the USA"',
        label_visibility="collapsed",
    )
    if st.button("➜ Classify now", type="primary"):
        if quick.strip():
            st.session_state["prefill_classify"] = quick.strip()
            go_to("🔎 Classify HS Code")
        else:
            st.warning("Type a product description first.")


# ── Classify ─────────────────────────────────────────────────────────────────
elif page == "🔎 Classify HS Code":
    st.title("🔎 Classify HS Code")
    st.caption("Describe the product. The AI suggests a tariff code with its reasoning.")

    prefill = st.session_state.pop("prefill_classify", "")
    description = st.text_area(
        "Product description",
        value=prefill,
        placeholder="e.g. Men's t-shirts, 100% cotton, knitted, short sleeve, for retail sale",
        height=100,
        key="classify_desc",
    )
    destination = st.text_input("Destination country *(optional)*", placeholder="e.g. United States")

    if st.button("Classify with AI ✨", type="primary", disabled=client is None):
        if not description.strip():
            st.warning("Please describe the product first.")
        else:
            with st.spinner("Classifying…"):
                result = client.classify_hs_code(description.strip(), destination.strip())
            st.session_state["classify_result"] = result
            st.session_state["classify_desc_used"] = description.strip()

    result = st.session_state.get("classify_result")
    if result:
        if "error" in result:
            st.error("⚠️ " + result["error"])
        else:
            confidence_str = result.get("confidence_level", "")
            try:
                confidence_num = int(confidence_str.split("/")[0])
                badge_class = (
                    "confidence-high" if confidence_num >= 80
                    else "confidence-low" if confidence_num < 60
                    else "confidence-med"
                )
                confidence_label = f"{confidence_str} confidence"
            except (ValueError, IndexError):
                badge_class = "confidence-med"
                confidence_label = confidence_str if confidence_str else "Medium confidence"

            with st.container(border=True):
                col_code, col_conf = st.columns([3, 1])
                with col_code:
                    st.markdown(
                        f'<span class="hs-code">{result.get("hs_code", "—")}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**{result.get('description', '')}**")
                with col_conf:
                    st.markdown(
                        f'<span class="{badge_class}">{confidence_label}</span>',
                        unsafe_allow_html=True,
                    )

                st.markdown(result.get("reasoning", ""))

                if result.get("gri_rule"):
                    st.markdown(f"**GRI Rule applied:** {result['gri_rule']}")

                questions = result.get("questions", [])
                if questions:
                    st.markdown(
                        '<div class="caution-box">⚠️ <strong>Clarifying questions before finalising:</strong><ul>'
                        + "".join(f"<li>{q}</li>" for q in questions)
                        + "</ul></div>",
                        unsafe_allow_html=True,
                    )

                sources = result.get("sources", [])
                links = result.get("links_to_sources", [])
                if sources:
                    with st.expander("📚 Sources"):
                        for i, src in enumerate(sources):
                            link = links[i] if i < len(links) else None
                            if link:
                                st.markdown(f"- [{src}]({link})")
                            else:
                                st.markdown(f"- {src}")

                st.divider()
                if st.button("Use this code → Generate Invoice", type="secondary"):
                    st.session_state["prefill_invoice"] = {
                        "product_description": st.session_state.get("classify_desc_used", ""),
                        "hs_code": result.get("hs_code", ""),
                    }
                    st.session_state["classify_result"] = None
                    go_to("🧾 Generate Invoice")


# ── Invoice ───────────────────────────────────────────────────────────────────
elif page == "🧾 Generate Invoice":
    st.title("🧾 Generate Commercial Invoice")
    st.caption("Fill in shipment details — the AI drafts a ready-to-send invoice.")

    prefill = st.session_state.pop("prefill_invoice", {})

    col1, col2 = st.columns(2)
    with col1:
        exporter_name = st.text_input("Exporter name", placeholder="Your company name")
        exporter_addr = st.text_input("Exporter address", placeholder="City, Country")
        product_desc = st.text_input(
            "Product description",
            value=prefill.get("product_description", ""),
            placeholder="What's being shipped",
        )
        quantity = st.text_input("Quantity", placeholder="e.g. 500 units")
        currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "INR", "ZAR", "KES", "NGN"])

    with col2:
        buyer_name = st.text_input("Buyer name", placeholder="Buyer's company name")
        buyer_addr = st.text_input("Buyer address", placeholder="City, Country")
        hs_code = st.text_input(
            "HS Code",
            value=prefill.get("hs_code", ""),
            placeholder="e.g. 6109.10",
        )
        unit_price = st.text_input("Unit price", placeholder="e.g. 4.50")
        incoterm = st.selectbox("Incoterm", ["FOB", "CIF", "EXW", "FCA", "DDP", "CPT"])

    if st.button("Generate Invoice with AI ✨", type="primary", disabled=client is None):
        required = [exporter_name, buyer_name, product_desc, quantity, unit_price]
        if any(not f.strip() for f in required):
            st.warning("Please fill in exporter, buyer, product, quantity, and price.")
        else:
            invoice_data = {
                "exporter_name": exporter_name.strip(),
                "exporter_address": exporter_addr.strip(),
                "buyer_name": buyer_name.strip(),
                "buyer_address": buyer_addr.strip(),
                "product_description": product_desc.strip(),
                "hs_code": hs_code.strip(),
                "quantity": quantity.strip(),
                "unit_price": unit_price.strip(),
                "currency": currency,
                "incoterm": incoterm,
            }

            with st.spinner("Drafting invoice…"):
                result = client.generate_invoice(invoice_data)

            if "error" in result:
                st.error("⚠️ " + result["error"])
            else:
                with st.container(border=True):
                    st.markdown(f"**Invoice №** `{result.get('invoice_number', '')}`")
                    st.text(result.get("formatted_invoice", ""))

                    if result.get("compliance_note"):
                        st.markdown(
                            f'<div class="compliance-note">ℹ️ {result["compliance_note"]}</div>',
                            unsafe_allow_html=True,
                        )

                    st.download_button(
                        "💾 Download as .txt",
                        data=result.get("formatted_invoice", ""),
                        file_name=f'{result.get("invoice_number", "invoice")}.txt',
                        mime="text/plain",
                    )


# ── Mentor ────────────────────────────────────────────────────────────────────
elif page == "🧭 Guidance & Mentor":
    st.title("🧭 Guidance & Mentor")
    st.caption("Quick answers for first-time exporters — not a substitute for a licensed customs broker.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{
            "role": "assistant",
            "text": (
                "Hi! I'm Tia 👋 Ask me anything about exporting — required documents, "
                "Incoterms, AGOA eligibility, or how to read your HS code result."
            ),
        }]

    for msg in st.session_state.chat_history:
        role = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(role, avatar="🧭" if role == "assistant" else None):
            st.markdown(msg["text"])

    user_input = st.chat_input("Ask about documents, Incoterms, AGOA, customs basics…")
    if user_input:
        if client is None:
            st.error("No API key configured.")
        else:
            st.session_state.chat_history.append({"role": "user", "text": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.chat_message("assistant", avatar="🧭"):
                with st.spinner("Tia is thinking…"):
                    result = client.ask_mentor(user_input, list(st.session_state.chat_history))
                reply = result.get("reply", "Sorry, something went wrong — please try again.")
                st.markdown(reply)

            st.session_state.chat_history.append({"role": "assistant", "text": reply})
