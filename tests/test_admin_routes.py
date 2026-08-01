from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.commands.seed import seed_development_data
from app.services.administration_catalog import ENTITY_DEFINITIONS


def test_administration_index_lists_core_sections(client: TestClient) -> None:
    response = client.get("/admin")

    assert response.status_code == 200
    assert "Locations" in response.text
    assert "Tent configurations" in response.text
    assert "Tentmaster memberships" in response.text
    assert "Lorry types" in response.text


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
