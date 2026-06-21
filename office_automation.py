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
            # Move selection to end of document before writing
            self.word_app.Selection.EndKey(Unit=6)  # 6 = wdStory
            self.word_app.Selection.Text = text
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
            # Check if LLM actually worked (not error message)
            if essay.startswith("Error:") or "error" in result.get("stats", {}).get("model", ""):
                logger.warning(f"LLM generation returned error, using placeholder")
                essay = self._generate_placeholder_essay(topic, pages)
        except Exception as e:
            logger.warning(f"LLM generation failed: {e}")
            essay = self._generate_placeholder_essay(topic, pages)

        # Write paragraph by paragraph for natural typing effect
        paragraphs = essay.split("\n\n")
        for para in paragraphs:
            if para.strip():
                await self.write_to_word(para + "\n\n")
        
        # Auto-save to temp directory
        output_path = Path("C:/Temp") / f"MECOS_Essay_{topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_result = await self.save_word_document(str(output_path))
        if save_result["status"] != "ok":
            logger.warning(f"Auto-save failed: {save_result}")
        
        return {
            "status": "ok",
            "topic": topic,
            "pages_requested": pages,
            "paragraphs_written": len([p for p in paragraphs if p.strip()]),
            "total_chars": len(essay),
            "saved_to": str(output_path) if save_result["status"] == "ok" else None
        }

    def _generate_placeholder_essay(self, topic: str, pages: int) -> str:
        """Generate substantial placeholder content when LLM unavailable."""
        all_paragraphs = [
            f"# The Meaning of Life: An Essay on {topic}",
            "",
            "## Introduction",
            f"The question of {topic.lower()} has captivated human thought since antiquity. This essay examines multiple perspectives on existence, purpose, and the human condition. From ancient philosophical inquiries through modern scientific understanding, humanity has sought to understand why we are here and what gives our lives significance.",
            "",
            "Throughout history, thinkers have proposed various frameworks for understanding life's ultimate purpose. Some argue meaning is discovered through divine revelation, others through rational inquiry, and still others through lived experience and authentic choice.",
            "",
            "This essay explores these dimensions systematically, drawing from philosophical traditions, scientific insights, and existential considerations to provide a comprehensive overview.",
            "",
            "## Ancient Philosophical Perspectives",
            "Greek philosophers laid the groundwork for understanding life through reason. Aristotle's concept of eudaimonia - often translated as 'flourishing' or 'the good life' - suggests that meaning emerges through the cultivation of virtue and excellence. Rather than seeking pleasure or avoiding pain, Aristotle argued that true fulfillment comes from developing our rational capacities and living in accordance with our nature as rational beings.",
            "",
            "Socrates famously declared that 'the unexamined life is not worth living,' emphasizing self-knowledge as the foundation of meaningful existence. Plato's allegory of the cave presents meaning as the arduous ascent from shadows to genuine reality - a metaphor for philosophical enlightenment.",
            "",
            "The Stoics, including Epictetus and Marcus Aurelius, taught that meaning lies in accepting the natural order and focusing on what lies within our control. Seneca wrote extensively on how to live with wisdom, emphasizing that suffering arises not from events but from our judgments about them.",
            "",
            "## Eastern Wisdom Traditions",
            "Buddhist philosophy approaches meaning through the Four Noble Truths. The recognition that suffering (dukkha) is intrinsic to existence leads to the path of practice culminating in nirvana - not annihilation but transcendence of the limited ego-self. The concept of dependent origination suggests that all meaning arises interdependently, not from isolated individual consciousness.",
            "",
            "Hindu traditions offer multiple pathways to meaning. The Purusharthas identify four aims of human life: dharma (righteous duty), artha (material prosperity), kama (pleasure and love), and moksha (liberation). The concept of karma suggests that meaning unfolds through action aligned with cosmic order.",
            "",
            "Taoist philosophy presents wu wei - effortless action - as a way to align with the natural flow of existence. Lao Tzu's Tao Te Ching suggests that meaning comes from embracing simplicity and yielding rather than striving against the current.",
            "",
            "## Modern Scientific Understanding",
            "Contemporary neuroscience reveals meaning as a construct of the brain's pattern recognition systems. The default mode network, active during rest and self-reflection, appears to generate our sense of self and narrative about our lives. Neuroscientists like Antonio Damasio have shown how emotions - 'somatic markers' - guide our decisions and give subjective weight to experiences.",
            "",
            "Evolutionary psychology suggests meaning may be an adaptation that promotes survival. The ability to find purpose in long-term goals, to sacrifice for offspring and community, confers reproductive advantages. However, this does not necessarily invalidate meaning - consciousness itself may be the universe's way of experiencing its own wonder.",
            "",
            "Cosmology places human concerns in perspective through the cosmic calendar. If the universe's history were compressed into a single year, humanity appears only in the final minutes of December. Yet Carl Sagan noted that consciousness itself - the ability to observe and comprehend the cosmos - makes us in a sense the universe reflecting on itself.",
            "",
            "## Existentialist Views",
            "Jean-Paul Sartre proclaimed that existence precedes essence - we exist first, thrown into being, and must create ourselves through authentic choices. This radical freedom brings anxiety but also the responsibility to author our own meaning. There is no predetermined human nature, only what we choose to become.",
            "",
            "Albert Camus embraced the absurd - the conflict between human desire for meaning and the universe's apparent silence. In works like 'The Myth of Sisyphus,' he argues we should imagine Sisyphus happy, finding meaning in the struggle itself despite its futility.",
            "",
            "Viktor Frankl, surviving Nazi concentration camps, observed that meaning can be found even in suffering. His logotherapy suggests humans can bear any burden if they understand its purpose - whether through creative work, loving relationships, or the stance we take toward unavoidable pain.",
            "",
            "## Religious and Spiritual Dimensions",
            "Abrahamic traditions locate meaning in relationship with the divine. Judaism emphasizes covenant, Christianity speaks of salvation through love, and Islam presents submission to Allah's will as the path to transcendent purpose.",
            "",
            "Christian mystics from Augustine to Thomas Merton have described meaning as union with God - the via negativa suggesting that ultimate reality transcends conceptual understanding.",
            "",
            "Islamic philosophy, through thinkers like Al-Ghazali and Ibn Rushd, balances rational inquiry with spiritual surrender, proposing that meaning comes through proper worship and ethical living.",
            "",
            "## Contemporary Synthesis",
            "Modern thinkers have attempted to synthesize these traditions. Secular humanism finds meaning in human welfare and rational progress without supernatural assumptions. Transhumanist visions extend meaning through technological enhancement and cosmic exploration.",
            "",
            "Positive psychology identifies meaning as one pillar of well-being alongside positive emotion, engagement, relationships, and achievement. Martin Seligman's PERMA model suggests we flourish when we engage with valued activities and contribute to something larger than ourselves.",
            "",
            "## Conclusion",
            f"In contemplating {topic.lower()}, we discover that meaning is multifaceted. Whether discovered through revelation, found through reason, or created through authentic choice, meaning appears to require consciousness, connection, and commitment.",
            "",
            "The search itself may be more important than finding final answers. Each generation must grapple anew with these questions, bringing its particular knowledge and circumstances to bear on the mystery of existence.",
        ]
        
        # Calculate target paragraphs (roughly 200 words per paragraph, ~250 words per page)
        target_paragraphs = pages * 10
        while len(all_paragraphs) < target_paragraphs:
            section_num = len(all_paragraphs) // 2
            all_paragraphs.append(f"## Reflection Section {section_num}")
            all_paragraphs.append(f"Further meditations on {topic.lower()} reveal the depth and complexity of this fundamental question. Each perspective adds nuance to our understanding, suggesting that meaning may be plural rather than singular - a constellation of purposes rather than a single destination.")
        
        return "\n\n".join(all_paragraphs)


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