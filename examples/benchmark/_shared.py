"""Shared utilities: synthetic datasets, offline forward stubs, token tracking."""

from __future__ import annotations

import hashlib
import random
import time
from typing import Any

from pydantic import BaseModel, Field

from operad import Agent, Configuration
from operad.benchmark import Dataset
from operad.benchmark.entry import Entry
from operad.core.config import Sampling

# ---------------------------------------------------------------------------
# Offline configuration (never contacts a real model)
# ---------------------------------------------------------------------------

OFFLINE_CFG = Configuration(
    backend="llamacpp",
    host="127.0.0.1:0",
    model="offline-stub",
    sampling=Sampling(temperature=0.0, max_tokens=2048),
)


# ---------------------------------------------------------------------------
# Classification dataset (banking / intent)
# ---------------------------------------------------------------------------

_INTENTS = [
    "check_balance",
    "transfer_funds",
    "report_card_lost",
    "activate_card",
    "change_pin",
    "dispute_charge",
    "close_account",
    "open_account",
    "update_address",
    "request_statement",
]

_TEMPLATES: dict[str, list[str]] = {
    "check_balance": [
        "What's my current balance?",
        "How much money do I have in my account?",
        "Can you show me my account balance?",
        "I'd like to know my balance.",
        "Tell me how much is left in my account.",
        "What is the available balance on my account?",
        "Show me my account funds.",
        "How much do I have saved?",
        "Please display my balance.",
        "I want to check my balance.",
    ],
    "transfer_funds": [
        "I need to send money to my friend.",
        "Please transfer $200 to account 12345.",
        "How do I wire funds to another account?",
        "Move $500 from checking to savings.",
        "I want to transfer money.",
        "Send $50 to John.",
        "Can you initiate a funds transfer?",
        "I'd like to make a bank transfer.",
        "Transfer money between my accounts.",
        "Wire funds to an external account.",
    ],
    "report_card_lost": [
        "I lost my card.",
        "My credit card is missing.",
        "Someone stole my debit card.",
        "I can't find my bank card.",
        "Please report my card as lost.",
        "My card was stolen.",
        "I need to report a missing card.",
        "Block my card, I lost it.",
        "My card has been lost or stolen.",
        "Flag my card as missing.",
    ],
    "activate_card": [
        "How do I activate my new card?",
        "I just received a new card and need to activate it.",
        "Please activate my card.",
        "I want to start using my new card.",
        "Card activation help.",
        "I need to turn on my new debit card.",
        "My card arrived, how do I activate?",
        "Enable my new card.",
        "I have a new card to activate.",
        "Walk me through card activation.",
    ],
    "change_pin": [
        "I want to change my PIN.",
        "How do I update my card PIN?",
        "Can I reset my PIN?",
        "I forgot my PIN and need a new one.",
        "Please help me change my PIN.",
        "I'd like a new PIN.",
        "Update my ATM PIN.",
        "I need to modify my security PIN.",
        "Change my card PIN please.",
        "How do I set a new PIN?",
    ],
    "dispute_charge": [
        "There's an unauthorized charge on my account.",
        "I want to dispute a transaction.",
        "A charge on my card doesn't look right.",
        "I didn't make this purchase.",
        "Please help me dispute a charge.",
        "I see a suspicious transaction.",
        "How do I contest a charge?",
        "I need to file a dispute.",
        "There's a fraudulent charge on my account.",
        "I want to challenge a billing error.",
    ],
    "close_account": [
        "I want to close my account.",
        "Please cancel my bank account.",
        "How do I shut down my account?",
        "I'd like to terminate my account.",
        "Close my savings account.",
        "I no longer want to bank here.",
        "Shut my account down.",
        "Account closure request.",
        "I want to end my banking relationship.",
        "Please close all my accounts.",
    ],
    "open_account": [
        "I want to open a new account.",
        "How do I create a bank account?",
        "Can I sign up for a savings account?",
        "I'd like to start a checking account.",
        "Open a new account for me.",
        "I'm interested in opening an account.",
        "What do I need to open an account?",
        "Sign me up for a new account.",
        "I want to become a customer.",
        "How to open a new savings account?",
    ],
    "update_address": [
        "I moved and need to update my address.",
        "Can you change my mailing address?",
        "My address has changed.",
        "Please update my contact address.",
        "I need to provide my new address.",
        "Update my home address on file.",
        "My shipping address changed.",
        "I relocated and need address updates.",
        "New address update request.",
        "Please change my address.",
    ],
    "request_statement": [
        "I need a copy of my bank statement.",
        "Can you send me my last statement?",
        "How do I get my account statement?",
        "Please email me my statement.",
        "I want to download my statement.",
        "Request for monthly statement.",
        "I need my transaction history.",
        "Send me my account statement.",
        "I'd like a statement for the last 3 months.",
        "Generate my account statement.",
    ],
}


class IntentIn(BaseModel):
    text: str = Field(default="", description="Customer message to classify.")


class IntentOut(BaseModel):
    intent: str = Field(default="", description="Predicted intent label.")


def make_classification_dataset(n: int = 100, seed: int = 42) -> Dataset[IntentIn, IntentOut]:
    rng = random.Random(seed)
    entries: list[Entry[IntentIn, IntentOut]] = []
    pool = [
        (intent, text)
        for intent, texts in _TEMPLATES.items()
        for text in texts
    ]
    rng.shuffle(pool)
    pool = pool[:n]
    for intent, text in pool:
        entries.append(Entry(
            input=IntentIn(text=text),
            expected_output=IntentOut(intent=intent),
        ))
    return Dataset(entries, name="intent_classification", version="1.0")


# ---------------------------------------------------------------------------
# Summarization dataset
# ---------------------------------------------------------------------------

_DOCS = [
    (
        "The water cycle describes how water evaporates from the surface of the earth, "
        "rises into the atmosphere, cools and condenses into rain or snow, and falls "
        "again to the surface. This process redistributes heat and drives weather patterns.",
        "Water cycles through evaporation, condensation, and precipitation, driving weather.",
    ),
    (
        "Photosynthesis is the process by which plants use sunlight, water, and carbon "
        "dioxide to produce oxygen and energy in the form of sugar. It occurs mainly in "
        "the leaves, where chlorophyll absorbs light energy.",
        "Plants convert sunlight, water, and CO2 into oxygen and sugar via photosynthesis.",
    ),
    (
        "The industrial revolution began in Britain in the late 18th century and transformed "
        "manufacturing through mechanization and steam power. It shifted economies from "
        "agrarian to industrial and led to urbanization.",
        "Britain's industrial revolution mechanized production, fueling urbanization.",
    ),
    (
        "Vaccination works by introducing a weakened or inactive form of a pathogen into "
        "the body so the immune system can build a defense without causing disease. "
        "This creates lasting immunity against future infection.",
        "Vaccines train the immune system to fight pathogens without causing disease.",
    ),
    (
        "Black holes are regions of space where gravity is so strong that nothing, including "
        "light, can escape once it crosses the event horizon. They form when massive stars "
        "collapse at the end of their life cycle.",
        "Black holes are regions of extreme gravity formed by collapsing massive stars.",
    ),
    (
        "Machine learning is a branch of artificial intelligence where systems learn to "
        "perform tasks by analyzing data rather than following explicit instructions. "
        "Neural networks, a type of machine learning model, excel at pattern recognition.",
        "Machine learning systems learn from data; neural networks excel at patterns.",
    ),
    (
        "The human genome contains approximately 3 billion base pairs encoding roughly "
        "20,000 genes. Sequencing the genome took over a decade and has accelerated "
        "medical research into genetic diseases.",
        "The 3-billion base-pair human genome encodes ~20,000 genes, aiding medical research.",
    ),
    (
        "Plate tectonics explains how the Earth's lithosphere is divided into large plates "
        "that move slowly. Their interactions cause earthquakes, volcanic eruptions, and "
        "the formation of mountain ranges.",
        "Moving tectonic plates cause earthquakes, volcanoes, and mountain formation.",
    ),
    (
        "Supply and demand is a fundamental economic model describing how prices are "
        "determined in a market. When supply exceeds demand prices fall; when demand "
        "exceeds supply prices rise.",
        "Prices rise when demand exceeds supply and fall when supply exceeds demand.",
    ),
    (
        "The nervous system is composed of the brain, spinal cord, and peripheral nerves. "
        "It processes sensory information and coordinates responses, using electrical "
        "impulses transmitted between neurons.",
        "The nervous system uses electrical impulses across neurons to process and respond.",
    ),
    (
        "Climate change refers to long-term shifts in global temperatures and weather "
        "patterns. While natural factors play a role, human activities—especially burning "
        "fossil fuels—have been the dominant driver since the mid-20th century.",
        "Human fossil fuel use is the dominant driver of long-term climate change.",
    ),
    (
        "The internet is a global network of interconnected computers communicating via "
        "standardized protocols such as TCP/IP. It enables data sharing, communication, "
        "and commerce across the world.",
        "The internet connects computers globally using TCP/IP for communication.",
    ),
    (
        "Antibiotics are medicines that kill or inhibit bacteria. They have saved millions "
        "of lives since Alexander Fleming discovered penicillin in 1928, but overuse is "
        "leading to resistant strains.",
        "Antibiotics kill bacteria and save lives, but overuse creates resistant strains.",
    ),
    (
        "Gravity is the force of attraction between masses. On Earth, it gives objects "
        "weight and causes them to fall. Newton described gravity as a force; Einstein "
        "reframed it as the curvature of spacetime.",
        "Gravity attracts masses; Newton described it as force, Einstein as spacetime curvature.",
    ),
    (
        "Democracy is a system of government in which citizens exercise power through "
        "voting. Representative democracy delegates authority to elected officials, "
        "while direct democracy involves citizens voting on policy directly.",
        "Democracy gives citizens voting power, either directly or through elected representatives.",
    ),
    (
        "The digestive system breaks down food into nutrients the body can absorb. "
        "Starting in the mouth and ending at the large intestine, it uses mechanical "
        "and chemical processes to extract energy and materials.",
        "The digestive system extracts nutrients from food via mechanical and chemical processes.",
    ),
    (
        "Encryption transforms data into an unreadable format using an algorithm and key. "
        "Only those with the correct key can decrypt it. It underpins secure communications "
        "on the internet and protects private information.",
        "Encryption protects data by making it unreadable without the correct key.",
    ),
    (
        "Renewable energy comes from naturally replenishing sources such as solar, wind, "
        "and hydro. Unlike fossil fuels, these sources do not deplete and emit far less "
        "carbon dioxide, making them critical for sustainability.",
        "Renewable energy sources are naturally replenishing and emit far less carbon dioxide.",
    ),
    (
        "The stock market is a marketplace where shares of publicly listed companies are "
        "bought and sold. Prices reflect investor expectations about future earnings, "
        "making markets forward-looking and volatile.",
        "Stock prices reflect future earnings expectations, making markets forward-looking.",
    ),
    (
        "Evolution by natural selection, proposed by Charles Darwin, explains how "
        "organisms with favorable traits survive and reproduce more than others. "
        "Over many generations this drives adaptation and the emergence of new species.",
        "Darwin's natural selection explains how favorable traits drive adaptation over generations.",
    ),
    (
        "The immune system defends the body against pathogens using two layers: innate "
        "immunity (fast, non-specific) and adaptive immunity (slow, targeted). "
        "Antibodies produced by B cells recognize and neutralize specific threats.",
        "The immune system uses innate and adaptive responses; antibodies neutralize pathogens.",
    ),
    (
        "Nuclear fission releases energy by splitting heavy atomic nuclei. Nuclear power "
        "plants harness this heat to generate electricity. Fission produces no direct "
        "CO2 emissions but generates radioactive waste.",
        "Nuclear fission generates electricity without CO2 but produces radioactive waste.",
    ),
    (
        "The rule of law means that laws apply equally to all individuals including "
        "government officials. It is a cornerstone of democratic governance and protects "
        "citizens against arbitrary exercise of power.",
        "Rule of law ensures all people, including officials, are equally subject to law.",
    ),
    (
        "Software version control tracks changes to code over time, allowing teams to "
        "collaborate and revert errors. Git is the dominant distributed version control "
        "system used in modern software development.",
        "Git tracks code changes and enables team collaboration with easy rollbacks.",
    ),
    (
        "The speed of light in a vacuum is approximately 299,792 km/s. According to "
        "Einstein's theory of special relativity, no object with mass can reach or "
        "exceed this speed.",
        "Light travels at ~300,000 km/s and nothing with mass can exceed this speed.",
    ),
    (
        "Urban planning shapes the design and use of land in cities to balance housing, "
        "transport, commerce, and green space. Good planning improves quality of life "
        "and reduces inequality.",
        "Urban planning balances land use to improve city life and reduce inequality.",
    ),
    (
        "Inflation is the rate at which the general level of prices for goods and services "
        "rises, eroding purchasing power. Central banks target low, stable inflation "
        "through monetary policy.",
        "Inflation erodes purchasing power; central banks use monetary policy to keep it stable.",
    ),
    (
        "Ocean currents transport heat around the globe, influencing climate. The Gulf "
        "Stream warms Western Europe while deep-water circulation moves cold water from "
        "poles to equator.",
        "Ocean currents redistribute heat globally, influencing regional climates.",
    ),
    (
        "The printing press, invented by Gutenberg around 1440, made books affordable "
        "and accelerated the spread of knowledge in Europe, fueling the Renaissance "
        "and Reformation.",
        "Gutenberg's press made books affordable and accelerated Renaissance-era knowledge.",
    ),
    (
        "A computer's CPU executes instructions by fetching them from memory, decoding "
        "them, and performing the required operations. Modern CPUs contain billions of "
        "transistors and run at billions of cycles per second.",
        "CPUs fetch, decode, and execute instructions at billions of cycles per second.",
    ),
    (
        "Sleep is essential for memory consolidation, emotional regulation, and physical "
        "repair. During deep sleep, the brain replays experiences to strengthen neural "
        "connections.",
        "Sleep consolidates memory and repairs the body; the brain replays experiences.",
    ),
    (
        "Blockchain is a distributed ledger that records transactions across many computers. "
        "Each block contains a hash of the previous one, making it tamper-resistant. "
        "Bitcoin uses blockchain for decentralized currency.",
        "Blockchain is a tamper-resistant distributed ledger; Bitcoin uses it for currency.",
    ),
    (
        "Antibodies are proteins produced by the immune system that bind to specific "
        "antigens on pathogens. They neutralize threats directly or flag them for "
        "destruction by other immune cells.",
        "Antibodies bind specific antigens to neutralize or flag pathogens for destruction.",
    ),
    (
        "The Amazon rainforest produces about 20% of the world's oxygen and houses more "
        "than 10% of all species. Deforestation threatens this biodiversity and "
        "destabilizes the global carbon cycle.",
        "Amazon deforestation threatens global biodiversity and the carbon cycle.",
    ),
    (
        "A scientific theory is not a guess—it is a well-tested explanation of natural "
        "phenomena backed by extensive evidence. Theories like evolution and germ theory "
        "have survived rigorous scrutiny.",
        "Scientific theories are rigorously tested explanations, not guesses.",
    ),
    (
        "Microplastics are tiny plastic fragments less than 5 mm in size. They accumulate "
        "in oceans, enter food chains, and have been found in human blood and breast milk. "
        "Their long-term effects on health are under study.",
        "Microplastics accumulate in food chains and have been detected in human tissue.",
    ),
    (
        "The French Revolution began in 1789 and dismantled the monarchy, aristocracy, "
        "and church as dominant powers. It spread ideals of liberty, equality, and "
        "fraternity across Europe.",
        "The French Revolution dismantled monarchy and spread liberty and equality ideals.",
    ),
    (
        "CRISPR-Cas9 is a gene-editing tool that allows scientists to cut and modify DNA "
        "at precise locations. It has potential applications in treating genetic diseases "
        "and developing disease-resistant crops.",
        "CRISPR-Cas9 enables precise gene editing with applications in medicine and agriculture.",
    ),
    (
        "A recession is a period of negative economic growth lasting at least two consecutive "
        "quarters. It typically involves rising unemployment, declining consumer spending, "
        "and tightening credit.",
        "A recession is two or more quarters of negative growth with rising unemployment.",
    ),
    (
        "Jazz originated in New Orleans in the early 20th century, blending African rhythms "
        "with European harmonies. Its improvisational nature set the stage for rock, soul, "
        "and hip-hop.",
        "Jazz blended African and European musical traditions and influenced modern genres.",
    ),
    (
        "Quantum computing uses qubits that can exist in superposition, representing 0 and 1 "
        "simultaneously. This allows certain problems—like factoring large numbers—to be "
        "solved exponentially faster than classical computers.",
        "Quantum computers use superposed qubits to solve certain problems exponentially faster.",
    ),
    (
        "The Paris Agreement is an international treaty committing nations to limit warming "
        "to 1.5–2°C above pre-industrial levels. Countries submit nationally determined "
        "contributions outlining their emissions-reduction pledges.",
        "The Paris Agreement commits nations to limit warming by reducing emissions.",
    ),
    (
        "Language models are trained on large text corpora to predict the next word. "
        "Recent large language models can write code, answer questions, and summarize "
        "documents with surprising fluency.",
        "Large language models predict text tokens and can write, answer, and summarize.",
    ),
    (
        "The mitochondria generate most of the cell's energy in the form of ATP through "
        "a process called cellular respiration. They also regulate cell death and have "
        "their own DNA, suggesting an ancient symbiotic origin.",
        "Mitochondria produce ATP via respiration and carry their own DNA from ancient symbiosis.",
    ),
    (
        "Colonialism refers to the control and exploitation of one territory by another. "
        "European colonialism from the 15th to 20th centuries reshaped economies, cultures, "
        "and borders globally, with effects still felt today.",
        "European colonialism reshaped global economies and cultures with lasting effects.",
    ),
    (
        "Nuclear fusion combines light atomic nuclei to release enormous energy. Unlike "
        "fission, it produces minimal radioactive waste and uses hydrogen isotopes as fuel. "
        "Achieving sustained fusion remains an engineering challenge.",
        "Fusion releases clean energy by combining nuclei, but sustained fusion is unsolved.",
    ),
    (
        "The placebo effect occurs when patients improve after receiving an inert treatment "
        "because they believe it will help. It demonstrates the powerful connection "
        "between mind and body in healing.",
        "The placebo effect shows the mind can influence physical healing through belief.",
    ),
    (
        "3D printing builds objects layer by layer from a digital design. It is used in "
        "medicine, aerospace, and consumer goods. Bioprinting—printing living tissue—is "
        "an emerging frontier.",
        "3D printing builds objects from digital designs; bioprinting is an emerging frontier.",
    ),
    (
        "The social contract theory holds that governments derive legitimacy from the "
        "consent of the governed. Thinkers like Locke, Rousseau, and Hobbes differed "
        "on what this contract entails.",
        "Social contract theory holds that government legitimacy stems from citizens' consent.",
    ),
    (
        "Emotional intelligence involves recognizing, understanding, and managing emotions "
        "in oneself and others. It predicts leadership effectiveness and interpersonal "
        "success better than IQ in many contexts.",
        "Emotional intelligence—recognizing and managing emotions—predicts leadership success.",
    ),
]


class DocIn(BaseModel):
    text: str = Field(default="", description="Source text to summarize.")


class SummaryOut(BaseModel):
    summary: str = Field(default="", description="One-sentence summary of the source text.")


def make_summarization_dataset(n: int = 50, seed: int = 42) -> Dataset[DocIn, SummaryOut]:
    rng = random.Random(seed)
    pool = list(_DOCS)
    rng.shuffle(pool)
    pool = pool[:n]
    entries = [
        Entry(input=DocIn(text=doc), expected_output=SummaryOut(summary=summary))
        for doc, summary in pool
    ]
    return Dataset(entries, name="summarization", version="1.0")


# ---------------------------------------------------------------------------
# Tool-use dataset
# ---------------------------------------------------------------------------

_TOOLS = ["get_weather", "set_reminder", "search_web", "send_email", "calculate"]

_TOOL_EXAMPLES: list[tuple[str, str, str]] = [
    ("What's the weather in Paris?", "get_weather", '{"city": "Paris"}'),
    ("Is it raining in Tokyo?", "get_weather", '{"city": "Tokyo"}'),
    ("What will the temperature be in New York tomorrow?", "get_weather", '{"city": "New York"}'),
    ("How's the weather in London?", "get_weather", '{"city": "London"}'),
    ("Tell me the current weather in Berlin.", "get_weather", '{"city": "Berlin"}'),
    ("Weather forecast for Sydney.", "get_weather", '{"city": "Sydney"}'),
    ("Is it sunny in Rome today?", "get_weather", '{"city": "Rome"}'),
    ("Weather conditions in Moscow?", "get_weather", '{"city": "Moscow"}'),
    ("Check the weather in Toronto.", "get_weather", '{"city": "Toronto"}'),
    ("What's the forecast for Dubai?", "get_weather", '{"city": "Dubai"}'),
    ("Remind me to call John at 3pm.", "set_reminder", '{"message": "Call John", "time": "15:00"}'),
    ("Set a reminder to submit the report by Friday.", "set_reminder", '{"message": "Submit report", "time": "Friday"}'),
    ("Remind me about the meeting tomorrow at 9am.", "set_reminder", '{"message": "Meeting", "time": "09:00"}'),
    ("Set an alarm for 7am.", "set_reminder", '{"message": "Alarm", "time": "07:00"}'),
    ("Remind me to take my medication at noon.", "set_reminder", '{"message": "Take medication", "time": "12:00"}'),
    ("Schedule a reminder for the dentist appointment.", "set_reminder", '{"message": "Dentist appointment", "time": "TBD"}'),
    ("Remind me to water the plants every evening.", "set_reminder", '{"message": "Water plants", "time": "evening"}'),
    ("Set a reminder to call mom on Sunday.", "set_reminder", '{"message": "Call mom", "time": "Sunday"}'),
    ("Remind me to buy groceries.", "set_reminder", '{"message": "Buy groceries", "time": "TBD"}'),
    ("Remind me about the team standup at 10am.", "set_reminder", '{"message": "Team standup", "time": "10:00"}'),
    ("Search for the latest news about AI.", "search_web", '{"query": "latest AI news"}'),
    ("Find recipes for chocolate cake.", "search_web", '{"query": "chocolate cake recipes"}'),
    ("Look up the capital of Brazil.", "search_web", '{"query": "capital of Brazil"}'),
    ("Search for information about climate change.", "search_web", '{"query": "climate change"}'),
    ("Find the best Python tutorials.", "search_web", '{"query": "Python tutorials"}'),
    ("Search for reviews of the iPhone 15.", "search_web", '{"query": "iPhone 15 reviews"}'),
    ("Look up Marie Curie biography.", "search_web", '{"query": "Marie Curie biography"}'),
    ("Search for flights from NYC to LA.", "search_web", '{"query": "flights NYC to LA"}'),
    ("Find the current stock price of Apple.", "search_web", '{"query": "Apple stock price"}'),
    ("Search for hiking trails near Denver.", "search_web", '{"query": "hiking trails near Denver"}'),
    ("Send an email to alice@example.com about the meeting.", "send_email", '{"to": "alice@example.com", "subject": "Meeting"}'),
    ("Email the project update to the team.", "send_email", '{"to": "team@example.com", "subject": "Project update"}'),
    ("Send a follow-up email to bob@example.com.", "send_email", '{"to": "bob@example.com", "subject": "Follow-up"}'),
    ("Email HR about my vacation request.", "send_email", '{"to": "hr@example.com", "subject": "Vacation request"}'),
    ("Send an invoice to client@example.com.", "send_email", '{"to": "client@example.com", "subject": "Invoice"}'),
    ("Compose an email confirming the appointment.", "send_email", '{"to": "doctor@example.com", "subject": "Appointment confirmation"}'),
    ("Send the agenda to attendees@example.com.", "send_email", '{"to": "attendees@example.com", "subject": "Agenda"}'),
    ("Email a thank-you note to sarah@example.com.", "send_email", '{"to": "sarah@example.com", "subject": "Thank you"}'),
    ("Forward my resume to hr@company.com.", "send_email", '{"to": "hr@company.com", "subject": "Resume"}'),
    ("Send a birthday greeting to mark@example.com.", "send_email", '{"to": "mark@example.com", "subject": "Happy Birthday"}'),
    ("What is 15% of 200?", "calculate", '{"expression": "15% of 200"}'),
    ("Calculate the square root of 144.", "calculate", '{"expression": "sqrt(144)"}'),
    ("What is 45 divided by 9?", "calculate", '{"expression": "45 / 9"}'),
    ("Multiply 37 by 48.", "calculate", '{"expression": "37 * 48"}'),
    ("What is 2 to the power of 10?", "calculate", '{"expression": "2^10"}'),
    ("Convert 100 Fahrenheit to Celsius.", "calculate", '{"expression": "(100-32)*5/9"}'),
    ("What is the area of a circle with radius 7?", "calculate", '{"expression": "pi * 7^2"}'),
    ("How much is 250 euros in dollars at 1.08 rate?", "calculate", '{"expression": "250 * 1.08"}'),
    ("What is 12 factorial?", "calculate", '{"expression": "12!"}'),
    ("Calculate compound interest: $1000 at 5% for 3 years.", "calculate", '{"expression": "1000*(1+0.05)^3"}'),
]


class ToolIn(BaseModel):
    instruction: str = Field(default="", description="Natural-language instruction to execute.")


class ToolOut(BaseModel):
    tool_name: str = Field(default="", description="Name of the tool to call.")
    tool_args: str = Field(default="{}", description="JSON string of arguments for the tool.")


def make_tool_use_dataset(n: int = 50, seed: int = 42) -> Dataset[ToolIn, ToolOut]:
    rng = random.Random(seed)
    pool = list(_TOOL_EXAMPLES)
    rng.shuffle(pool)
    pool = pool[:n]
    entries = [
        Entry(
            input=ToolIn(instruction=instr),
            expected_output=ToolOut(tool_name=tool, tool_args=args),
        )
        for instr, tool, args in pool
    ]
    return Dataset(entries, name="tool_use", version="1.0")


# ---------------------------------------------------------------------------
# Offline forward: deterministic canned outputs, no LLM
# ---------------------------------------------------------------------------

def _stable_hash(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16)


class OfflineIntentLeaf(Agent[IntentIn, IntentOut]):
    """Returns a deterministic intent label based on keyword matching."""

    input = IntentIn
    output = IntentOut

    async def forward(self, x: IntentIn) -> IntentOut:
        text = x.text.lower()
        for intent in _INTENTS:
            keyword = intent.replace("_", " ").split()[0]
            if keyword in text:
                return IntentOut(intent=intent)
        idx = _stable_hash(x.text) % len(_INTENTS)
        return IntentOut(intent=_INTENTS[idx])


class OfflineSummaryLeaf(Agent[DocIn, SummaryOut]):
    """Returns first sentence of doc as a fake summary."""

    input = DocIn
    output = SummaryOut

    async def forward(self, x: DocIn) -> SummaryOut:
        sentences = x.text.split(".")
        summary = sentences[0].strip() + "." if sentences else x.text[:80]
        return SummaryOut(summary=summary[:120])


class OfflineToolLeaf(Agent[ToolIn, ToolOut]):
    """Returns tool name based on keyword matching."""

    input = ToolIn
    output = ToolOut

    async def forward(self, x: ToolIn) -> ToolOut:
        instr = x.instruction.lower()
        if any(w in instr for w in ["weather", "temperature", "rain", "sunny", "forecast"]):
            return ToolOut(tool_name="get_weather", tool_args='{"city": "Unknown"}')
        if any(w in instr for w in ["remind", "reminder", "alarm", "schedule"]):
            return ToolOut(tool_name="set_reminder", tool_args='{"message": "Reminder", "time": "TBD"}')
        if any(w in instr for w in ["search", "find", "look up", "latest"]):
            return ToolOut(tool_name="search_web", tool_args='{"query": "query"}')
        if any(w in instr for w in ["email", "send", "mail", "forward"]):
            return ToolOut(tool_name="send_email", tool_args='{"to": "user@example.com", "subject": "Message"}')
        if any(w in instr for w in ["calculate", "what is", "multiply", "divide", "convert", "area", "power", "sqrt", "interest", "factorial", "percent"]):
            return ToolOut(tool_name="calculate", tool_args='{"expression": "0"}')
        idx = _stable_hash(x.instruction) % len(_TOOLS)
        return ToolOut(tool_name=_TOOLS[idx], tool_args="{}")


# ---------------------------------------------------------------------------
# Token tracking via forward hooks
# ---------------------------------------------------------------------------

class TokenCounter:
    """Accumulates token usage by attaching a forward hook to an agent.

    Usage:
        counter = TokenCounter()
        handle = counter.attach(agent)
        await evaluate(agent, dataset, metrics)
        handle.remove()
        print(counter.totals())
    """

    def __init__(self) -> None:
        self._prompt = 0
        self._completion = 0

    def attach(self, agent: Agent) -> Any:
        def _hook(a: Agent, x: Any, y: Any) -> None:
            usage = getattr(y, "usage", None) or getattr(y, "_usage", None)
            if usage is None:
                return
            self._prompt += int(getattr(usage, "prompt_tokens", 0) or 0)
            self._completion += int(getattr(usage, "completion_tokens", 0) or 0)

        return agent.register_forward_hook(_hook)

    def totals(self) -> dict[str, int]:
        return {"prompt": self._prompt, "completion": self._completion}

    def reset(self) -> None:
        self._prompt = 0
        self._completion = 0


# ---------------------------------------------------------------------------
# Latency helper
# ---------------------------------------------------------------------------

class LatencyTimer:
    """Context manager that records elapsed time."""

    def __init__(self) -> None:
        self.elapsed: float = 0.0

    def __enter__(self) -> "LatencyTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed = time.perf_counter() - self._start
