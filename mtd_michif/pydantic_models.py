"""
Pydantic models for dictionary data structures.
"""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class Clip(BaseModel):
    """Audio clip for a Michif text"""

    speaker: str = Field(description="Full name of speaker")
    path: Path = Field(description="Path to audio clip relative to output directory")
    starts: Optional[list[int]] = Field(
        None,
        description="Start frames (10ms) of words in audio beginning with the second word",
    )


class Example(BaseModel):
    """Example sentence with associated audio."""

    english: str = Field(description="English sentence")
    michif: str = Field(description="Michif translation")
    audio: List[Clip] = Field(default=[], description="Michif audio clips")
    score: float = Field(default=0.0, description="Match score (less is better)")

    def __key(self):
        """Return (what we consider to be) a unique key for an Example."""
        return (self.english, self.michif)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __lt__(self, other):
        return self.__key() < other.__key()


class Entry(BaseModel):
    """Dictionary entry with associated audio and examples."""

    english: str = Field(description="English headword")
    michif: str = Field(description="Michif translation")
    id: Optional[str] = Field(None, description="Identifier for this entry")
    clarification: Optional[str] = Field(
        None, description="English description of specific sense"
    )
    audio: List[Clip] = Field(default=[], description="Michif audio clips")
    examples: List[Example] = Field(default=[], description="Example sentences")

    def __key(self):
        """Return (what we consider to be) a unique key for an Entry."""
        return (
            self.english,
            self.michif,
            "" if self.clarification is None else self.clarification,
        )

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        # FIXME: this doesn't match __hash__ which is probably a Bad Thing
        return self.__key() == other.__key() and self.examples == other.examples

    def __lt__(self, other):
        return self.__key() < other.__key()
