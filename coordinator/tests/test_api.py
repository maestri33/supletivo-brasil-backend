"""Integration tests for coordinator API endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    async def test_health(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    async def test_ready(self, client: AsyncClient) -> None:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    async def test_status(self, client: AsyncClient) -> None:
        resp = await client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestCoordinatorAPI:
    BASE = "/api/v1/coordinators"

    async def test_create_coordinator(self, client: AsyncClient) -> None:
        payload = {"external_id": str(uuid4()), "hub_external_id": str(uuid4())}
        resp = await client.post(self.BASE, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["external_id"] == payload["external_id"]
        assert data["hub_external_id"] == payload["hub_external_id"]
        assert data["status"] == "active"
        assert "id" in data

    async def test_list_coordinators(self, client: AsyncClient) -> None:
        # Create two
        payload1 = {"external_id": str(uuid4()), "hub_external_id": str(uuid4())}
        payload2 = {"external_id": str(uuid4()), "hub_external_id": str(uuid4())}
        await client.post(self.BASE, json=payload1)
        await client.post(self.BASE, json=payload2)

        resp = await client.get(self.BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

    async def test_get_coordinator(self, client: AsyncClient) -> None:
        payload = {"external_id": str(uuid4()), "hub_external_id": str(uuid4())}
        create_resp = await client.post(self.BASE, json=payload)
        created_id = create_resp.json()["id"]

        resp = await client.get(f"{self.BASE}/{created_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created_id

    async def test_get_coordinator_404(self, client: AsyncClient) -> None:
        resp = await client.get(f"{self.BASE}/nonexistent-id")
        assert resp.status_code == 404

    async def test_update_coordinator_status(self, client: AsyncClient) -> None:
        payload = {"external_id": str(uuid4()), "hub_external_id": str(uuid4())}
        create_resp = await client.post(self.BASE, json=payload)
        created_id = create_resp.json()["id"]

        resp = await client.patch(f"{self.BASE}/{created_id}", json={"status": "inactive"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    async def test_list_with_hub_filter(self, client: AsyncClient) -> None:
        hub_a, hub_b = str(uuid4()), str(uuid4())
        await client.post(self.BASE, json={"external_id": str(uuid4()), "hub_external_id": hub_a})
        await client.post(self.BASE, json={"external_id": str(uuid4()), "hub_external_id": hub_b})

        resp = await client.get(f"{self.BASE}?hub_external_id={hub_a}")
        data = resp.json()
        for item in data["items"]:
            assert item["hub_external_id"] == hub_a


class TestTrainingApprovalAPI:
    BASE = "/api/v1/training-approvals"
    COORD_BASE = "/api/v1/coordinators"

    @pytest.fixture
    async def coordinator_id(self, client: AsyncClient) -> str:
        payload = {"external_id": str(uuid4()), "hub_external_id": str(uuid4())}
        resp = await client.post(self.COORD_BASE, json=payload)
        return resp.json()["id"]

    async def test_create_approval(self, client: AsyncClient, coordinator_id: str) -> None:
        payload = {
            "coordinator_id": coordinator_id,
            "candidate_external_id": str(uuid4()),
            "training_external_id": str(uuid4()),
        }
        resp = await client.post(self.BASE, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["coordinator_id"] == coordinator_id

    async def test_list_approvals(self, client: AsyncClient, coordinator_id: str) -> None:
        cid = coordinator_id
        await client.post(self.BASE, json={
            "coordinator_id": cid,
            "candidate_external_id": str(uuid4()),
            "training_external_id": str(uuid4()),
        })

        resp = await client.get(self.BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_review_approval(self, client: AsyncClient, coordinator_id: str) -> None:
        create_resp = await client.post(self.BASE, json={
            "coordinator_id": coordinator_id,
            "candidate_external_id": str(uuid4()),
            "training_external_id": str(uuid4()),
        })
        approval_id = create_resp.json()["id"]

        resp = await client.patch(f"{self.BASE}/{approval_id}", json={
            "status": "approved",
            "reason": "Candidate meets requirements",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["reason"] == "Candidate meets requirements"

    async def test_review_approval_invalid_status(self, client: AsyncClient, coordinator_id: str) -> None:
        create_resp = await client.post(self.BASE, json={
            "coordinator_id": coordinator_id,
            "candidate_external_id": str(uuid4()),
            "training_external_id": str(uuid4()),
        })
        approval_id = create_resp.json()["id"]

        resp = await client.patch(f"{self.BASE}/{approval_id}", json={"status": "invalid"})
        assert resp.status_code == 400


class TestEnrollmentFeeAPI:
    BASE = "/api/v1/enrollment-fees"
    COORD_BASE = "/api/v1/coordinators"

    @pytest.fixture
    async def coordinator_id(self, client: AsyncClient) -> str:
        payload = {"external_id": str(uuid4()), "hub_external_id": str(uuid4())}
        resp = await client.post(self.COORD_BASE, json=payload)
        return resp.json()["id"]

    async def test_create_fee(self, client: AsyncClient, coordinator_id: str) -> None:
        payload = {
            "coordinator_id": coordinator_id,
            "student_external_id": str(uuid4()),
            "description": "Matrícula",
            "amount": "150.00",
        }
        resp = await client.post(self.BASE, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Matrícula"
        assert data["status"] == "pending"

    async def test_list_fees(self, client: AsyncClient, coordinator_id: str) -> None:
        cid = coordinator_id
        await client.post(self.BASE, json={
            "coordinator_id": cid,
            "student_external_id": str(uuid4()),
            "description": "Test fee",
            "amount": "100.00",
        })

        resp = await client.get(self.BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_pay_fee(self, client: AsyncClient, coordinator_id: str) -> None:
        create_resp = await client.post(self.BASE, json={
            "coordinator_id": coordinator_id,
            "student_external_id": str(uuid4()),
            "description": "Payable fee",
            "amount": "200.00",
        })
        fee_id = create_resp.json()["id"]

        resp = await client.post(f"{self.BASE}/{fee_id}/pay", json={
            "payment_external_id": str(uuid4()),
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"


class TestExamAPI:
    BASE = "/api/v1/exams"
    COORD_BASE = "/api/v1/coordinators"

    @pytest.fixture
    async def coordinator_id(self, client: AsyncClient) -> str:
        payload = {"external_id": str(uuid4()), "hub_external_id": str(uuid4())}
        resp = await client.post(self.COORD_BASE, json=payload)
        return resp.json()["id"]

    async def test_create_exam(self, client: AsyncClient, coordinator_id: str) -> None:
        payload = {
            "coordinator_id": coordinator_id,
            "student_external_id": str(uuid4()),
            "training_external_id": str(uuid4()),
        }
        resp = await client.post(self.BASE, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"

    async def test_submit_exam(self, client: AsyncClient, coordinator_id: str) -> None:
        create_resp = await client.post(self.BASE, json={
            "coordinator_id": coordinator_id,
            "student_external_id": str(uuid4()),
            "training_external_id": str(uuid4()),
        })
        exam_id = create_resp.json()["id"]

        resp = await client.post(f"{self.BASE}/{exam_id}/submit", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"

    async def test_grade_exam(self, client: AsyncClient, coordinator_id: str) -> None:
        create_resp = await client.post(self.BASE, json={
            "coordinator_id": coordinator_id,
            "student_external_id": str(uuid4()),
            "training_external_id": str(uuid4()),
        })
        exam_id = create_resp.json()["id"]

        resp = await client.post(f"{self.BASE}/{exam_id}/grade", json={
            "score": 85,
            "result_notes": "Bom desempenho",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "graded"
        assert resp.json()["score"] == 85

    async def test_list_exams(self, client: AsyncClient, coordinator_id: str) -> None:
        cid = coordinator_id
        await client.post(self.BASE, json={
            "coordinator_id": cid,
            "student_external_id": str(uuid4()),
            "training_external_id": str(uuid4()),
        })

        resp = await client.get(self.BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


class TestStudentDocumentAPI:
    BASE = "/api/v1/documents"

    async def test_create_document(self, client: AsyncClient) -> None:
        payload = {
            "student_external_id": str(uuid4()),
            "coordinator_external_id": str(uuid4()),
            "document_type": "rg",
            "description": "Cópia RG",
        }
        resp = await client.post(self.BASE, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_type"] == "rg"
        assert data["submitted_to_institution"] is False

    async def test_list_documents(self, client: AsyncClient) -> None:
        await client.post(self.BASE, json={
            "student_external_id": str(uuid4()),
            "coordinator_external_id": str(uuid4()),
            "document_type": "cpf",
            "description": "CPF",
        })

        resp = await client.get(self.BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_submit_document(self, client: AsyncClient) -> None:
        create_resp = await client.post(self.BASE, json={
            "student_external_id": str(uuid4()),
            "coordinator_external_id": str(uuid4()),
            "document_type": "history",
            "description": "Histórico escolar",
        })
        doc_id = create_resp.json()["id"]

        resp = await client.post(f"{self.BASE}/{doc_id}/submit", json={})
        assert resp.status_code == 200
        assert resp.json()["submitted_to_institution"] is True


class TestDiplomaAPI:
    BASE = "/api/v1/diplomas"

    async def test_create_diploma(self, client: AsyncClient) -> None:
        payload = {
            "student_external_id": str(uuid4()),
            "coordinator_external_id": str(uuid4()),
        }
        resp = await client.post(self.BASE, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"

    async def test_list_diplomas(self, client: AsyncClient) -> None:
        await client.post(self.BASE, json={
            "student_external_id": str(uuid4()),
            "coordinator_external_id": str(uuid4()),
        })

        resp = await client.get(self.BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_graduate(self, client: AsyncClient) -> None:
        create_resp = await client.post(self.BASE, json={
            "student_external_id": str(uuid4()),
            "coordinator_external_id": str(uuid4()),
        })
        diploma_id = create_resp.json()["id"]

        resp = await client.post(f"{self.BASE}/{diploma_id}/graduate", json={
            "diploma_photo_path": "/photos/diploma.jpg",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "graduated"
