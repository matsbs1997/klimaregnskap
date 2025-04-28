from fpdf import FPDF
import pandas as pd

class SimplePDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Klimaregnskap', ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Side {self.page_no()}', align='C')

    def add_project_title(self, project_name):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, f"Klimaregnskap for: {project_name}", ln=True, align='C')
        self.ln(10)

    def add_project_summary(self, total_co2, num_products):
        self.set_font('Arial', '', 12)
        if total_co2 < 1000:
            self.cell(0, 10, f'Totalt CO2-utslipp: {total_co2} kg CO2e', ln=True)
        else:
            self.cell(0, 10, f'Totalt CO2-utslipp: {round(total_co2/1000, 2)} tonn CO2e', ln=True)
        self.cell(0, 10, f'Antall produkter vurdert: {num_products}', ln=True)
        self.ln(10)

    def add_product_table(self, products):
        # Tabell-header
        self.set_fill_color(220, 220, 220)  # Lys grå bakgrunn
        self.set_font('Arial', 'B', 11)
        self.cell(60, 10, 'Produktnavn', 1, 0, 'C', fill=True)
        self.cell(30, 10, 'Antall', 1, 0, 'C', fill=True)
        self.cell(40, 10, 'CO2 per enhet', 1, 0, 'C', fill=True)
        self.cell(40, 10, 'Totalt CO2', 1, 1, 'C', fill=True)

        # Produkter
        self.set_font('Arial', '', 10)
        total_co2_sum = 0

        for product in products:
            self.cell(60, 10, product['name'], 1)
            self.cell(30, 10, str(product['quantity']), 1, 0, 'C')
            self.cell(40, 10, f"{product['co2_per_unit']} kg CO2e/{product['unit']}", 1, 0, 'C')
            self.cell(40, 10, f"{round(product['total_co2'], 2)} kg CO2e", 1, 1, 'C')
            total_co2_sum += product['total_co2']

        # Totalsum-rad
        self.set_fill_color(200, 200, 200)  # Mørkere grå for totalsum
        self.set_font('Arial', 'B', 11)
        self.cell(130, 10, 'TOTALT CO2', 1, 0, 'C', fill=True)

        if total_co2_sum < 1000:
            self.cell(40, 10, f"{round(total_co2_sum, 2)} kg CO2e", 1, 1, 'C', fill=True)
        else:
            self.cell(40, 10, f"{round(total_co2_sum/1000, 2)} tonn CO2e", 1, 1, 'C', fill=True)

def generate_pdf_report(output_path, products, total_co2, project_name):
    pdf = SimplePDFReport()
    pdf.add_page()
    pdf.add_project_title(project_name)
    pdf.add_project_summary(total_co2, len(products))
    pdf.add_product_table(products)
    pdf.output(output_path)

def generate_excel_report(output_path, products, total_co2, project_name):
    df = pd.DataFrame(products)

    if 'total_co2' not in df.columns:
        df['total_co2'] = df['quantity'] * df['co2_per_unit']

    if total_co2 < 1000:
        df['Total CO2 (kg CO2e)'] = df['total_co2'].round(2)
        co2_summary_value = round(total_co2, 2)
        co2_summary_unit = "kg CO2e"
    else:
        df['Total CO2 (tonn CO2e)'] = (df['total_co2'] / 1000).round(2)
        co2_summary_value = round(total_co2 / 1000, 2)
        co2_summary_unit = "tonn CO2e"

    selected_columns = ['name', 'quantity', 'unit', 'co2_per_unit', 'total_co2']
    selected_columns = [col for col in df.columns if col in selected_columns or 'Total CO2' in col]

    df_final = df[selected_columns]

    with pd.ExcelWriter(output_path) as writer:
        df_final.to_excel(writer, sheet_name='Produkter', index=False)

        summary_df = pd.DataFrame({
            'Prosjekt': [project_name],
            'Totalt CO2-utslipp': [f"{co2_summary_value} {co2_summary_unit}"],
            'Antall produkter': [len(products)]
        })

        summary_df.to_excel(writer, sheet_name='Sammendrag', index=False)
