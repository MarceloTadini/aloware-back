import abc


class AppointmentRepository(abc.ABC):
    SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "14:00", "14:30", "15:00", "15:30", "16:00"]

    @abc.abstractmethod
    def get_booked_times(self, date: str) -> set[str]: ...

    @abc.abstractmethod
    def save_appointment(self, date: str, time: str, patient: str) -> None:
        """Raise ValueError if slot already taken."""
        ...

    def available_slots(self, date: str) -> list[str]:
        taken = self.get_booked_times(date)
        return [s for s in self.SLOTS if s not in taken]


class InMemoryAppointmentRepository(AppointmentRepository):
    def __init__(self) -> None:
        self._booked: list[dict] = []

    def get_booked_times(self, date: str) -> set[str]:
        return {b["time"] for b in self._booked if b["date"] == date}

    def save_appointment(self, date: str, time: str, patient: str) -> None:
        if time in self.get_booked_times(date):
            raise ValueError(f"Slot {time} on {date} already booked")
        self._booked.append({"date": date, "time": time, "patient": patient})
