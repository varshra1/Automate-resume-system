import glob
import os
import warnings
import PyPDF2
from collections import Counter
from math import sqrt
# The following imports and associated logic have been removed or replaced 
# to eliminate dependencies that cause ModuleNotFound errors in this environment.
# Removed: textract, gensim, sklearn, nltk, inflect, autocorrect

# Note: The warnings filter for 'gensim' is kept but is now unnecessary
# since gensim is no longer used, but keeping it is harmless.
warnings.filterwarnings(action='ignore', category=UserWarning, module='gensim')

class ResultElement:
    """A simple data structure to hold the rank, filename, and score for results."""
    # Score is now mandatory in the constructor
    def __init__(self, rank, filename, score):
        self.rank = rank
        self.filename = filename
        self.score = score # Similarity score (0.0 to 100.0)

# --- Custom Vectorization and Similarity Logic (Replaces sklearn) ---

# Standard English stop words list used for basic text cleanup
STOP_WORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", 
    "you'll", "you'd", 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 
    'himself', 'she', "she's", 'her', 'hers', 'herself', 'it', "it's", 'its', 'itself', 
    'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 
    'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 
    'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 
    'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 
    'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 
    'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 
    'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 
    'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 
    'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 
    's', 't', 'can', 'will', 'just', 'don', "don't", 'should', "should've", 'now', 'd', 
    'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't", 'didn', 
    "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 
    'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 
    'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't", 'weren', "weren't", 'won', 
    "won't", 'wouldn', "wouldn't", 'english'
}

def tokenize_and_count(text, stop_words):
    """Simple tokenizer and word counter (Count Vectorizer replacement)."""
    # Simple lowercasing and splitting by non-alphanumeric characters
    import re
    words = re.findall(r'\b\w+\b', text.lower())
    # Filter words against the stop words list
    return Counter(word for word in words if word not in stop_words)

def calculate_cosine_similarity(vec1_counts, vec2_counts):
    """
    Calculates the cosine similarity between two count vectors.
    This replaces the NearestNeighbors distance calculation for scoring.
    """
    intersection = set(vec1_counts.keys()) & set(vec2_counts.keys())
    
    # 1. Dot Product (numerator)
    dot_product = sum(vec1_counts[word] * vec2_counts[word] for word in intersection)

    # 2. Vector Magnitudes (denominator)
    magnitude1 = sqrt(sum(count**2 for count in vec1_counts.values()))
    magnitude2 = sqrt(sum(count**2 for count in vec2_counts.values()))

    # Avoid division by zero
    if not magnitude1 or not magnitude2:
        return 0.0
    
    # Cosine Similarity Formula
    return dot_product / (magnitude1 * magnitude2)

# --- End Custom Logic ---

def getfilepath(loc):
    """Normalizes the file path string."""
    temp = str(loc)
    temp = temp.replace('\\', '/')
    return temp


def res(jobfile):
    """
    Core function to screen resumes against a job description using
    custom Count Vectorization and Cosine Similarity.
    
    NOTE: Only PDF files are supported due to lack of dependencies for .doc/.docx formats.
    """
    Ordered_list_Resume = []
    Ordered_list_Resume_Score = []
    LIST_OF_FILES_PDF = []
    Resumes = []
    
    # 1. Collect Files (Only PDFs due to missing dependencies for .doc/.docx)
    try:
        os.chdir('./Original_Resumes')
    except FileNotFoundError:
        print("Error: Could not find 'Original_Resumes' directory.")
        return []

    for file in glob.glob('**/*.pdf', recursive=True):
        LIST_OF_FILES_PDF.append(file)
        
    LIST_OF_FILES = LIST_OF_FILES_PDF 
    
    print("This is LIST OF FILES to process (only PDFs):", LIST_OF_FILES)


    # 2. Parse Files
    print("####### PARSING ########")
    for nooo, i in enumerate(LIST_OF_FILES):
        Ordered_list_Resume.append(i)
        
        try:
            print("Processing PDF", nooo, ":", i)
            page_content_combined = ''
            with open(i,'rb') as pdf_file:
                # Use PyPDF2.PdfReader (updated from deprecated PdfFileReader)
                read_pdf = PyPDF2.PdfReader(pdf_file)
                # Note: PyPDF2.PdfReader uses len(reader.pages) instead of getNumPages()
                number_of_pages = len(read_pdf.pages)
                
                for page in read_pdf.pages:
                    page_content = page.extract_text()
                    if page_content:
                        page_content_combined += page_content.replace('\n', ' ')
                
                Resumes.append(page_content_combined)
                
        except Exception as e: 
            print(f"Error reading PDF {i}: {e}. Skipping this file.")
            Resumes.append("") # Add empty string to maintain list length
    
    os.chdir('../') # Go back up to the root folder
    print("Done Parsing.")

    # 3. Process Job Description (JD)
    job_desc_path = os.path.join('./Job_Description', jobfile)
    jd_text = ''
    
    try:
        with open(job_desc_path , 'r', encoding='utf-8') as f:
            jd_text = f.read()
    except Exception as e:
        print(f"Error reading Job Description: {e}")
        return []

    # 4. Generate Count Vectors for JD and Resumes
    
    # JD Vector
    jd_vector_counts = tokenize_and_count(jd_text, STOP_WORDS)
    if not jd_vector_counts:
        print("Error: Job Description has no meaningful content for comparison.")
        return []
    
    # Resume Vectors
    resume_vectors_counts = []
    for resume_text in Resumes:
        # Generate count vector for the resume text
        resume_vectors_counts.append(tokenize_and_count(resume_text, STOP_WORDS))


    # 5. Calculate Scores (Cosine Similarity)
    for idx, resume_vector in enumerate(resume_vectors_counts):
        try:
            score = calculate_cosine_similarity(jd_vector_counts, resume_vector)
            Ordered_list_Resume_Score.append(score)
            
        except Exception as e:
            # Append a very low score for failed calculations (pushes to the end)
            Ordered_list_Resume_Score.append(-1.0) 
            print(f"Error during Cosine Similarity calculation for resume {Ordered_list_Resume[idx]}: {e}")


    # 6. Sort and Return Results
    # We sort in DESCENDING order of score, as higher cosine similarity means a better match.
    
    zipped_lists = sorted(
        zip(Ordered_list_Resume_Score, Ordered_list_Resume), 
        key=lambda x: x[0], 
        reverse=True # Highest score first
    )
    
    flask_return = []
    rank_counter = 1
    for score, filename in zipped_lists:
        if score > 0.0: # Only include resumes with a similarity score
            name = getfilepath(filename)
            # Convert score (0.0 to 1.0) to a percentage (0.0% to 100.0%)
            score_percent = round(score * 100, 2)
            res = ResultElement(rank_counter, name, score_percent) 
            flask_return.append(res)
            print(f"Rank {rank_counter} :\t {res.filename} (Score: {res.score}%)")
            rank_counter += 1
        
    return flask_return


if __name__ == '__main__':
    pass 
