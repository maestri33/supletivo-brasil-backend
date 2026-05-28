"""Rotas autenticadas do promoter (JWT role promoter, promoter ativo).

Visao do proprio promoter: seus dados, seus leads (agregados do `lead`) e suas
comissoes (agregadas do `commissions`). Tudo read-only — o promoter nao e' dono
desses dominios (CONVENTION §6).
"""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_promoter
from app.models import Promoter
from app.schemas.commissions import CommissionListResponse, CommissionView
from app.schemas.leads import LeadListResponse, LeadView
from app.schemas.promoter import PromoterOut
from app.services import commissions as commissions_svc
from app.services import leads as leads_svc
from app.services import notifications

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/me", response_model=PromoterOut, summary="Dados do promoter autenticado")
async def me(promoter: Promoter = Depends(get_current_promoter)):
    out = PromoterOut.model_validate(promoter, from_attributes=True)
    out.ref_url = notifications.ref_url(promoter.external_id)
    return out


@router.get("/me/leads", response_model=LeadListResponse, summary="Leads captados pelo promoter")
async def my_leads(promoter: Promoter = Depends(get_current_promoter)):
    rows = await leads_svc.list_for_promoter(promoter.external_id)
    leads = [LeadView.model_validate(r) for r in rows]
    return LeadListResponse(total=len(leads), leads=leads)


@router.get(
    "/me/commissions",
    response_model=CommissionListResponse,
    summary="Comissoes do promoter",
)
async def my_commissions(promoter: Promoter = Depends(get_current_promoter)):
    available, rows = await commissions_svc.list_for_promoter(promoter.external_id)
    commissions = [CommissionView.model_validate(r) for r in rows]
    return CommissionListResponse(
        total=len(commissions), available=available, commissions=commissions
    )
