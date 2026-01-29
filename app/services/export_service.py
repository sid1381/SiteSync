from typing import Dict, List
import json
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import io

class ExportService:
    def generate_pdf_export(self, survey_data: Dict, responses: List[Dict], site_profile: Dict = None) -> bytes:
        """Generate PDF export of completed survey with professional styling"""
        buffer = io.BytesIO()

        # Define custom colors
        brand_blue = colors.HexColor('#2563eb')
        light_blue = colors.HexColor('#dbeafe')
        light_gray = colors.HexColor('#f3f4f6')
        dark_gray = colors.HexColor('#374151')
        green = colors.HexColor('#10b981')
        yellow = colors.HexColor('#f59e0b')
        orange = colors.HexColor('#f97316')

        # Create PDF with custom page template
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                               topMargin=0.75*inch, bottomMargin=0.75*inch,
                               leftMargin=0.75*inch, rightMargin=0.75*inch)

        styles = getSampleStyleSheet()

        # Custom styles
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=12
        )

        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=brand_blue,
            spaceAfter=6,
            spaceBefore=12
        )

        # Cell style for text wrapping
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,  # line spacing
            wordWrap='CJK'  # enables wrapping
        )

        story = []

        # 1. HEADER BANNER
        header_table = Table([['Feasibility Assessment Report']], colWidths=[6.5*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), brand_blue),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 18),
            ('TOPPADDING', (0, 0), (-1, -1), 16),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 20))

        # 2. METADATA CARD with prominent score
        feasibility_score = survey_data.get('feasibility_score', 'N/A')
        completion_pct = survey_data.get('completion_percentage', 0)

        # Determine score color
        if isinstance(feasibility_score, (int, float)):
            if feasibility_score >= 80:
                score_color = green
            elif feasibility_score >= 60:
                score_color = yellow
            else:
                score_color = orange
        else:
            score_color = dark_gray

        # Score display
        score_table = Table([[f"Feasibility Score: {feasibility_score}/100"]], colWidths=[6.5*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), light_gray),
            ('TEXTCOLOR', (0, 0), (-1, -1), score_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 16),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 12))

        # Metadata details
        metadata = [
            ["Sponsor:", survey_data['sponsor_name']],
            ["Study:", survey_data['study_name']],
            ["NCT Number:", survey_data.get('nct_number', 'N/A')],
            ["Site:", survey_data['site_name']],
            ["Completion Rate:", f"{completion_pct:.1f}%"],
            ["Report Generated:", datetime.now().strftime("%B %d, %Y at %I:%M %p")]
        ]

        metadata_table = Table(metadata, colWidths=[140, 360])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), light_gray),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), dark_gray),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(metadata_table)
        story.append(Spacer(1, 24))

        # Separate objective and subjective
        objective_responses = [r for r in responses if r.get('is_objective')]
        subjective_responses = [r for r in responses if not r.get('is_objective')]

        # 3. OBJECTIVE SECTION
        if objective_responses:
            story.append(Paragraph("Objective Responses (AI Auto-filled)", section_style))
            story.append(Spacer(1, 8))

            # Table headers
            obj_data = [['#', 'Question', 'Answer', 'Confidence']]

            # Add response rows
            for resp in objective_responses:
                # Strip 'q_' prefix from question numbers
                question_num = str(resp.get('question_number', ''))
                if question_num.startswith('q_'):
                    question_num = question_num[2:]

                question_text = resp.get('question_text', resp.get('text', 'N/A'))
                response_text = str(resp.get('response', 'N/A'))

                # Wrap text in Paragraph objects for proper wrapping
                question_cell = Paragraph(question_text, cell_style)
                answer_cell = Paragraph(response_text, cell_style)

                confidence = resp.get('confidence', 0)
                if confidence:
                    conf_text = f"{confidence:.0f}%"
                else:
                    conf_text = "N/A"

                obj_data.append([
                    question_num,
                    question_cell,
                    answer_cell,
                    conf_text
                ])

            obj_table = Table(obj_data, colWidths=[25, 220, 180, 55])

            # Build style with alternating light blue rows
            table_style = [
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), brand_blue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

                # Data rows
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),

                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_blue]),
            ]

            # Color-code confidence scores
            for i, resp in enumerate(objective_responses, start=1):
                confidence = resp.get('confidence', 0)
                if confidence >= 80:
                    table_style.append(('TEXTCOLOR', (3, i), (3, i), green))
                elif confidence >= 60:
                    table_style.append(('TEXTCOLOR', (3, i), (3, i), yellow))
                elif confidence > 0:
                    table_style.append(('TEXTCOLOR', (3, i), (3, i), orange))

            obj_table.setStyle(TableStyle(table_style))
            story.append(obj_table)
            story.append(Spacer(1, 20))

        # 4. SUBJECTIVE SECTION
        if subjective_responses:
            story.append(Paragraph("Subjective Responses (Requires Manual Review)", section_style))
            story.append(Spacer(1, 8))

            subj_data = [['#', 'Question', 'Answer']]

            for resp in subjective_responses:
                # Strip 'q_' prefix
                question_num = str(resp.get('question_number', ''))
                if question_num.startswith('q_'):
                    question_num = question_num[2:]

                question_text = resp.get('question_text', resp.get('text', 'N/A'))
                response_text = resp.get('response', 'No response provided')

                # Wrap text in Paragraph objects for proper wrapping
                question_cell = Paragraph(question_text, cell_style)
                answer_cell = Paragraph(response_text, cell_style)

                subj_data.append([
                    question_num,
                    question_cell,
                    answer_cell
                ])

            subj_table = Table(subj_data, colWidths=[25, 220, 235])
            subj_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), brand_blue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

                # Data rows
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),

                # Grid and alternating rows
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_blue]),
            ]))
            story.append(subj_table)
            story.append(Spacer(1, 10))

        # 5. FOOTER with page numbers
        def add_page_number(canvas, doc):
            page_num = canvas.getPageNumber()
            text = f"Page {page_num}"
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(dark_gray)
            canvas.drawRightString(7.5*inch, 0.5*inch, text)
            canvas.drawString(0.75*inch, 0.5*inch, f"Generated by SiteSync | {datetime.now().strftime('%Y-%m-%d')}")

        # Build PDF with page numbers
        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        pdf = buffer.getvalue()
        buffer.close()

        return pdf

    def generate_excel_export(self, survey_data: Dict, responses: List[Dict], site_profile: Dict = None) -> bytes:
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

            # Responses sheet - all questions and answers
            if responses:
                responses_data = []
                for resp in responses:
                    # Get question number and strip 'q_' prefix if present
                    question_num = resp.get('question_number', resp.get('id', ''))
                    if isinstance(question_num, str) and question_num.startswith('q_'):
                        question_num = question_num[2:]

                    # Get question text
                    question_text = resp.get('question_text', resp.get('text', 'N/A'))

                    # Get answer/response
                    answer = resp.get('response', '')

                    # Determine type
                    question_type = 'Objective' if resp.get('is_objective') else 'Subjective'

                    # Get confidence (only for objective questions)
                    confidence = ''
                    if resp.get('is_objective') and resp.get('confidence'):
                        confidence = f"{resp.get('confidence', 0):.0f}%"

                    responses_data.append({
                        '#': question_num,
                        'Question': question_text,
                        'Answer': answer,
                        'Type': question_type,
                        'Confidence': confidence
                    })

                responses_df = pd.DataFrame(responses_data)
                responses_df.to_excel(writer, sheet_name='Responses', index=False)

            # Scoring breakdown sheet
            if survey_data.get('score_breakdown'):
                breakdown_data = []
                for category, details in survey_data['score_breakdown'].items():
                    # Handle both int and dict formats
                    if isinstance(details, dict):
                        score = details.get('score', 0)
                        weight = details.get('weight', 0)
                        weighted_score = details.get('weighted_score', 0)
                    else:
                        # It's just an integer
                        score = details
                        weight = 0
                        weighted_score = 0

                    breakdown_data.append({
                        'Category': category,
                        'Score': score,
                        'Weight': weight,
                        'Weighted Score': weighted_score
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