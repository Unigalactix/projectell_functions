import azure.functions as func
import logging
import json
import requests # For making HTTP calls to external APIs
import openai
import os

# This 'app' object is crucial for defining your functions
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Example: Simple in-memory rules for demonstration.
GIFTED_RULES = {
    "min_math_score": 90,
    "min_english_score": 90,
    "min_gpa": 3.8,
    "keywords_gifted": ["prodigy", "exceptional", "advanced", "brilliant"]
}

@app.route(route="EvaluateRules") # This decorator defines the HTTP trigger and its route
def EvaluateRules(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function (EvaluateRules) processed a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
             "Please pass a JSON body with student data.",
             status_code=400
        )

    student_data = req_body
    is_gifted_by_rules = False
    rule_reasons = []

    # Rule 1: High Scores and GPA
    if (student_data.get('MathScore', 0) >= GIFTED_RULES['min_math_score'] and
        student_data.get('EnglishScore', 0) >= GIFTED_RULES['min_english_score'] and
        student_data.get('GPA', 0.0) >= GIFTED_RULES['min_gpa']):
        is_gifted_by_rules = True
        rule_reasons.append("High Scores and GPA met thresholds.")

    # Rule 2: Keywords in Teacher Notes
    teacher_notes = student_data.get('TeacherNotes', '').lower()
    if any(keyword in teacher_notes for keyword in GIFTED_RULES['keywords_gifted']):
        is_gifted_by_rules = True
        rule_reasons.append("Teacher notes contain gifted keywords.")

    response_payload = {
        "StudentID": student_data.get('StudentID'),
        "IsGiftedByRules": is_gifted_by_rules,
        "RuleReasons": rule_reasons
    }

    return func.HttpResponse(
        json.dumps(response_payload),
        mimetype="application/json",
        status_code=200
    )

# Retrieve Azure OpenAI credentials from environment variables
# These will be set in Azure Function App's "Configuration -> Application settings"
# For local testing, you might set them in local.settings.json
openai.api_key = os.environ.get("OPENAI_API_KEY", "YOUR_AZURE_OPENAI_API_KEY_FOR_LOCAL_TESTING_ONLY")
openai.api_base = os.environ.get("OPENAI_API_BASE", "YOUR_AZURE_OPENAI_ENDPOINT_FOR_LOCAL_TESTING_ONLY")
openai.api_type = "azure"
openai.api_version = "2023-05-15" # Or your deployed API version

AZURE_OPENAI_MODEL_NAME = os.environ.get("AZURE_OPENAI_MODEL_NAME", "YOUR_DEPLOYMENT_NAME_FOR_LOCAL_TESTING_ONLY")

@app.route(route="ClassifyStudentAI") # This decorator defines the HTTP trigger and its route
def ClassifyStudentAI(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function (ClassifyStudentAI) processed a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
             "Please pass a JSON body with student data for AI classification.",
             status_code=400
        )

    student_data = req_body
    student_id = student_data.get('StudentID', 'N/A')

    prompt = f"""
    Analyze the following student profile to determine if they exhibit characteristics of a gifted or talented student.
    Focus on academic achievements, unique interests, critical thinking, creativity, and teacher observations.
    Respond with "Yes" or "No" and provide a brief justification (1-2 sentences).

    Student Profile:
    Name: {student_data.get('Name')}
    Age: {student_data.get('Age')}
    Grade Level: {student_data.get('GradeLevel')}
    Math Score: {student_data.get('MathScore')}
    English Score: {student_data.get('EnglishScore')}
    GPA: {student_data.get('GPA')}
    Extracurricular Activities: {student_data.get('ExtracurricularActivities')}
    Teacher Notes: {student_data.get('TeacherNotes')}

    Is this student potentially gifted or talented?
    """

    try:
        response = openai.chat.completions.create(
            model=AZURE_OPENAI_MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are an AI assistant helping to identify gifted students based on provided profiles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        ai_classification_text = response.choices[0].message.content.strip()
        is_gifted_by_ai = "Yes" in ai_classification_text
        ai_reason = ai_classification_text.replace("Yes", "").replace("No", "").strip(".: ").strip()

    except Exception as e:
        logging.error(f"Error calling Azure OpenAI: {e}")
        # Do not return sensitive error messages to client in production
        return func.HttpResponse(
            f"Error processing AI classification: {e}",
            status_code=500
        )

    response_payload = {
        "StudentID": student_id,
        "IsGiftedByAI": is_gifted_by_ai,
        "AIReason": ai_reason
    }

    return func.HttpResponse(
        json.dumps(response_payload),
        mimetype="application/json",
        status_code=200
    )