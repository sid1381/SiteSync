import json
from typing import List, Dict, Any
import PyPDF2
import pandas as pd
import re
import io

class SurveyParser:
    def extract_from_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract questions from PDF survey"""
        text = self._extract_pdf_text(pdf_bytes)
        questions = []

        # Parse common survey patterns
        patterns = [
            # Numbered questions: "1. Question text"
            r'(\d+)\.\s*([^?]+\??)',
            # Checkbox questions: "□ Question text"
            r'□\s*([^□\n]+)',
            # Questions with colons: "Field: _____"
            r'([^:]+):\s*_{3,}',
            # Direct questions
            r'([^.!]+\?)'
        ]

        question_id = 1
        seen_questions = set()

        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                question_text = match[-1].strip() if isinstance(match, tuple) else match.strip()

                # Skip if already seen
                if question_text in seen_questions or len(question_text) < 10:
                    continue

                seen_questions.add(question_text)

                # Categorize question type
                question_type = self._determine_question_type(question_text)
                is_objective = self._is_objective_question(question_text)

                questions.append({
                    "id": f"q_{question_id}",
                    "text": question_text,
                    "type": question_type,
                    "is_objective": is_objective,
                    "response": None,
                    "source": None,
                    "confidence": 0
                })
                question_id += 1

        return questions

    def extract_from_excel(self, excel_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract questions from Excel survey"""
        excel_file = io.BytesIO(excel_bytes)

        try:
            df = pd.read_excel(excel_file, sheet_name=0)
            questions = []
            question_id = 1

            # Common column names for questions
            question_columns = ['question', 'item', 'field', 'criteria', 'requirement']

            for col in df.columns:
                if any(q in col.lower() for q in question_columns):
                    for idx, value in df[col].items():
                        if pd.notna(value) and len(str(value)) > 10:
                            question_text = str(value).strip()
                            question_type = self._determine_question_type(question_text)
                            is_objective = self._is_objective_question(question_text)

                            questions.append({
                                "id": f"q_{question_id}",
                                "text": question_text,
                                "type": question_type,
                                "is_objective": is_objective,
                                "response": None,
                                "source": None,
                                "confidence": 0
                            })
                            question_id += 1

            return questions

        except Exception as e:
            print(f"Error parsing Excel: {e}")
            return []

    def _determine_question_type(self, question_text: str) -> str:
        """Determine the type of question"""
        text_lower = question_text.lower()

        if any(word in text_lower for word in ['yes', 'no', '□']):
            return "boolean"
        elif any(word in text_lower for word in ['how many', 'number', 'count', 'quantity']):
            return "number"
        elif any(word in text_lower for word in ['date', 'when', 'timeline']):
            return "date"
        elif any(word in text_lower for word in ['select', 'choose', 'which']):
            return "multiple_choice"
        else:
            return "text"

    def _is_objective_question(self, question_text: str) -> bool:
        """Determine if question can be answered objectively from data"""
        objective_keywords = [
            'equipment', 'certification', 'experience', 'capacity',
            'number of', 'how many', 'volume', 'throughput',
            'square feet', 'staff', 'fte', 'accreditation',
            'emr', 'system', 'capability', 'historical', 'past',
            'completed', 'enrolled', 'rate', 'average'
        ]

        subjective_keywords = [
            'describe', 'explain', 'strategy', 'approach',
            'plan', 'how will', 'what is your', 'rationale',
            'justify', 'elaborate', 'discuss', 'opinion'
        ]

        text_lower = question_text.lower()

        # Check for subjective indicators
        if any(keyword in text_lower for keyword in subjective_keywords):
            return False

        # Check for objective indicators
        if any(keyword in text_lower for keyword in objective_keywords):
            return True

        # Default to subjective for safety
        return False

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF"""
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"

        return text