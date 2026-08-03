from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.models.administration import CrewMember
from app.services.administration_catalog import ENTITY_DEFINITIONS


def test_administration_index_lists_core_sections(client: TestClient) -> None:
    response = client.get("/admin")

    assert response.status_code == 200
    assert "Locations" in response.text
    assert "Linked equipment" in response.text
    assert "Tentmaster memberships" in response.text
    assert "Lorry types" in response.text
    assert "Crew availability" not in response.text
    assert "Availability windows" not in response.text


def test_all_administration_sections_and_forms_render(client: TestClient, session: Session) -> None:
    seed_development_data(session)

    for definition in ENTITY_DEFINITIONS:
        assert client.get(f"/admin/{definition.slug}").status_code == 200
        assert client.get(f"/admin/{definition.slug}/new").status_code == 200


def test_location_crud_flow(client: TestClient) -> None:
    create_response = client.post(
        "/admin/locations/new",
        data={
            "name": "Route Test Yard",
            "location_type": "yard",
            "country_code": "GB",
            "timezone": "Europe/London",
            "default_unload_duration_minutes": "45",
            "active": "true",
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 303
    detail_url = create_response.headers["location"]
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "Route Test Yard" in detail_response.text

    edit_response = client.post(
        f"{detail_url}/edit",
        data={
            "name": "Updated Route Test Yard",
            "location_type": "yard",
            "country_code": "GB",
            "timezone": "Europe/London",
            "default_unload_duration_minutes": "45",
            "active": "true",
        },
        follow_redirects=False,
    )
    assert edit_response.status_code == 303
    assert "Updated Route Test Yard" in client.get(detail_url).text
    assert "Updated Route Test Yard" in client.get("/admin/locations").text

    delete_response = client.post(f"{detail_url}/delete", follow_redirects=False)
    assert delete_response.status_code == 303
    assert "Updated Route Test Yard" not in client.get("/admin/locations").text


def test_new_crew_member_form_defaults_to_monkey_and_crew(
    client: TestClient, session: Session
) -> None:
    seed_development_data(session)

    response = client.get("/admin/crew-members/new")

    assert response.status_code == 200
    assert '<option value="1" selected>Monkey</option>' in response.text
    assert '<option value="1" selected>Crew</option>' in response.text


def test_crew_member_edit_page_manages_availability_inline(
    client: TestClient, session: Session
) -> None:
    seed_development_data(session)
    member = session.scalar(select(CrewMember))
    assert member is not None
    member_id = member.id
    edit_url = f"/admin/crew-members/{member_id}/edit"

    add_leave = client.post(
        "/admin/crew-availability/new",
        data={
            "crew_member_id": str(member_id),
            "start_at": "2026-07-01",
            "end_at": "2026-07-05",
            "status": "leave",
            "redirect_to": edit_url,
        },
        follow_redirects=False,
    )
    assert add_leave.status_code == 303
    assert add_leave.headers["location"] == edit_url

    add_window = client.post(
        "/admin/crew-availability-windows/new",
        data={
            "crew_member_id": str(member_id),
            "start_at": "2026-05-01",
            "redirect_to": edit_url,
        },
        follow_redirects=False,
    )
    assert add_window.status_code == 303
    assert add_window.headers["location"] == edit_url

    edit_page = client.get(edit_url)
    assert edit_page.status_code == 200
    assert "2026-07-01" in edit_page.text
    assert "2026-05-01" in edit_page.text
    assert "redirect_to" in edit_page.text

    assert client.get("/admin/crew-availability").status_code == 200


def test_crew_role_and_employment_type_crud_flow(client: TestClient) -> None:
    role_response = client.post(
        "/admin/crew-roles/new",
        data={"name": "Rigger", "active": "true"},
        follow_redirects=False,
    )
    assert role_response.status_code == 303

    type_response = client.post(
        "/admin/crew-employment-types/new",
        data={"name": "Freelance", "active": "true"},
        follow_redirects=False,
    )
    assert type_response.status_code == 303

    member_form = client.get("/admin/crew-members/new")
    assert "Rigger" in member_form.text
    assert "Freelance" in member_form.text
