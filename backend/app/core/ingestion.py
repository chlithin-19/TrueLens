import os
import logging
import urllib.request
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import trafilatura
from newspaper import Article as NewspaperArticle
import fitz # PyMuPDF

logger = logging.getLogger("truelens.ingestion")

def ingest_from_url(url: str) -> dict:
    """
    Ingests and extracts clean article content from a news URL.
    Uses newspaper4k, trafilatura, and BeautifulSoup fallbacks.
    """
    logger.info(f"Ingesting URL: {url}")
    
    title = ""
    content = ""
    author = None
    publication = None
    published_date = None
    
    # 1. Newspaper4k extraction
    try:
        newspaper_article = NewspaperArticle(url)
        newspaper_article.download()
        newspaper_article.parse()
        
        title = newspaper_article.title
        content = newspaper_article.text
        if newspaper_article.authors:
            author = ", ".join(newspaper_article.authors)
        if newspaper_article.publish_date:
            published_date = newspaper_article.publish_date.strftime("%b %d, %Y")
    except Exception as e:
        logger.warning(f"Newspaper4k extraction failed for {url}: {e}")

    # 2. Trafilatura extraction (for cleaner, boilerplate-free content)
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted_text = trafilatura.extract(downloaded)
            # If trafilatura succeeded and returned cleaner/longer text, use it
            if extracted_text and len(extracted_text) > len(content):
                content = extracted_text
    except Exception as e:
        logger.warning(f"Trafilatura extraction failed for {url}: {e}")

    # 3. BeautifulSoup fallback
    if not title or not content:
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read()
                soup = BeautifulSoup(html, 'html.parser')
                
                if not title and soup.title:
                    title = soup.title.string.strip()
                if not content:
                    paragraphs = soup.find_all('p')
                    content = "\n\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        except Exception as e:
            logger.error(f"BeautifulSoup fallback failed for {url}: {e}")

    # Set default metadata if not found
    if not title:
        title = urlparse(url).path.split("/")[-1].replace("-", " ").replace("_", " ").title() or "Ingested Web Article"
        
    if not content:
        content = "Could not extract body content from the provided URL. Please verify the link or if the site is protected by anti-scraping measures."
        
    try:
        domain = urlparse(url).netloc
        publication = domain.replace("www.", "")
    except Exception:
        publication = "Web Article"

    return {
        "title": title.strip(),
        "content": content.strip(),
        "author": author or "Staff Reporter",
        "publication": publication,
        "published_date": published_date or "Just Now",
        "url": url,
        "filename": None
    }

def ingest_from_pdf(file_bytes: bytes, filename: str) -> dict:
    """
    Ingests and extracts text from an uploaded PDF file using PyMuPDF.
    """
    logger.info(f"Ingesting PDF: {filename} ({len(file_bytes)} bytes)")
    
    title = ""
    content = ""
    author = None
    publication = "PDF Upload"
    published_date = "Just Now"
    
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        text_pages = []
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text_pages.append(page_text)
                
        content = "\n\n".join(text_pages)
        
        meta = doc.metadata
        if meta:
            if meta.get("title"):
                title = meta.get("title")
            if meta.get("author"):
                author = meta.get("author")
                
        doc.close()
    except Exception as e:
        logger.error(f"PyMuPDF extraction failed for {filename}: {e}")
        content = f"Failed to extract text from PDF document: {str(e)}"

    # Set default metadata if not found
    if not title:
        # Try first line
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        if lines and len(lines[0]) < 120:
            title = lines[0]
        else:
            title = os.path.splitext(filename)[0].replace("-", " ").replace("_", " ").title()

    return {
        "title": title.strip(),
        "content": content.strip(),
        "author": author or "Document Author",
        "publication": publication,
        "published_date": published_date,
        "url": None,
        "filename": filename
    }
