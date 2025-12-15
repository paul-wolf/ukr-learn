"""Content generator using AI providers."""

from typing import Optional

from src.ai.base import AIProvider
from src.core.models import Text, WordList, GrammarNote, WordEntry


SYSTEM_PROMPT = """You are a Ukrainian language teaching assistant.
You help create learning materials for English speakers learning Ukrainian.
Always provide accurate Ukrainian with proper grammar and spelling.
Use the Cyrillic alphabet for Ukrainian text."""


class ContentGenerator:
    """Generate language learning content using AI."""

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def generate_text(
        self,
        topic: str,
        difficulty: str = "beginner",
        length: str = "short",
    ) -> Text:
        """
        Generate a reading text on a topic.

        Args:
            topic: What the text should be about
            difficulty: beginner, intermediate, or advanced
            length: short (~50 words), medium (~150 words), or long (~300 words)

        Returns:
            A Text object with generated content
        """
        word_counts = {
            "short": "about 50",
            "medium": "about 150",
            "long": "about 300",
        }
        word_count = word_counts.get(length, "about 100")

        difficulty_guidance = {
            "beginner": "Use simple sentences, common vocabulary, present tense mainly.",
            "intermediate": "Use varied sentence structures, past and future tenses, common idioms.",
            "advanced": "Use complex sentences, advanced vocabulary, all tenses, idiomatic expressions.",
        }
        guidance = difficulty_guidance.get(difficulty, difficulty_guidance["beginner"])

        prompt = f"""Create a Ukrainian reading text about: {topic}

Requirements:
- Length: {word_count} words
- Difficulty: {difficulty}
- {guidance}

Format your response as:
TITLE: [A short Ukrainian title]
---
[The Ukrainian text content]

Do not include translations or explanations."""

        response = self.provider.generate(prompt, system=SYSTEM_PROMPT)

        # Parse response
        title = topic  # Default
        content = response

        if "TITLE:" in response and "---" in response:
            parts = response.split("---", 1)
            title_line = parts[0].replace("TITLE:", "").strip()
            if title_line:
                title = title_line
            if len(parts) > 1:
                content = parts[1].strip()

        return Text.create(
            title=title,
            content=content,
            difficulty=difficulty,
            tags=[topic.lower()],
            source="ai_generated",
        )

    def generate_wordlist(
        self,
        theme: str,
        count: int = 20,
    ) -> WordList:
        """
        Generate a themed word list.

        Args:
            theme: Theme for the word list (e.g., "food", "greetings", "numbers")
            count: Number of words to generate

        Returns:
            A WordList object with words and translations
        """
        prompt = f"""Create a list of {count} Ukrainian words for the theme: {theme}

Format each word as:
WORD | TRANSLATION | NOTES

Where:
- WORD is the Ukrainian word
- TRANSLATION is the English translation
- NOTES is optional grammatical info (part of speech, gender for nouns, etc.)

Example:
привіт | hello | greeting, informal
дякую | thank you | verb, expression of gratitude

List {count} words, one per line:"""

        response = self.provider.generate(prompt, system=SYSTEM_PROMPT, max_tokens=3000)

        # Parse response
        words = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Try to parse WORD | TRANSLATION | NOTES format
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                word = parts[0].strip("- ")
                translation = parts[1]
                notes = parts[2] if len(parts) > 2 else None
                words.append(WordEntry(
                    word=word,
                    translation=translation,
                    notes=notes,
                ))

        # Create title from theme
        title = f"{theme.title()} Vocabulary"

        return WordList.create(
            title=title,
            theme=theme.lower(),
            words=words,
        )

    def generate_grammar_note(self, topic: str) -> GrammarNote:
        """
        Generate a grammar explanation.

        Args:
            topic: Grammar topic (e.g., "noun cases", "verb conjugation")

        Returns:
            A GrammarNote with explanation
        """
        prompt = f"""Explain this Ukrainian grammar topic for English speakers: {topic}

Include:
1. Clear explanation of the concept
2. When/how it's used
3. Examples with Ukrainian text and English translations
4. Common patterns or rules
5. Common mistakes to avoid

Format the explanation clearly with sections.
Use Ukrainian examples with translations in parentheses."""

        response = self.provider.generate(prompt, system=SYSTEM_PROMPT, max_tokens=3000)

        # Extract potential tags from the topic
        tags = [word.lower() for word in topic.split() if len(word) > 3]

        return GrammarNote.create(
            title=topic.title(),
            content=response,
            tags=tags,
        )

    def explain_word(
        self,
        word: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Get explanation for a specific word.

        Args:
            word: The Ukrainian word to explain
            context: Optional sentence where the word appears

        Returns:
            Explanation text
        """
        context_text = ""
        if context:
            context_text = f'\nContext: "{context}"'

        prompt = f"""Explain this Ukrainian word: {word}{context_text}

Provide:
1. Translation(s) to English
2. Part of speech
3. For nouns: gender and example declensions
4. For verbs: aspect and example conjugations
5. Example sentence with translation
6. Related words or expressions"""

        return self.provider.generate(prompt, system=SYSTEM_PROMPT, max_tokens=1000)

    def translate_word(self, word: str) -> str:
        """Get a simple translation for a word."""
        prompt = f"Translate this Ukrainian word to English. Reply with ONLY the translation, nothing else: {word}"

        response = self.provider.generate(prompt, system=SYSTEM_PROMPT, max_tokens=50)
        return response.strip()

    def get_word_info(self, word: str, context: Optional[str] = None) -> str:
        """
        Get detailed information about a Ukrainian word.

        Args:
            word: The Ukrainian word
            context: Optional sentence context

        Returns:
            Detailed information formatted for display
        """
        context_text = ""
        if context:
            context_text = f'\nContext: "{context}"'

        prompt = f"""Provide detailed information about this Ukrainian word: {word}{context_text}

Format your response exactly like this:

WORD: {word}
PRONUNCIATION: [phonetic guide for English speakers]
PART OF SPEECH: [noun/verb/adjective/etc.]
GENDER: [for nouns: masculine/feminine/neuter, otherwise N/A]
ASPECT: [for verbs: imperfective/perfective, otherwise N/A]

DEFINITIONS:
1. [primary meaning]
2. [secondary meaning if any]

EXAMPLES:
• [Ukrainian sentence] — [English translation]
• [Ukrainian sentence] — [English translation]

RELATED WORDS:
• [related word 1] — [translation]
• [related word 2] — [translation]

NOTES:
[Any irregularities, common mistakes, or usage tips]"""

        return self.provider.generate(prompt, system=SYSTEM_PROMPT, max_tokens=1500)

    def get_phrase_info(self, phrase: str, context: Optional[str] = None) -> str:
        """
        Get detailed information about a Ukrainian phrase.

        Args:
            phrase: The Ukrainian phrase (multiple words)
            context: Optional sentence context

        Returns:
            Detailed information formatted for display
        """
        context_text = ""
        if context:
            context_text = f'\nContext: "{context}"'

        prompt = f"""Provide detailed information about this Ukrainian phrase: {phrase}{context_text}

Format your response exactly like this:

PHRASE: {phrase}
LITERAL MEANING: [word-by-word translation]
ACTUAL MEANING: [what it really means]

TYPE: [idiom/expression/collocation/compound verb/etc.]
REGISTER: [formal/informal/neutral/slang]

USAGE:
[When and how to use this phrase]

EXAMPLES:
• [Ukrainian sentence using the phrase] — [English translation]
• [Ukrainian sentence using the phrase] — [English translation]

RELATED EXPRESSIONS:
• [similar phrase 1] — [translation]
• [similar phrase 2] — [translation]

NOTES:
[Cultural context, common mistakes, or tips]"""

        return self.provider.generate(prompt, system=SYSTEM_PROMPT, max_tokens=1500)

    def analyze_text_vocabulary(self, words: list[str]) -> str:
        """
        Analyze vocabulary from a text, grouping inflected forms.

        Args:
            words: List of unique words from a text

        Returns:
            Formatted vocabulary analysis with lemmas and translations
        """
        words_str = ", ".join(words)

        prompt = f"""Analyze this list of Ukrainian words from a text. Group inflected forms under their dictionary form (lemma).

Words: {words_str}

For each unique lemma, provide:
1. The dictionary form (lemma)
2. English translation
3. Part of speech
4. Which inflected forms from the list belong to this lemma

Format your response EXACTLY like this, one entry per line:
LEMMA | translation | part of speech | forms: form1, form2, ...

Example:
кіт | cat | noun (m) | forms: кота, коти, коту, котів
бути | to be | verb | forms: є, був, була, буде
великий | big, large | adjective | forms: великий, велика, великого

Rules:
- List lemmas alphabetically
- For nouns, indicate gender: (m), (f), (n)
- For verbs, give infinitive as lemma
- Group ALL inflected forms under their lemma
- Include common words like prepositions, conjunctions
- Be thorough - every word from the input should appear under some lemma

Analyze ALL {len(words)} words:"""

        return self.provider.generate(prompt, system=SYSTEM_PROMPT, max_tokens=4000)
