from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import sqlite3
import os
import uvicorn
from datetime import datetime

from epd_fetcher import fetch_epd, extract_gwp_from_pdf
from emissions_calculator import calculate_total_emissions
from report_generator import generate_pdf_report, generate_excel_report

app = FastAPI()

# Aktiver CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database-konfig
DB_NAME = "users.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_NAME):
        conn = get_db_connection()
        conn.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                email TEXT UNIQUE,
                password TEXT
            );
        ''')
        # Legg til admin-bruker
        conn.execute('''
            INSERT INTO users (company_name, email, password)
            VALUES (?, ?, ?)
        ''', ("Admin", "admin@klimaregnskap.no", "hemmeligadmin"))
        conn.commit()
        conn.close()

init_db()

# Registrering
@app.post("/register/")
def register(company_name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO users (company_name, email, password) VALUES (?, ?, ?)',
            (company_name, email, password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="E-postadressen er allerede registrert")
    finally:
        conn.close()
    return {"message": "Bruker registrert!"}

# Login
@app.post("/login/")
def login(email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ? AND password = ?',
        (email, password)
    ).fetchone()
    conn.close()
    if user is None:
        raise HTTPException(status_code=401, detail="Feil e-post eller passord")
    return {"message": "Login vellykket!"}

# Modell for produkt
class ProductRequest(BaseModel):
    product_name: str
    quantity: float
    co2_per_unit: float = None
    unit: str = None

class ReportRequest(BaseModel):
    project_name: str
    products: List[ProductRequest]

# Generere rapport
@app.post("/lag_rapport/")
def lag_rapport(report: ReportRequest):
    product_list = []
    total_co2 = 0

    today = datetime.now().strftime("%d-%m-%Y")
    base_filename = f"klimaregnskap_{report.project_name}_{today}".replace(" ", "_")

    pdf_path = f"{base_filename}.pdf"
    excel_path = f"{base_filename}.xlsx"

    for item in report.products:
        if item.co2_per_unit is not None and item.unit is not None:
            co2_per_unit = item.co2_per_unit
            unit = item.unit
        else:
            epd = fetch_epd(item.product_name)
            if not epd:
                continue
            co2_per_unit = epd['co2_per_unit']
            unit = epd['unit']

        total = calculate_total_emissions(co2_per_unit, item.quantity)
        total_co2 += total

        product_list.append({
            "name": item.product_name,
            "quantity": item.quantity,
            "unit": unit,
            "co2_per_unit": co2_per_unit,
            "total_co2": total
        })

    generate_pdf_report(pdf_path, product_list, total_co2, report.project_name)
    generate_excel_report(pdf_path.replace(".pdf", ".xlsx"), product_list, total_co2, report.project_name)

    return {
        "message": "Rapporter generert!",
        "pdf_report_url": f"/lastned/pdf/{base_filename}",
        "excel_report_url": f"/lastned/excel/{base_filename}",
        "total_co2": total_co2
    }

# Last ned rapporter
@app.get("/lastned/pdf/{filename}")
def download_pdf(filename: str):
    filepath = f"{filename}.pdf"
    return FileResponse(path=filepath, media_type='application/pdf', filename=filepath)

@app.get("/lastned/excel/{filename}")
def download_excel(filename: str):
    filepath = f"{filename}.xlsx"
    return FileResponse(path=filepath, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=filepath)

# Kjøre server
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
