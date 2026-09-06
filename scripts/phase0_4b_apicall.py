"""Phase 0.4b: 直接 HTTP POST list-files 看 API 是否真返回文件列表"""
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8765/api/auth/login',
    data=b'username=admin&password=akwj210627',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
try:
    body = urllib.request.urlopen(req, timeout=10).read().decode()
    print('login OK:', body[:80])
    token = json.loads(body)['access_token']
except Exception as e:
    print('login ERR:', e)
    exit()

req = urllib.request.Request('http://127.0.0.1:8765/api/file-storage/list-files',
    data=json.dumps({'project_id':4, 'folder_type':'tender'}).encode(),
    headers={'Content-Type':'application/json', 'Authorization': f'Bearer {token}'})
try:
    body = urllib.request.urlopen(req, timeout=10).read().decode()
    print('list-files OK (tender):', body[:2000])
except Exception as e:
    print('list-files ERR:', e)

req2 = urllib.request.Request('http://127.0.0.1:8765/api/file-storage/list-files',
    data=json.dumps({'project_id':4, 'folder_type':'bid'}).encode(),
    headers={'Content-Type':'application/json', 'Authorization': f'Bearer {token}'})
try:
    body = urllib.request.urlopen(req2, timeout=10).read().decode()
    print('list-files OK (bid):', body[:2000])
except Exception as e:
    print('list-files ERR:', e)
