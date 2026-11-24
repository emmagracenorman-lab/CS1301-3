# Lab 3: Spending Explorer (API data page)
# Shows where the City of Atlanta's money goes, using the Open Checkbook API.
# No AI is used on this page: all the totals and rankings are done by the Python below.
#
# NOTE: AI (Claude) helped write this page.

import requests
import pandas as pd
import streamlit as st

URL = "https://atlanta.data.socrata.com/resource/jmke-icfi.json"

# Atlanta's fiscal year starts in July, so fiscal period 1 = July, 2 = August, and so on.
MONTHS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]


# ---------- Getting the data ----------

@st.cache_data(ttl=3600)  # remember results for an hour so the page stays fast
def get_json(params):
    """Ask the Open Checkbook API for data and return the list of records."""
    response = requests.get(URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_years():
    """Return every fiscal year in the dataset, newest first."""
    rows = get_json({"$select": "fiscal_year", "$group": "fiscal_year", "$order": "fiscal_year DESC"})
    return [int(float(row["fiscal_year"])) for row in rows if "fiscal_year" in row]


def get_departments(year):
    """Return the departments that made payments in a given fiscal year."""
    rows = get_json({
        "$select": "department",
        "$where": f"fiscal_year={year}",
        "$group": "department",
        "$order": "department",
    })
    return [row["department"] for row in rows if "department" in row]


def get_payments(year, department):
    """Return every payment one department made in one fiscal year."""
    return get_json({"fiscal_year": year, "department": department, "$limit": 50000})


# ---------- Processing the data (plain Python, no AI) ----------

def total_by(payments, field):
    """Add up the payment amounts for each value of a field (like each vendor)."""
    totals = {}
    for payment in payments:
        key = payment.get(field, "Unknown")
        amount = float(payment.get("amount", 0))
        totals[key] = totals.get(key, 0) + amount
    return totals


def top_n(totals, n):
    """Return the n biggest entries of a totals dictionary, largest first."""
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return dict(ranked[:n])


def total_by_month(payments):
    """Add up spending for each month of the fiscal year, in order from July to June."""
    by_period = total_by(payments, "fiscal_period")
    by_month = {}
    for number, month in enumerate(MONTHS, start=1):
        label = f"{number:02d} {month}"  # "01 Jul" keeps the months in order on the chart
        amount = 0
        for period, total in by_period.items():
            if period != "Unknown" and int(float(period)) == number:
                amount += total
        by_month[label] = amount
    return by_month


# ---------- The page ----------

st.title("Spending Explorer")
st.write(
    "Pick a fiscal year and a city department to see how much it spent, "
    "what the money went to, and which vendors were paid the most."
)

try:
    years = get_years()
except Exception:
    st.error("Sorry, the Atlanta Open Checkbook data couldn't be loaded. Please try again later.")
    st.stop()

# User input 1: fiscal year
year = st.selectbox("Fiscal year", years)

try:
    departments = get_departments(year)
except Exception:
    st.error("Sorry, the list of departments couldn't be loaded.")
    st.stop()

# User input 2: department
department = st.selectbox("Department", departments)

# User input 3: how many vendors to show
how_many = st.slider("Number of top vendors to show", min_value=3, max_value=20, value=10)

with st.spinner("Loading payments..."):
    try:
        payments = get_payments(year, department)
    except Exception:
        st.error("Sorry, the payments couldn't be loaded.")
        st.stop()

if not payments:
    st.info("No payments found for this department and year.")
    st.stop()

# Summary numbers
total_spent = sum(float(p.get("amount", 0)) for p in payments)
vendor_totals = total_by(payments, "vendor_name")
col1, col2, col3 = st.columns(3)
col1.metric("Total spent", f"${total_spent:,.0f}")
col2.metric("Payments", f"{len(payments):,}")
col3.metric("Vendors paid", f"{len(vendor_totals):,}")

# Visual 1: spending by category
st.subheader("Where the money went")
category_totals = total_by(payments, "expense_category")
st.bar_chart(pd.Series(category_totals, name="Amount ($)"))

# Visual 2: top vendors
st.subheader(f"Top {how_many} vendors")
top_vendors = top_n(vendor_totals, how_many)
st.bar_chart(pd.Series(top_vendors, name="Amount ($)"))

# Visual 3: spending through the year
st.subheader("Spending by month")
st.line_chart(pd.Series(total_by_month(payments), name="Amount ($)"))
