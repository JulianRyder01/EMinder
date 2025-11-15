import requests

msg = requests.get("http://127.0.0.1:8000/api/templates/info")

print(msg.json())   