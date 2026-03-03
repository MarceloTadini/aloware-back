import datetime
import logging
from typing import Annotated

from livekit.agents import function_tool

from repositories import AppointmentRepository

logger = logging.getLogger("aloware.tools")


def make_check_availability(repo: AppointmentRepository):
    async def check_availability(
        date: Annotated[str, "Desired date in YYYY-MM-DD format, e.g. 2026-03-10"],
    ) -> str:
        """Check available appointment slots for a specific date. Use when the patient asks about availability or wants to know open time slots."""
        logger.info("check_availability called for date=%s", date)

        try:
            parsed = datetime.date.fromisoformat(date)
        except ValueError:
            return "I couldn't understand the date you provided. Please say the date as month, day, and year."

        if parsed.weekday() >= 5:  # Saturday=5, Sunday=6
            return "We don't have appointments on weekends. Please choose a weekday."

        available = repo.available_slots(date)

        if not available:
            return f"Unfortunately there are no available slots on {parsed.strftime('%B %d, %Y')}. Would you like to check another day?"

        slots_str = ", ".join(available)
        return (
            f"For {parsed.strftime('%B %d, %Y')} we have the following available times: {slots_str}. "
            "Which time works best for you?"
        )

    return function_tool(check_availability)


def make_book_appointment(repo: AppointmentRepository):
    async def book_appointment(
        date: Annotated[str, "Appointment date in YYYY-MM-DD format, e.g. 2026-03-10"],
        time: Annotated[str, "Appointment time in HH:MM format, e.g. 14:30"],
        patient_name: Annotated[str, "Patient's full name"],
    ) -> str:
        """Confirm and register an appointment for the patient. Only use this after obtaining the date, time, and patient's full name."""
        logger.info("book_appointment | patient=%s | date=%s | time=%s", patient_name, date, time)

        try:
            repo.save_appointment(date, time, patient_name)
        except ValueError:
            return (
                f"The {time} slot on {date} has already been booked. "
                "Would you like to choose a different time?"
            )

        logger.info("Appointment confirmed: date=%s time=%s patient=%s", date, time, patient_name)

        try:
            parsed = datetime.date.fromisoformat(date)
            date_display = parsed.strftime("%B %d, %Y")
        except ValueError:
            date_display = date

        return (
            f"Your appointment has been confirmed for {patient_name} "
            f"on {date_display} at {time}. "
            "You will receive a confirmation shortly. Is there anything else I can help you with?"
        )

    return function_tool(book_appointment)


def make_transfer_to_human():
    async def transfer_to_human() -> str:
        """Transfer the call to a human agent at Aloware Health. Use when the patient requests to speak with a person, or when the situation is beyond your capabilities."""
        logger.info("transfer_to_human called — initiating handoff to human agent")
        return (
            "Of course! I'm transferring your call to one of our agents now. "
            "Please hold for a moment. Thank you for contacting Aloware Health!"
        )

    return function_tool(transfer_to_human)


def build_tool_registry(repo: AppointmentRepository) -> dict:
    """Return a mapping of tool name → FunctionTool, with all tools wired to the given repo."""
    return {
        "check_availability": make_check_availability(repo),
        "book_appointment": make_book_appointment(repo),
        "transfer_to_human": make_transfer_to_human(),
    }
