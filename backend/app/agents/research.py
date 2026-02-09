"""
Research Agent - Uses Google Search for web research and URL content retrieval.
Leverages Gemini's built-in grounding capabilities for reliable web content.
"""

import re
import asyncio
import os
from typing import Optional
from dataclasses import dataclass

from google import genai
from google.genai import types

from ..logging_config import get_logger
from ..config import get_settings

logger = get_logger(__name__)
settings = get_settings()

# Initialize Gemini client
client = genai.Client(api_key=settings.google_api_key)

# URL regex pattern
URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+'
)


@dataclass
class ResearchSource:
    """A source from research grounding."""
    title: str
    url: str


@dataclass
class ResearchResult:
    """Result from research agent."""
    content: str
    sources: list[ResearchSource]
    success: bool
    error: Optional[str] = None


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from the given text."""
    urls = URL_PATTERN.findall(text)
    # Clean up URLs (remove trailing punctuation)
    cleaned = []
    for url in urls:
        # Remove trailing punctuation that might be part of sentence
        url = url.rstrip('.,;:!?)\'"]')
        if url:
            cleaned.append(url)
    return list(set(cleaned))  # Deduplicate


async def research_with_google_search(
    topic: str,
    context: str = "",
    urls: list[str] = None
) -> ResearchResult:
    """
    Research a topic using Google Search through Gemini's grounding.
    
    This uses Gemini's built-in google_search tool which:
    - Performs web searches automatically
    - Retrieves and processes web content
    - Returns grounded responses with source citations
    
    Args:
        topic: The main topic to research
        context: Additional context for the research
        urls: Specific URLs to focus on (if any)
        
    Returns:
        ResearchResult with content and sources
    """
    logger.info(
        "Starting Google Search research",
        extra={'extra_data': {'topic': topic[:100], 'has_urls': bool(urls)}}
    )
    
    # Build the research prompt
    url_instruction = ""
    if urls:
        url_list = "\n".join(f"- {url}" for url in urls[:5])  # Limit to 5 URLs
        url_instruction = f"""
IMPORTANT: The user has provided these specific URLs for reference. 
Search for and include information from these sources:
{url_list}

Make sure to visit and extract relevant content from these URLs.
"""
    
    prompt = f"""Research the following topic thoroughly using web search.

TOPIC: {topic}

ADDITIONAL CONTEXT: {context if context else 'None provided'}

{url_instruction}

Instructions:
1. Search the web for comprehensive, up-to-date information about this topic
2. If specific URLs were provided, make sure to include information from those sources
3. Focus on factual, actionable information that would help with project planning
4. Include technical details, best practices, and practical considerations
5. Organize the information clearly

Provide a detailed research summary with all relevant findings."""

    try:
        # Use Gemini with Google Search grounding
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",  # Flash model works well with search
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        
        content = response.text or ""
        sources: list[ResearchSource] = []
        
        # Extract sources from grounding metadata
        if response.candidates and response.candidates[0].grounding_metadata:
            grounding = response.candidates[0].grounding_metadata
            chunks = grounding.grounding_chunks or []
            
            for chunk in chunks:
                if chunk.web and chunk.web.uri and chunk.web.title:
                    sources.append(ResearchSource(
                        title=chunk.web.title,
                        url=chunk.web.uri
                    ))
            
            # Deduplicate sources by URL
            seen_urls = set()
            unique_sources = []
            for source in sources:
                if source.url not in seen_urls:
                    seen_urls.add(source.url)
                    unique_sources.append(source)
            sources = unique_sources
        
        logger.info(
            "Google Search research completed",
            extra={'extra_data': {
                'content_length': len(content),
                'sources_found': len(sources),
                'source_urls': [s.url for s in sources[:10]]  # Log first 10 source URLs
            }}
        )
        
        # Log each source for debugging
        for i, source in enumerate(sources[:10]):
            logger.info(
                f"Research source {i+1}",
                extra={'extra_data': {'title': source.title[:100], 'url': source.url}}
            )
        
        return ResearchResult(
            content=content,
            sources=sources,
            success=True
        )
        
    except Exception as e:
        logger.error(
            "Google Search research failed",
            extra={'extra_data': {'error': str(e)}},
            exc_info=True
        )
        return ResearchResult(
            content="",
            sources=[],
            success=False,
            error=str(e)
        )


async def research_urls(text: str) -> dict:
    """
    Research based on text content and any URLs found.
    Uses Google Search for comprehensive research.
    
    Returns:
        Dict with 'urls_found', 'research_content', 'sources', 'context_summary', 'success'
    """
    urls = extract_urls(text)
    
    # Clean text for research (remove URLs themselves to focus on the topic)
    research_text = text
    for url in urls:
        research_text = research_text.replace(url, "")
    research_text = research_text.strip()
    
    if not research_text and not urls:
        return {
            'urls_found': [],
            'research_content': None,
            'sources': [],
            'context_summary': None,
            'success': True
        }
    
    logger.info(
        "Starting URL/topic research",
        extra={'extra_data': {'url_count': len(urls), 'urls': urls[:5]}}
    )
    
    # Use Google Search for research
    result = await research_with_google_search(
        topic=research_text or "the provided URLs",
        context="",
        urls=urls if urls else None
    )
    
    # Build context summary
    context_summary = None
    if result.success and result.content:
        # Format sources for context
        source_citations = ""
        if result.sources:
            source_list = "\n".join(
                f"  - {s.title}: {s.url}" 
                for s in result.sources[:10]
            )
            source_citations = f"\n\nSources Referenced:\n{source_list}"
        
        context_summary = f"""
--- WEB RESEARCH FINDINGS ---
{result.content}
{source_citations}
--- END OF RESEARCH ---
"""
    
    return {
        'urls_found': urls,
        'research_content': result.content,
        'sources': [{'title': s.title, 'url': s.url} for s in result.sources],
        'context_summary': context_summary,
        'success': result.success,
        'error': result.error
    }


async def identify_research_terms(
    topic: str,
    clarification_answers: str
) -> list[str]:
    """
    Use LLM to identify terms in the clarification answers that would benefit
    from web research - technical terms, frameworks, tools, methodologies, etc.
    
    Returns:
        List of terms/concepts to research
    """
    if not clarification_answers or len(clarification_answers.strip()) < 10:
        return []
    
    prompt = f"""Analyze the following project topic and user clarification answers.
Identify any specific technical terms, frameworks, libraries, tools, methodologies, 
APIs, services, or concepts that would benefit from web research to better understand
the project requirements.

PROJECT TOPIC: {topic}

USER'S CLARIFICATION ANSWERS:
{clarification_answers}

Rules:
1. Only identify terms that are specific enough to research (not generic words)
2. Focus on: technologies, frameworks, APIs, services, methodologies, tools
3. Ignore common/well-known terms unless context suggests specific usage
4. Return ONLY the terms, one per line
5. Maximum 5 terms (prioritize most important/unclear ones)
6. If everything is clear and well-known, return "NONE"

Return ONLY the terms (one per line) or "NONE":"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1  # Low temperature for consistent extraction
            )
        )
        
        text = response.text.strip() if response.text else ""
        
        if text.upper() == "NONE" or not text:
            return []
        
        # Parse terms (one per line)
        terms = [
            t.strip().strip('-').strip('•').strip() 
            for t in text.split('\n') 
            if t.strip() and t.strip().upper() != "NONE"
        ]
        
        # Filter out very short or generic terms
        terms = [t for t in terms if len(t) > 2 and ' ' not in t or len(t) > 5][:5]
        
        logger.info(
            "Identified research terms from clarification",
            extra={'extra_data': {'terms': terms}}
        )
        
        return terms
        
    except Exception as e:
        logger.error(
            "Failed to identify research terms",
            extra={'extra_data': {'error': str(e)}},
            exc_info=True
        )
        return []


async def research_terms(
    terms: list[str],
    project_topic: str
) -> ResearchResult:
    """
    Research specific terms/concepts using Google Search.
    
    Args:
        terms: List of terms to research
        project_topic: The overall project context
        
    Returns:
        ResearchResult with combined findings
    """
    if not terms:
        return ResearchResult(content="", sources=[], success=True)
    
    logger.info(
        "Researching unfamiliar terms",
        extra={'extra_data': {'terms': terms, 'topic': project_topic[:100]}}
    )
    
    terms_list = ", ".join(terms)
    
    prompt = f"""Research the following technical terms/concepts in the context of this project.

PROJECT CONTEXT: {project_topic}

TERMS TO RESEARCH: {terms_list}

For each term, provide:
1. What it is (brief definition)
2. How it's typically used
3. Key considerations for project planning
4. Any prerequisites or dependencies

Focus on practical information that would help with project planning and estimation."""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        
        content = response.text or ""
        sources: list[ResearchSource] = []
        
        # Extract sources from grounding metadata
        if response.candidates and response.candidates[0].grounding_metadata:
            grounding = response.candidates[0].grounding_metadata
            chunks = grounding.grounding_chunks or []
            
            for chunk in chunks:
                if chunk.web and chunk.web.uri and chunk.web.title:
                    sources.append(ResearchSource(
                        title=chunk.web.title,
                        url=chunk.web.uri
                    ))
            
            # Deduplicate
            seen_urls = set()
            unique_sources = []
            for source in sources:
                if source.url not in seen_urls:
                    seen_urls.add(source.url)
                    unique_sources.append(source)
            sources = unique_sources
        
        logger.info(
            "Term research completed",
            extra={'extra_data': {
                'terms_researched': len(terms),
                'content_length': len(content),
                'sources_found': len(sources)
            }}
        )
        
        return ResearchResult(
            content=content,
            sources=sources,
            success=True
        )
        
    except Exception as e:
        logger.error(
            "Term research failed",
            extra={'extra_data': {'error': str(e)}},
            exc_info=True
        )
        return ResearchResult(
            content="",
            sources=[],
            success=False,
            error=str(e)
        )


async def auto_research_context(
    topic: str,
    context: str
) -> dict:
    """
    Automatically identify and research unfamiliar terms from context.
    This is the main entry point for automatic research.
    
    Args:
        topic: The project topic
        context: User's clarification answers and additional context
        
    Returns:
        Dict with 'terms_found', 'research_content', 'sources', 'context_summary', 'success'
    """
    # Step 1: Identify terms that need research
    terms = await identify_research_terms(topic, context)
    
    if not terms:
        logger.info("No unfamiliar terms identified for research")
        return {
            'terms_found': [],
            'research_content': None,
            'sources': [],
            'context_summary': None,
            'success': True
        }
    
    # Step 2: Research the identified terms
    result = await research_terms(terms, topic)
    
    # Build context summary
    context_summary = None
    if result.success and result.content:
        source_citations = ""
        if result.sources:
            source_list = "\n".join(
                f"  - {s.title}: {s.url}" 
                for s in result.sources[:10]
            )
            source_citations = f"\n\nSources Referenced:\n{source_list}"
        
        context_summary = f"""
--- AUTOMATIC RESEARCH: Technical Terms ---
Terms Researched: {', '.join(terms)}

{result.content}
{source_citations}
--- END OF AUTOMATIC RESEARCH ---
"""
    
    return {
        'terms_found': terms,
        'research_content': result.content,
        'sources': [{'title': s.title, 'url': s.url} for s in result.sources],
        'context_summary': context_summary,
        'success': result.success,
        'error': result.error
    }
