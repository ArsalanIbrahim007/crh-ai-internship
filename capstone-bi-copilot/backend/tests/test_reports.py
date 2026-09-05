def test_exports(client):
    rows=[{"a":1,"b":2}]
    assert client.post("/api/reports/export/csv",json=rows).status_code==200
    assert client.post("/api/reports/export/xlsx",json=rows).content[:2]==b"PK"
    assert client.post("/api/reports/export/pdf",params={"title":"T","summary":"S"}).content.startswith(b"%PDF")
