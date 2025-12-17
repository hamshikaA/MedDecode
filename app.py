from flask import Flask, render_template, request, send_file
import os
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from google import genai
from gtts import gTTS
from deep_translator import GoogleTranslator

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\poppler-24.02.0\Library\bin"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)
HOVER_DICT = {
    'Blood Pressure': 'Force of blood against blood vessels.',
    'Heart Rate': 'Number of heartbeats per minute.',
    'Symptoms': 'Indicators of what may be going on in the body.',
    'Medications': 'Prescribed medicines taken by patient.',
    'bpm': 'Beats per minute, measurement of heart rate.'
}
def translate_text_func(text, lang):
    if lang == 'en':
        return text
    else:
        return GoogleTranslator(source='auto', target=lang).translate(text)
def extract_insights(text):
    lines = text.split("\n")
    insights = []
    for line in lines:
        if any(kw in line for kw in ['Blood Pressure','Heart Rate','Symptoms','Medications']):
            insights.append(line.strip())
    return insights

@app.route("/", methods=["GET", "POST"])
def index():
    output = None
    error = None
    translations = {"en": "", "ta": "", "hi": ""}
    audio_files = {"en": "", "ta": "", "hi": ""}
    hover_terms = []
    insights = []
    if request.method == "POST":
        try:
            if "file" not in request.files:
                error = "No file uploaded"
            else:
                file = request.files["file"]

                if file.filename == "":
                    error = "No file selected"
                else:
                    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                    file.save(file_path)

                    extracted_text = ""

                    if file.filename.lower().endswith(".pdf"):
                        images = convert_from_path(
                            file_path,
                            poppler_path=POPPLER_PATH
                        )
                        for img in images:
                            extracted_text += pytesseract.image_to_string(img)
                    else:
                        extracted_text = pytesseract.image_to_string(
                            Image.open(file_path)
                        )

                    if extracted_text.strip() == "":
                        error = "Could not extract text from file"
                    else:
                        prompt = f"""
Explain the following medical report in very simple English.
Rules:
- Do NOT include any introductory line
- Do NOT diagnose
- Do NOT give medical advice
- No bullet points
-Explain all pointsclearly
-step by step explanation no any numbers
Medical Report:
{extracted_text}
"""

                        try:
                            response = client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=[prompt]
                            )
                            output_en = response.text
                        except Exception:
                            error = "AI limit reached. Please wait 1 minute and try again."
                            return render_template(
                                "index.html",
                                error=error
                            )

                        translations["en"] = output_en
                        translations["ta"] = translate_text_func(output_en, "ta")
                        translations["hi"] = translate_text_func(output_en, "hi")

                        for lang_code, tts_lang in {
                            "en": "en",
                            "ta": "ta",
                            "hi": "hi"
                        }.items():
                            audio_path = os.path.join(
                                UPLOAD_FOLDER,
                                f"output_{lang_code}.mp3"
                            )
                            tts = gTTS(
                                text=translations[lang_code],
                                lang=tts_lang
                            )
                            tts.save(audio_path)
                            audio_files[lang_code] = f"/static/uploads/output_{lang_code}.mp3"

                        insights = extract_insights(output_en)
                        hover_terms = list(HOVER_DICT.keys())
                        output = output_en

        except Exception as e:
            error = f"Unexpected error: {str(e)}"

    return render_template(
        "index.html",
        output=output,
        error=error,
        translations=translations,
        audio_files=audio_files,
        hover_terms=hover_terms,
        insights=insights
    )

@app.route("/download/<lang>")
def download_audio(lang):
    audio_path = os.path.join(UPLOAD_FOLDER, f"output_{lang}.mp3")
    if os.path.exists(audio_path):
        return send_file(audio_path, as_attachment=True)
    else:
        return "File not found", 404

if __name__=="__main__":
    app.run(debug=True)
