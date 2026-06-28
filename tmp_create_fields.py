import requests, json

token = 'eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjA1YmRkNzNlLWUyYTItNDc0Ny04ZGFjLTAwY2U1OThiYjllMiJ9.eyJzdWIiOiIyMThiYTZmYi00MWFmLTRhNzMtYTgyMC1lNjkwYTA5NjVjMWUiLCJ0eXBlIjoiQVBJX0tFWSIsIndvcmtzcGFjZUlkIjoiMjE4YmE2ZmItNDFhZi00YTczLWE4MjAtZTY5MGEwOTY1YzFlIiwiaWF0IjoxNzgyNTQ4MDY4LCJleHAiOjQ5MzYxNDgwNjcsImp0aSI6IjQyNTc1YmI4LTllYTYtNGQwMC04MWE3LTNlOWI0NDBkNzI2ZCJ9.0OHcrc2yhB3BsBSi9VS3ajeOHoIVHFfnCVss9E54Tu4PVIVpDFGnuE-GFTTirK4k25wCPSDqH-uY2rEYCL-U7A'

base = 'http://localhost:3000'
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Get object metadata IDs first
r = requests.get(f'{base}/rest/metadata/objects', headers=headers, timeout=10)
objects = r.json().get('data', [])
obj_ids = {}
for obj in objects:
    name = obj.get('nameSingular', '')
    if name in ['mecosLead', 'mecosLeadBrief', 'mecosEmailDraft', 'mecosPayment']:
        obj_ids[name] = obj.get('id')
        print(f'{name}: {obj.get("id")}')

# Create fields for mecosLead
fields_to_create = [
    {'name': 'url', 'type': 'TEXT', 'label': 'URL', 'objectMetadataId': obj_ids.get('mecosLead'), 'isNullable': True},
    {'name': 'domain', 'type': 'TEXT', 'label': 'Domain', 'objectMetadataId': obj_ids.get('mecosLead'), 'isNullable': True},
    {'name': 'totalScore', 'type': 'NUMBER', 'label': 'Total Score', 'objectMetadataId': obj_ids.get('mecosLead'), 'isNullable': True},
    {'name': 'status', 'type': 'TEXT', 'label': 'Status', 'objectMetadataId': obj_ids.get('mecosLead'), 'isNullable': True},
    {'name': 'source', 'type': 'TEXT', 'label': 'Source', 'objectMetadataId': obj_ids.get('mecosLead'), 'isNullable': True},
    {'name': 'contacts', 'type': 'TEXT', 'label': 'Contacts', 'objectMetadataId': obj_ids.get('mecosLead'), 'isNullable': True},
]

for field in fields_to_create:
    r = requests.post(f'{base}/rest/metadata/fields', headers=headers, json=field, timeout=10)
    print(f"Create field {field['name']}: {r.status_code} {r.text[:100]}")
