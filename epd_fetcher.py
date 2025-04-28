
# epd_fetcher.py

import requests
from bs4 import BeautifulSoup
import pdfplumber
import re
import json
import io
import os
from rapidfuzz import fuzz

# Fallback-database peker på lokale PDF-filer
fallback_epd_database = {
    "fotrør og ig-falsrør (armert)": {
        "pdf_path": "epd_pdfs/fotror_og_ig_falsror_armert.pdf"
    }
}

def clean_text(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', '', text)
    text = text.replace('ø', 'o').replace('å', 'a').replace('æ', 'ae')
    return text

def search_epd_norge_fuzzy(product_name):
    print(f"\n🔎 Søker etter produkt på epder-siden: {product_name}")
    url = "https://www.epd-norge.no/epder/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Feil ved henting av epder-siden: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    all_links = soup.find_all('a', href=True)

    best_score = 0
    best_link = None

    user_input_clean = clean_text(product_name)

    for link in all_links:
        link_text = link.get_text(strip=True)
        link_clean = clean_text(link_text)

        score = fuzz.ratio(user_input_clean, link_clean)

        if score > best_score:
            best_score = score
            best_link = link

    if best_link and best_score > 75:
        epd_detail_link = "https://www.epd-norge.no" + best_link['href']
        print(f"✅ Beste match ({best_score}%): {best_link.get_text(strip=True)}")
        print(f"✅ EPD-detaljside: {epd_detail_link}")
        return epd_detail_link

    print("❌ Fant ingen god match på epder-siden.")
    return None

def fetch_epd(product_name):
    product_name_clean = product_name.lower().strip()
    
    # Først: Sjekk i lokal lagret database
    if os.path.exists("epd_database.json"):
        with open("epd_database.json", "r") as f:
            epd_database = json.load(f)

        if product_name_clean in epd_database:
            product = epd_database[product_name_clean]
            print(f"✅ Fant produkt i lokal database: {product_name_clean}")
            return {
                "unit": product.get("unit", "tonn"),
                "co2_per_unit": product.get("co2_per_unit", 0.0),
                "pdf_path": product.get("pdf_path", None)
            }

    # Hvis ikke funnet lokalt, prøv nett-søk (kan utvides senere)
    print(f"🔎 Søker etter produkt på epder-siden: {product_name}")
    
    # (Her kan du senere implementere søk på nett hvis du vil)
    
    print(f"❌ Fant ikke produkt i lokal database.")
    return None


def download_pdf_from_epd_page(epd_page_url):
    print(f"🌍 Åpner EPD-detaljside: {epd_page_url}")
    try:
        response = requests.get(epd_page_url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Feil ved åpning av EPD-detaljside: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    pdf_tag = soup.find('a', href=lambda href: href and href.endswith('.pdf'))
    if not pdf_tag:
        print("❌ Fant ikke PDF-lenke på EPD-siden.")
        return None

    pdf_url = "https://www.epd-norge.no" + pdf_tag['href']
    print(f"⬇️ Laster ned PDF fra: {pdf_url}")
    try:
        pdf_response = requests.get(pdf_url, timeout=10)
        pdf_response.raise_for_status()
    except Exception as e:
        print(f"❌ Feil ved nedlasting av PDF: {e}")
        return None

    return pdf_response.content


import pdfplumber
import io
import re

def extract_gwp_from_pdf(pdf_content):
    print("📄 Leser PDF og søker etter GWP-total...")
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 2:
                        continue  # Hopper over tomme tabeller

                    headers = [h.lower() if h else "" for h in table[0]]
                    gwp_row = None

                    for row in table[1:]:
                        joined_row = " ".join(str(cell) if cell else "" for cell in row).lower()
                        if "gwp" in joined_row and "total" in joined_row:
                            gwp_row = row
                            print(f"✅ Fant GWP-rad: {row}")
                            break

                    if gwp_row:
                        try:
                            # Først prøver vi å finne "A1-A3" kolonne
                            for idx, header in enumerate(headers):
                                if "a1-a3" in header or "a1 – a3" in header:
                                    value = safe_parse(gwp_row[idx])
                                    if value is not None:
                                        print(f"✅ Fant A1-A3 verdi: {value} kg CO2e")
                                        return round(value, 2)

                            # Hvis ikke, prøv å summere A1, A2, A3 individuelt
                            a_values = []
                            for idx, header in enumerate(headers):
                                if header.strip() in ["a1", "a2", "a3"]:
                                    val = safe_parse(gwp_row[idx])
                                    if val is not None:
                                        a_values.append(val)

                            if len(a_values) == 3:
                                total = round(sum(a_values), 2)
                                print(f"✅ Summert A1+A2+A3: {total} kg CO2e")
                                return total

                            # 🔥 Hvis alt feiler: nød-løsning! 🔥
                            print("⚠️ Bruker nød-løsning for å plukke første 3 tall etter enhet...")
                            numbers = []
                            unit_found = False
                            for cell in gwp_row:
                                if cell:
                                    cell_text = str(cell).lower()
                                    if not unit_found and ("kg co2" in cell_text or "kg co₂" in cell_text):
                                        unit_found = True
                                        continue  # Start plukking etter enheten

                                    if unit_found:
                                        val = safe_parse(cell)
                                        if val is not None:
                                            numbers.append(val)

                            if len(numbers) >= 3:
                                total = round(numbers[0] + numbers[1] + numbers[2], 2)
                                print(f"✅ Summert nød-tall: {total} kg CO2e")
                                return total
                            else:
                                print("⚠️ Klarte ikke plukke 3 tall i nød-løsning.")

                        except Exception as e:
                            print(f"❌ Feil i parsing av GWP-tall: {e}")
                            return None
    except Exception as e:
        print(f"❌ Feil ved lesing av PDF: {e}")
        return None

    print("❌ Fant ingen GWP-total i PDF.")
    return None

def safe_parse(text):
    try:
        if text:
            text = text.replace(",", ".")
            match = re.search(r"([-+]?\d*\.\d+(?:[Ee][-+]?\d+)?|\d+)", text)
            if match:
                return float(match.group(1))
    except:
        return None
    return None
def safe_parse(text):
    try:
        if text:
            text = text.replace(",", ".")
            match = re.search(r"([-+]?\d*\.\d+(?:[Ee][-+]?\d+)?|\d+)", text)
            if match:
                return float(match.group(1))
    except:
        return None
    return None


def safe_parse(text):
    try:
        if text:
            text = text.replace(",", ".")
            match = re.search(r"([-+]?\d*\.\d+(?:[Ee][-+]?\d+)?|\d+)", text)
            if match:
                return float(match.group(1))
    except:
        return None
    return None


    print("❌ Fant ingen GWP-total i PDF.")
    return None

def safe_parse(text):
    if text:
        text = text.replace(",", ".")
        match = re.search(r"([-+]?\d*\.\d+(?:[Ee][-+]?\d+)?|\d+)", text)
        if match:
            try:
                return float(match.group(1))
            except:
                return 0.0
    return 0.0

