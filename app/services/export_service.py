from typing import Dict, List
import json
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import io

class ExportService:
    def generate_pdf_export(self, survey_data: Dict, responses: List[Dict]) -> bytes:
        """Generate PDF export of completed survey"""
        buffer = io.BytesIO()

        # Create PDF
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title = Paragraph(f"<b>Feasibility Assessment - {survey_data['study_name']}</b>", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))

        # Metadata
        metadata = [
            ["Sponsor:", survey_data['sponsor_name']],
            ["Study:", survey_data['study_name']],
            ["NCT Number:", survey_data.get('nct_number', 'N/A')],
            ["Site:", survey_data['site_name']],
            ["Feasibility Score:", f"{survey_data.get('feasibility_score', 'N/A')}/100"],
            ["Completion:", f"{survey_data.get('completion_percentage', 0):.1f}%"],
            ["Date:", datetime.now().strftime("%Y-%m-%d")]
        ]

        metadata_table = Table(metadata, colWidths=[120, 380])
        metadata_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(metadata_table)
        story.append(Spacer(1, 20))

        # Responses
        story.append(Paragraph("<b>Survey Responses</b>", styles['Heading1']))
        story.append(Spacer(1, 12))

        # Separate objective and subjective
        objective_responses = [r for r in responses if r.get('is_objective')]
        subjective_responses = [r for r in responses if not r.get('is_objective')]

        # Objective Section
        if objective_responses:
            story.append(Paragraph("<b>Objective Responses (Auto-filled)</b>", styles['Heading2']))
            obj_data = []
            for resp in objective_responses:
                obj_data.append([
                    resp['text'][:80] + "..." if len(resp['text']) > 80 else resp['text'],
                    str(resp.get('response', 'N/A')),
                    f"{resp.get('confidence', 0)*100:.0f}%" if resp.get('confidence') else "Manual"
                ])

            obj_table = Table(obj_data, colWidths=[280, 150, 70])
            obj_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(obj_table)
            story.append(Spacer(1, 20))

        # Subjective Section
        if subjective_responses:
            story.append(Paragraph("<b>Subjective Responses</b>", styles['Heading2']))
            for resp in subjective_responses:
                story.append(Paragraph(f"<b>Q:</b> {resp['text']}", styles['Normal']))
                story.append(Paragraph(f"<b>A:</b> {resp.get('response', 'No response provided')}", styles['Normal']))
                story.append(Spacer(1, 10))

        # Build PDF
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()

        return pdf

    def generate_excel_export(self, survey_data: Dict, responses: List[Dict]) -> bytes:
        """Generate Excel export of completed survey"""
        buffer = io.BytesIO()

        # Create Excel writer
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Field': ['Sponsor', 'Study', 'NCT Number', 'Site', 'Feasibility Score', 'Completion %', 'Export Date'],
                'Value': [
                    survey_data['sponsor_name'],
                    survey_data['study_name'],
                    survey_data.get('nct_number', 'N/A'),
                    survey_data['site_name'],
                    survey_data.get('feasibility_score', 'N/A'),
                    f"{survey_data.get('completion_percentage', 0):.1f}%",
                    datetime.now().strftime("%Y-%m-%d")
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

            # Responses sheet
            responses_data = []
            for resp in responses:
                responses_data.append({
                    'Question ID': resp['id'],
                    'Question': resp['text'],
                    'Type': resp['type'],
                    'Objective/Subjective': 'Objective' if resp.get('is_objective') else 'Subjective',
                    'Response': resp.get('response', ''),
                    'Source': resp.get('source', 'Manual'),
                    'Confidence': f"{resp.get('confidence', 0)*100:.0f}%" if resp.get('confidence') else 'N/A'
                })

            responses_df = pd.DataFrame(responses_data)
            responses_df.to_excel(writer, sheet_name='Responses', index=False)

            # Scoring breakdown sheet
            if survey_data.get('score_breakdown'):
                breakdown_data = []
                for category, details in survey_data['score_breakdown'].items():
                    breakdown_data.append({
                        'Category': category,
                        'Score': details.get('score', 0),
                        'Weight': details.get('weight', 0),
                        'Weighted Score': details.get('weighted_score', 0)
                    })

                breakdown_df = pd.DataFrame(breakdown_data)
                breakdown_df.to_excel(writer, sheet_name='Score Breakdown', index=False)

        excel = buffer.getvalue()
        buffer.close()

        return excel

    def send_email_submission(
        self,
        to_email: str,
        survey_data: Dict,
        pdf_bytes: bytes,
        excel_bytes: bytes
    ) -> bool:
        """Send completed survey via email"""
        try:
            # Email configuration (use environment variables in production)
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            sender_email = "sitesync@example.com"  # Configure with real email
            sender_password = "your_app_password"  # Use app-specific password

            # Create message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = to_email
            msg['Subject'] = f"Feasibility Assessment - {survey_data['study_name']} - {survey_data['site_name']}"

            # Email body
            body = f"""
            Dear {survey_data['sponsor_name']} Team,

            Please find attached the completed feasibility assessment for:

            Study: {survey_data['study_name']}
            NCT Number: {survey_data.get('nct_number', 'N/A')}
            Site: {survey_data['site_name']}

            Feasibility Score: {survey_data.get('feasibility_score', 'N/A')}/100
            Completion Rate: {survey_data.get('completion_percentage', 0):.1f}%

            The assessment includes:
            - PDF Report: Comprehensive assessment with all responses
            - Excel Export: Structured data for further analysis

            Please don't hesitate to contact us if you need any clarification.

            Best regards,
            {survey_data['site_name']} Research Team

            ---
            Generated by SiteSync - AI-Powered Feasibility Platform
            """

            msg.attach(MIMEText(body, 'plain'))

            # Attach PDF
            pdf_attachment = MIMEBase('application', 'pdf')
            pdf_attachment.set_payload(pdf_bytes)
            encoders.encode_base64(pdf_attachment)
            pdf_attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="Feasibility_{survey_data["study_name"].replace(" ", "_")}.pdf"'
            )
            msg.attach(pdf_attachment)

            # Attach Excel
            excel_attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            excel_attachment.set_payload(excel_bytes)
            encoders.encode_base64(excel_attachment)
            excel_attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="Feasibility_{survey_data["study_name"].replace(" ", "_")}.xlsx"'
            )
            msg.attach(excel_attachment)

            # Send email (commented out for demo - would need real SMTP credentials)
            # with smtplib.SMTP(smtp_server, smtp_port) as server:
            #     server.starttls()
            #     server.login(sender_email, sender_password)
            #     server.send_message(msg)

            # For demo purposes, just return True
            print(f"Email would be sent to {to_email} with attachments")
            return True

        except Exception as e:
            print(f"Email sending failed: {e}")
            return False