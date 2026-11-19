from app.schemas import LLMNoteAnalysis
from app.services.llm import LLMError
from app.services.notes import NoteAnalyzer, heuristic_analysis

CATEGORIES = [
    "P2P", "Ovqatlanish", "Narsa sotib olish", "Qarz berish", "Qarz olish",
    "Investitsiya", "Uyga to‘lov", "Maosh", "Boshqa",
]  # fmt: skip


def test_heuristics_read_people_count():
    result = heuristic_analysis("Kamolonda ovqatlandik 3 kishi", None, CATEGORIES)
    assert result.people_count == 3
    assert result.is_shared_expense is True


def test_heuristics_guess_food_category():
    assert heuristic_analysis("Kamolonda ovqatlandik 3 kishi", None, CATEGORIES).category_guess == "Ovqatlanish"


def test_heuristics_guess_lending():
    assert heuristic_analysis("Do'stimga qarz berdim", None, CATEGORIES).category_guess == "Qarz berish"


def test_heuristics_guess_salary():
    assert heuristic_analysis("Maosh keldi", None, CATEGORIES).category_guess == "Maosh"


def test_heuristics_guess_rent_as_recurring_home_payment():
    result = heuristic_analysis("Kvartira ijarasi, har oy", None, CATEGORIES)
    assert result.category_guess == "Uyga to‘lov"
    assert result.is_recurring is True
    assert result.recurring_period == "monthly"


def test_heuristics_do_not_guess_when_unclear():
    result = heuristic_analysis("shunchaki", None, CATEGORIES)
    assert result.category_guess is None
    assert result.people_count is None
    assert result.is_recurring is False


def test_heuristics_only_suggest_existing_categories():
    assert heuristic_analysis("Maosh keldi", None, ["Boshqa"]).category_guess is None


def test_heuristics_collect_hashtags_as_tags():
    assert heuristic_analysis("taksi #ish #safar", None, CATEGORIES).tags == ["ish", "safar"]


class FakeLLM:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, 0

    async def analyze_note(self, note, merchant, transaction_type, categories):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


async def test_analyzer_without_llm_uses_heuristics():
    result = await NoteAnalyzer(None).analyze("Kamolonda ovqatlandik 3 kishi", "KAMOLON", "expense", CATEGORIES)
    assert result.people_count == 3
    assert result.category_guess == "Ovqatlanish"


async def test_analyzer_prefers_llm_result():
    llm = FakeLLM(LLMNoteAnalysis(category_guess="P2P", tags=["o'tkazma"], people_count=2, summary="Xulosa"))
    result = await NoteAnalyzer(llm).analyze("Akamga tashladim", None, "expense", CATEGORIES)
    assert result.category_guess == "P2P"
    assert result.tags == ["o'tkazma"]
    assert result.summary == "Xulosa"


async def test_analyzer_ignores_llm_category_that_user_does_not_have():
    llm = FakeLLM(LLMNoteAnalysis(category_guess="Sayohat"))
    result = await NoteAnalyzer(llm).analyze("Maosh keldi", None, "income", CATEGORIES)
    assert result.category_guess == "Maosh"


async def test_analyzer_falls_back_to_heuristics_when_llm_fails():
    llm = FakeLLM(error=LLMError("down"))
    result = await NoteAnalyzer(llm).analyze("Kamolonda ovqatlandik 3 kishi", None, "expense", CATEGORIES)
    assert llm.calls == 1
    assert result.people_count == 3


def test_going_home_is_not_a_home_payment():
    assert heuristic_analysis("Taksi — uyga qaytish", "YANDEX GO", CATEGORIES).category_guess is None


def test_paying_for_home_is_a_home_payment():
    assert heuristic_analysis("Uyga to'lov, noyabr", None, CATEGORIES).category_guess == "Uyga to‘lov"
    assert heuristic_analysis("uy uchun svet", None, CATEGORIES).category_guess == "Uyga to‘lov"
