"""Check what fields exist in Twenty custom objects."""
import requests

base = 'http://localhost:3000'
key = '<SECRET_28c3331a>'
headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

# Query for object metadata via GraphQL
query = '''
{
  mecosLeads(first: 1) {
    edges {
      node {
        id
        url
        domain
        ... on MecosLead {
          __typename
        }
      }
    }
  }
}
'''

r = requests.post(f'{base}/graphql', json={'query': query}, headers=headers, timeout=10)
print(f'Query mecosLeads: {r.status_code}')
print(r.text[:500])

# Try to get object metadata
query2 = '''
{
  __type(name: "MecosLead") {
    name
    fields {
      name
      type {
        name
      }
    }
  }
}
'''
r2 = requests.post(f'{base}/graphql', json={'query': query2}, headers=headers, timeout=10)
print(f'\nQuery MecosLead fields: {r2.status_code}')
print(r2.text[:800])
