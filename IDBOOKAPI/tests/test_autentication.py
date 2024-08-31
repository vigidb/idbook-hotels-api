import pytest
import requests

BASE_URL = "http://127.0.0.1:8000" + "/api/v1/"

URLS = {
        "authentication": [
            "users",
            "roles",
            "groups",
            "permissions"
        ]
    }


@pytest.mark.parametrize("url", URLS['authentication'])
def test_authentication_list_api(url):
    # Send the get request to the APIs
    response = requests.get(BASE_URL + url)

    # Verify the response
    assert response.status_code == 200
    assert response.headers['Content-type'] == 'application/json'

