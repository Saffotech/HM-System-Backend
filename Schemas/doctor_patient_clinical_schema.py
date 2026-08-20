from Schemas.common_schema import PaginatedResponse
from Schemas.nurse_schema import VitalResponse, NursingNoteResponse


class DoctorVitalsResponse(PaginatedResponse[VitalResponse]):
    pass


class DoctorNotesResponse(PaginatedResponse[NursingNoteResponse]):
    pass
