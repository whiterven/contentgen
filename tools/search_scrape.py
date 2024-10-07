import os
import requests
import json
import re
from bs4 import BeautifulSoup
from crewai_tools import BaseTool
from typing import Optional, List, Dict
from pydantic import Field
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
from heapq import nlargest
from datetime import datetime
from urllib.parse import urlparse
import math

class AdvancedSerperSearchTool(BaseTool):
    name: str = "Advanced Serper Web Search, Scraper, and Analyzer"
    description: str = "A tool to search the web using serper.dev API, scrape content, filter unwanted text, summarize content, extract keywords, estimate reading time, assess source credibility, and return structured data in JSON format."
    api_key: str = Field(default_factory=lambda: os.environ.get("SERPER_API_KEY"))
    base_url: str = Field(default="https://google.serper.dev/search")

    def __init__(self, **data):
        super().__init__(**data)
        if not self.api_key:
            raise ValueError("SERPER_API_KEY environment variable is not set")
        # Download necessary NLTK data
        import nltk
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)

    def _run(self, query: str) -> str:
        search_results = self._search(query)
        analyzed_data = self._scrape_and_analyze(search_results)
        return json.dumps(analyzed_data, indent=2, default=str)

    def _search(self, query: str) -> List[Dict]:
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        payload = {'q': query}

        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            results = response.json()
            return results.get('organic', [])[:5]  # Limit to top 5 results
        except requests.exceptions.RequestException as e:
            return [{"error": f"An error occurred while searching: {str(e)}"}]

    def _scrape_and_analyze(self, search_results: List[Dict]) -> List[Dict]:
        analyzed_data = []
        for result in search_results:
            url = result.get('link')
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')

                # Extract and clean content
                title = self._clean_text(soup.title.string) if soup.title else "No title found"
                paragraphs = [self._clean_text(p.text) for p in soup.find_all('p') if self._is_relevant_paragraph(p.text)]

                # Combine paragraphs
                full_text = ' '.join(paragraphs)

                # Analyze content
                summary = self._summarize_text(full_text, num_words=500)
                keywords = self._extract_keywords(full_text)
                reading_time = self._estimate_reading_time(full_text)
                credibility_score = self._estimate_credibility(url, soup)

                analyzed_data.append({
                    "url": url,
                    "title": title,
                    "search_snippet": self._clean_text(result.get('snippet', 'No snippet available')),
                    "summary": summary,
                    "keywords": keywords,
                    "reading_time": reading_time,
                    "credibility_score": credibility_score,
                    "scraped_date": datetime.now().isoformat(),
                    "search_date": result.get('date')
                })
            except Exception as e:
                analyzed_data.append({
                    "url": url,
                    "error": f"Failed to scrape or analyze: {str(e)}",
                    "search_snippet": self._clean_text(result.get('snippet', 'No snippet available')),
                    "scraped_date": datetime.now().isoformat(),
                    "search_date": result.get('date')
                })

        return analyzed_data

    def _clean_text(self, text: str) -> str:
        # Remove unwanted phrases
        unwanted_phrases = [
            "sign in", "sign up", "join us", "get started", "subscribe", "cookie",
            "privacy policy", "terms of service", "all rights reserved"
        ]
        cleaned_text = text.lower()
        for phrase in unwanted_phrases:
            cleaned_text = cleaned_text.replace(phrase, "")

        # Remove extra whitespace and capitalize
        cleaned_text = " ".join(cleaned_text.split()).capitalize()

        return cleaned_text

    def _is_relevant_paragraph(self, text: str) -> bool:
        min_length = 50
        unwanted_phrases = [
            "sign in", "sign up", "join us", "get started", "subscribe", "cookie",
            "privacy policy", "terms of service", "all rights reserved"
        ]

        if len(text) < min_length:
            return False

        lower_text = text.lower()
        for phrase in unwanted_phrases:
            if phrase in lower_text:
                return False

        return True

    def _summarize_text(self, text: str, num_words: int = 500) -> str:
        sentences = sent_tokenize(text)
        stop_words = set(stopwords.words('english'))
        word_frequencies = FreqDist(word.lower() for sentence in sentences for word in sentence.split() if word.lower() not in stop_words)

        sentence_scores = {}
        for sentence in sentences:
            for word in sentence.split():
                if word.lower() in word_frequencies:
                    if sentence not in sentence_scores:
                        sentence_scores[sentence] = word_frequencies[word.lower()]
                    else:
                        sentence_scores[sentence] += word_frequencies[word.lower()]

        summary_sentences = nlargest(15, sentence_scores, key=sentence_scores.get)
        summary = ' '.join(summary_sentences)

        words = summary.split()
        if len(words) > num_words:
            summary = ' '.join(words[:num_words]) + '...'

        return summary

    def _extract_keywords(self, text: str, num_keywords: int = 10) -> List[str]:
        words = word_tokenize(text.lower())
        stop_words = set(stopwords.words('english'))
        filtered_words = [word for word in words if word.isalnum() and word not in stop_words]

        word_freq = FreqDist(filtered_words)
        return [word for word, _ in word_freq.most_common(num_keywords)]

    def _estimate_reading_time(self, text: str) -> str:
        words = text.split()
        word_count = len(words)
        reading_time_minutes = math.ceil(word_count / 200)  # Assuming average reading speed of 200 words per minute
        return f"{reading_time_minutes} minute{'s' if reading_time_minutes != 1 else ''}"

    def _estimate_credibility(self, url: str, soup: BeautifulSoup) -> float:
        score = 0.0

        # Domain authority (simplified)
        domain = urlparse(url).netloc
        if any(trusted_domain in domain for trusted_domain in ['.edu', '.gov', '.org']):
            score += 0.3

        # Content length
        content_length = len(soup.get_text())
        if content_length > 2000:
            score += 0.2

        # Presence of author information
        if soup.find('author') or soup.find(class_='author'):
            score += 0.2

        # Presence of references or citations
        if soup.find('cite') or soup.find(class_='reference'):
            score += 0.2

        # HTTPS
        if url.startswith('https'):
            score += 0.1

        return round(score, 2)

