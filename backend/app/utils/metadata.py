import os
import re
from datetime import datetime
from typing import Optional, Dict, Any
from pypdf import PdfReader

def extract_pdf_global_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extracts global metadata like author and year from a PDF file using pypdf.
    
    Args:
        file_path (str): Path to the PDF file on disk.
        
    Returns:
        Dict[str, Any]: Dictionary containing 'author' and 'year'.
    """
    metadata = {"author": "Unknown", "year": None}
    if not os.path.exists(file_path):
        return metadata

    try:
        reader = PdfReader(file_path)
        info = reader.metadata
        
        # 1. Extract Author from PDF standard fields
        if info and info.author:
            metadata["author"] = info.author.strip()
        
        # 2. Extract Year from creation date
        if info and info.get("/CreationDate"):
            creation_date = info.get("/CreationDate")
            match = re.search(r"D:(\d{4})", creation_date)
            if match:
                metadata["year"] = int(match.group(1))
        
        # Fallback: Parse the first page text for a publication year
        if metadata["year"] is None and len(reader.pages) > 0:
            first_page_text = reader.pages[0].extract_text() or ""
            current_year = datetime.now().year
            years = re.findall(r"\b(19\d{2}|20[0-2]\d)\b", first_page_text)
            if years:
                for y in years:
                    yi = int(y)
                    if 1980 <= yi <= current_year + 1:
                        metadata["year"] = yi
                        break
    except Exception as e:
        print(f"Error extracting PDF global metadata: {str(e)}")
        
    return metadata

def detect_section(text: str, current_section: Optional[str] = None) -> str:
    """
    Analyzes the text chunk to check if a new section heading is defined.
    If yes, returns the new section name. Otherwise, returns the current active section.
    
    Args:
        text (str): The chunk text.
        current_section (Optional[str]): The currently active section name.
        
    Returns:
        str: The resolved section name.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    common_sections = [
        "abstract", "introduction", "methodology", "methods", "experiments",
        "related work", "relatedwork", "results", "discussion", "conclusion", 
        "conclusions", "references", "acknowledgements", "future work"
    ]
    
    # Check the first few lines of the text chunk for a header pattern
    for line in lines[:3]:
        # Match numbered headers (e.g. 1. Introduction, II. Methodology)
        heading_match = re.match(
            r"^(?:(?:[I|V|X|L|C]+|\d+(?:\.\d+)*)\.?\s+)?([A-Z][A-Za-z\s\-]+)$", 
            line
        )
        if heading_match:
            candidate = heading_match.group(1).strip()
            if candidate.lower() in common_sections:
                return candidate.title()
            if len(candidate) < 40 and not candidate.endswith(".") and not candidate.endswith(","):
                return candidate.title()
                
        # Direct check for section headers in lowercase
        for sec in common_sections:
            if line.lower() == sec or line.lower().startswith(sec + " ") or line.lower().endswith(" " + sec):
                if len(line) < 40:
                    return sec.title()
                    
    return current_section or "Main Body"
