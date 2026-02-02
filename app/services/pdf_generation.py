"""PDF summary, questions, and report generation using LangChain and PyMuPDF."""
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, List

import fitz  # PyMuPDF
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import settings


# Storage base for generated .md files (same parent as local_storage)
STORAGE_DIR = Path("datasets")


def _extract_text_from_pdf(pdf_content: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    text = "\n\n".join(text_parts).strip()
    if not text:
        raise ValueError("No text could be extracted from the PDF.")
    # Truncate if very long to avoid token limits (keep ~100k chars as safe limit)
    max_chars = 120_000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... document truncated for processing ...]"
    return text


def _get_llm():
    """Create LangChain ChatOpenAI with model from settings."""
    model = getattr(settings, "OPENAI_MODEL", "gpt-4o") or "gpt-4o"
    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to .env.")
    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        temperature=0.3,
    )


def _generate_summary_sync(text: str, doc_name: str) -> str:
    """Generate summary from PDF text (runs in thread)."""
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert at summarizing documents. Produce a clear, concise summary."),
        ("human", "Summarize the following document in 2–4 paragraphs. Focus on main topics, findings, and conclusions.\n\nDocument name: {doc_name}\n\nContent:\n{content}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"doc_name": doc_name, "content": text[:80_000]})


def _generate_questions_sync(text: str, doc_name: str) -> List[str]:
    """Generate suggested questions from PDF text (runs in thread)."""
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You generate insightful questions that a user could ask about a document. Return only a numbered list of questions, one per line, no other text."),
        ("human", "Based on this document, generate 5–8 specific questions a user might ask to understand it better.\n\nDocument: {doc_name}\n\nContent:\n{content}"),
    ])
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"doc_name": doc_name, "content": text[:80_000]})
    # Parse numbered lines into list
    questions = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove leading number/bullet (e.g. "1. " or "1) ")
        for sep in (". ", ") "):
            parts = line.split(sep, 1)
            if len(parts) == 2 and parts[0].strip().replace(".", "").rstrip(")").isdigit():
                line = parts[1].strip()
                break
        if line:
            questions.append(line)
    return questions[:10] if questions else ([result.strip()] if result.strip() else [])


def _generate_report_sync(text: str, doc_name: str) -> str:
    """Generate analysis report from PDF text (runs in thread)."""
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You write structured analysis reports in Markdown. Use headers (##), bullet points, and short paragraphs."),
        ("human", "Write an analysis report for this document in Markdown. Include: 1) Overview, 2) Key points, 3) Main findings or conclusions, 4) Recommendations or next steps if applicable.\n\nDocument: {doc_name}\n\nContent:\n{content}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"doc_name": doc_name, "content": text[:80_000]})


def _ensure_generated_dir(user_id: str, dataset_id: str) -> Path:
    """Ensure directory for generated .md files exists; return path."""
    path = STORAGE_DIR / f"user_{user_id}" / "generated" / str(dataset_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_pdf_summary_questions_report(
    pdf_content: bytes,
    doc_name: str,
    user_id: str,
    dataset_id: str,
) -> Tuple[str, List[str], str]:
    """
    Extract text from PDF with PyMuPDF, then run summary, questions, and report
    in three parallel threads using LangChain/OpenAI. Write results to .md files
    and return (summary, questions, report).
    """
    text = _extract_text_from_pdf(pdf_content)
    out_dir = _ensure_generated_dir(user_id, dataset_id)

    summary = ""
    questions: List[str] = []
    report = ""

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_summary = executor.submit(_generate_summary_sync, text, doc_name)
        f_questions = executor.submit(_generate_questions_sync, text, doc_name)
        f_report = executor.submit(_generate_report_sync, text, doc_name)

        summary = f_summary.result()
        questions = f_questions.result()
        report = f_report.result()

    # Write .md files
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")
    (out_dir / "questions.md").write_text("\n".join(f"{i+1}. {q}" for i, q in enumerate(questions)), encoding="utf-8")
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    return summary, questions, report
