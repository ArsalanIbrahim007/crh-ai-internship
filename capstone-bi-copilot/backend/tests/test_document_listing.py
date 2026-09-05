def test_document_list_requires_session(client):
    assert client.get('/api/documents').status_code == 401


def test_document_list_obeys_roles(client):
    client.post('/api/documents/upload', files={'file': ('visible.txt', b'Visible workspace document', 'text/plain')}, data={'allowed_roles': 'admin'})
    client.post('/api/documents/upload', files={'file': ('restricted.txt', b'Restricted document', 'text/plain')}, data={'allowed_roles': 'executive'})
    login = client.post('/api/auth/login', json={'email': 'admin@example.com', 'password': 'Admin123!'})
    assert login.status_code == 200
    response = client.get('/api/documents')
    assert response.status_code == 200
    assert [item['filename'] for item in response.json()] == ['visible.txt']
    assert response.json()[0]['created_at']
