import collections, collections.abc

# --- Python 3.13 fix for PyPDF2 (Deque removed from typing) ---
try:
    from typing import Deque
except ImportError:
    from collections import deque as Deque
    import typing
    typing.Deque = Deque
import glob
import os
import warnings
import PyPDF2
import docx2txt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


warnings.filterwarnings("ignore")


class ResultElement:
    def __init__(self, rank, filename, score):
        self.rank = rank
        self.filename = filename
        self.score = score


def getfilepath(loc):
    temp = str(loc)
    temp = temp.replace('\\', '/')
    return temp


def read_resume(filepath):
    """Read PDF or DOCX safely"""
    ext = filepath.lower().split(".")[-1]
    text = ""
    if ext == "pdf":
        try:
            with open(filepath, "rb") as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                for page in reader.pages:
                    text += page.extract_text() or ""
        except Exception as e:
            text = f"[Error reading PDF: {e}]"
    elif ext == "docx":
        try:
            text = docx2txt.process(filepath)
        except Exception as e:
            text = f"[Error reading DOCX: {e}]"
    elif ext == "txt":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    return text.replace("\n", " ")


def summarize_text(text, max_sentences=5):
    """Simple summarizer — just first few sentences"""
    sentences = text.replace("\n", " ").split(". ")
    return ". ".join(sentences[:max_sentences])


def res(jobfile):
    """Main resume screening function"""
    resumes_dir = "./Original_Resumes"
    job_dir = "./Job_Description"

    resume_files = glob.glob(os.path.join(resumes_dir, "**/*.*"), recursive=True)
    resume_texts = []
    resume_names = []

    for filepath in resume_files:
        if filepath.lower().endswith((".pdf", ".docx", ".txt")):
            resume_names.append(os.path.basename(filepath))
            resume_texts.append(read_resume(filepath))

    # --- read job description ---
    job_path = os.path.join(job_dir, jobfile)
    if not os.path.exists(job_path):
        raise FileNotFoundError(f"Job description file not found: {job_path}")

    with open(job_path, "r", encoding="utf-8", errors="ignore") as f:
        job_text = f.read()

    job_summary = summarize_text(job_text)
    corpus = [job_summary] + [summarize_text(r) for r in resume_texts]

    # --- TF-IDF similarity ---
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf = vectorizer.fit_transform(corpus)
    similarities = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

    ranked = sorted(zip(similarities, resume_names), key=lambda x: x[0], reverse=True)

    flask_return = []
    for idx, (score, name) in enumerate(ranked, 1):
        print(f"Rank {idx}: {name} — Score {round(score,3)}")
        flask_return.append(ResultElement(rank=idx, filename=name, score=round(score * 100, 2)))


    return flask_return


if __name__ == "__main__":
    print("Run via Flask — not standalone.")
