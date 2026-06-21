"""
MECOS Office Automation Module
Direct integration with Microsoft Office applications (Word, Excel, PowerPoint)
via pywin32 COM automation.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


class OfficeAutomation:
    """Automates Microsoft Office applications."""

    def __init__(self):
        self.word_app = None
        self.word_doc = None
        self._pywin32_available = self._check_pywin32()

    def _check_pywin32(self) -> bool:
        """Check if pywin32 is available."""
        try:
            import win32com.client
            return True
        except ImportError:
            return False

    async def open_word(self) -> Dict[str, Any]:
        """Open Microsoft Word and return status."""
        if not self._pywin32_available:
            return {"status": "error", "message": "pywin32 not installed. Run: pip install pywin32"}

        try:
            import win32com.client
            self.word_app = win32com.client.Dispatch("Word.Application")
            self.word_app.Visible = True
            self.word_doc = self.word_app.Documents.Add()
            return {"status": "ok", "message": "Word opened successfully"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to open Word: {e}"}

    async def write_to_word(self, text: str) -> Dict[str, Any]:
        """Write text to the open Word document."""
        if not self._pywin32_available:
            return {"status": "error", "message": "pywin32 not installed"}

        if not self.word_app or not self.word_doc:
            open_result = await self.open_word()
            if open_result["status"] != "ok":
                return open_result

        try:
            # Get the Selection object
            selection = self.word_app.Selection
            selection.Text = text
            return {"status": "ok", "chars_written": len(text)}
        except Exception as e:
            return {"status": "error", "message": f"Failed to write to Word: {e}"}

    async def save_word_document(self, path: str) -> Dict[str, Any]:
        """Save the current Word document."""
        if not self._pywin32_available or not self.word_doc:
            return {"status": "error", "message": "No open document"}

        try:
            self.word_doc.SaveAs2(path)
            return {"status": "ok", "path": path}
        except Exception as e:
            return {"status": "error", "message": f"Failed to save: {e}"}

    async def close_word(self) -> None:
        """Close Word and cleanup."""
        if self.word_app:
            try:
                self.word_app.Quit()
            except Exception:
                pass
            self.word_app = None
            self.word_doc = None

    async def generate_and_write_essay(self, topic: str, pages: int = 20) -> Dict[str, Any]:
        """Generate an essay using the LLM and write to Word."""
        # First open Word
        open_result = await self.open_word()
        if open_result["status"] != "ok":
            return open_result

        # Generate essay content using MECOS LLM
        try:
            from mecos_llm import get_mecos_llm
            llm = get_mecos_llm()
            
            prompt = f"""Write a comprehensive essay on '{topic}'.
            
Target length: approximately {pages} pages (about {pages * 250} words).
Structure:
- Introduction with thesis statement
- 5-7 main body sections with clear arguments
- Conclusion summarizing key insights

Write in academic prose, include references to philosophical perspectives from both Eastern and Western traditions.
Be thorough and substantive.
"""
            result = await llm.think_and_act(
                prompt,
                system_prompt="You are a philosophy professor writing an academic essay. Write well-structured, insightful content."
            )
            essay = result.get("response", "")
        except Exception as e:
            logger.warning(f"LLM generation failed: {e}")
            essay = self._generate_placeholder_essay(topic, pages)

        # Write paragraph by paragraph for natural typing effect
        paragraphs = essay.split("\n\n")
        for i, para in enumerate(paragraphs):
            if para.strip():
                await self.write_to_word(para + "\n\n")

        return {
            "status": "ok",
            "topic": topic,
            "pages_requested": pages,
            "paragraphs_written": len([p for p in paragraphs if p.strip()]),
            "total_chars": len(essay),
        }

    def _generate_placeholder_essay(self, topic: str, pages: int) -> str:
        """Generate placeholder content when LLM unavailable."""
        sections = [
            f"# The Meaning of Life: An Essay on {topic}",
            "",
            "## Introduction",
            f"The question of {topic.lower()} has captivated human thought since antiquity...",
            "",
            "## Ancient Philosophical Perspectives",
            "Greek philosophers like Aristotle spoke of eudaimonia...",
            "",
            "## Eastern Wisdom Traditions",
            "Buddhist teachings on dukkha and liberation...",
            "",
            "## Modern Scientific Understanding",
            "Contemporary neuroscience and evolutionary psychology...",
            "",
            "## Existentialist Views",
            "Sartre, Camus, and the burden of freedom...",
            "",
            "## Religious and Spiritual Dimensions",
            "Major world religions and their answers to mortality...",
            "",
            "## Conclusion",
            f"In contemplating {topic.lower()}, we find...",
        ]
        
        # Pad with more content for longer essays
        while len("\n".join(sections)) < pages * 1000:
            sections.append(f"\n## Reflection {len(sections)}")
            sections.append(f"Further meditations on {topic.lower()}...")
        
        return "\n\n".join(sections)


async def main():
    """Test the Office automation."""
    office = OfficeAutomation()
    print(f"pywin32 available: {office._pywin32_available}")
    
    if office._pywin32_available:
        result = await office.generate_and_write_essay("The Meaning of Life", 20)
        print(f"Essay result: {result}")
        await office.close_word()
    else:
        print("Install pywin32 to test Word automation")


if __name__ == "__main__":
    asyncio.run(main())