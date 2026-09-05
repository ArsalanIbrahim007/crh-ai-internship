def test_login_and_me(client):
    r=client.post("/api/auth/login",json={"email":"admin@example.com","password":"Admin123!"}); assert r.status_code==200
    token=r.json()["access_token"]; me=client.get("/api/auth/me",headers={"Authorization":f"Bearer {token}"}); assert me.status_code==200; assert me.json()["role"]=="admin"
def test_bad_login(client): assert client.post("/api/auth/login",json={"email":"admin@example.com","password":"bad"}).status_code==401


def test_opt_in_development_identity(client):
    from app.core.config import get_settings
    settings = get_settings()
    previous_environment = settings.environment
    previous_email = settings.development_auth_email
    try:
        settings.environment = "development"
        settings.development_auth_email = "admin@example.com"
        response = client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["email"] == "admin@example.com"
    finally:
        settings.environment = previous_environment
        settings.development_auth_email = previous_email


def test_development_identity_never_applies_in_production(client):
    from app.core.config import get_settings
    settings = get_settings()
    previous_environment = settings.environment
    previous_email = settings.development_auth_email
    try:
        settings.environment = "production"
        settings.development_auth_email = "admin@example.com"
        assert client.get("/api/auth/me").status_code == 401
    finally:
        settings.environment = previous_environment
        settings.development_auth_email = previous_email
