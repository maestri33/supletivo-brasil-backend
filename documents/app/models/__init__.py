from app.models.cnh import CNH
from app.models.document import CERTIFICATE_KINDS, Document
from app.models.passport import Passport
from app.models.rg import RG
from app.models.work_card import WorkCard

__all__ = [
    "Document",
    "RG",
    "CNH",
    "WorkCard",
    "Passport",
    "CERTIFICATE_KINDS",
]
