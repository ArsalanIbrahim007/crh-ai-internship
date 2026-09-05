import io
def test_upload_and_search(client):
    files={"file":("policy.txt",b"Employees receive 12 paid sick leave days per calendar year.","text/plain")}
    up=client.post("/api/documents/upload",files=files); assert up.status_code==200
    s=client.get("/api/documents/search",params={"q":"sick leave days"}); assert s.status_code==200; assert s.json(); assert s.json()[0]["title"]=="policy.txt"
