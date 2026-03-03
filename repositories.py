import abc
import datetime
import json
import logging
from pathlib import Path

logger = logging.getLogger("aloware.repositories")

APPOINTMENTS_PATH = Path(__file__).parent / "appointments.json"


class AppointmentRepository(abc.ABC):
    SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "14:00", "14:30", "15:00", "15:30", "16:00"]

    @abc.abstractmethod
    def get_booked_times(self, date: str) -> set[str]: ...

    @abc.abstractmethod
    def save_appointment(self, date: str, time: str, patient: str, phone: str = "") -> None:
        """Raise ValueError if slot already taken."""
        ...

    @abc.abstractmethod
    def list_appointments(self, date: str | None = None) -> list[dict]: ...

    def available_slots(self, date: str) -> list[str]:
        taken = self.get_booked_times(date)
        return [s for s in self.SLOTS if s not in taken]


class JsonAppointmentRepository(AppointmentRepository):
    """Persistent store backed by a local JSON file."""

    def __init__(self, path: Path = APPOINTMENTS_PATH) -> None:
        self._path = path

    def _read(self) -> list[dict]:
        if not self._path.exists():
            return []
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, appointments: list[dict]) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(appointments, f, ensure_ascii=False, indent=2)
            logger.info("appointments.json written (%d entries) → %s", len(appointments), self._path)
        except OSError as e:
            logger.error("Failed to write appointments.json: %s", e)
            raise

    def get_booked_times(self, date: str) -> set[str]:
        return {a["time"] for a in self._read() if a["date"] == date}

    def save_appointment(self, date: str, time: str, patient: str, phone: str = "") -> None:
        logger.info("save_appointment called: patient=%s date=%s time=%s", patient, date, time)
        appointments = self._read()
        if any(a["date"] == date and a["time"] == time for a in appointments):
            raise ValueError(f"Slot {time} on {date} already booked")
        appointments.append({
            "date": date,
            "time": time,
            "patient": patient,
            "phone": phone,
            "created_at": datetime.datetime.utcnow().isoformat(),
        })
        self._write(appointments)

    def list_appointments(self, date: str | None = None) -> list[dict]:
        appointments = self._read()
        if date:
            appointments = [a for a in appointments if a["date"] == date]
        return sorted(appointments, key=lambda a: (a["date"], a["time"]))
