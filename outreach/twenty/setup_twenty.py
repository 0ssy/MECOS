"""
MECOS Outreach - Twenty CRM Object Setup
Creates custom objects and fields in Twenty CRM via GraphQL.
Run this after starting your Twenty instance: python -m outreach.twenty.setup_twenty
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import requests
from loguru import logger

from config import settings
from outreach.twenty.schema import ALL_OBJECTS, ObjectDef


class TwentySetup:
    def __init__(self):
        self.api_url = getattr(settings, "TWENTY_CRM_API_URL", "").rstrip("/")
        self.api_key = getattr(settings, "TWENTY_CRM_API_KEY", "")
        self.graphql_url = f"{self.api_url}/graphql"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})

    def _request(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        try:
            resp = self.session.post(self.graphql_url, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Twenty setup request failed: {e}")
            return {"data": None, "errors": [{"message": str(e)}]}

    def create_object(self, obj: ObjectDef) -> Optional[str]:
        query = """
        mutation CreateObject($input: CreateObjectInput!) {
          createObject(input: $input) {
            object {
              id
              name
            }
          }
        }
        """
        variables = {
            "input": {
                "name": obj.name,
                "labelSingular": obj.label_singular,
                "labelPlural": obj.label_plural,
            }
        }
        result = self._request(query, variables)
        data = result.get("data") or {}
        obj_data = data.get("createObject", {}).get("object")
        if obj_data:
            logger.info(f"Created object: {obj.name} (id: {obj_data.get('id')})")
            return obj_data.get("id")
        logger.error(f"Failed to create object {obj.name}: {result.get('errors')}")
        return None

    def create_field(self, object_id: str, field: Any, is_relation: bool = False) -> bool:
        query = """
        mutation CreateField($input: CreateFieldInput!) {
          createField(input: $input) {
            field {
              id
              name
            }
          }
        }
        """
        field_input: Dict[str, Any] = {
            "objectId": object_id,
            "name": field.name,
            "type": field.type,
            "label": field.label or field.name,
            "isRequired": field.required,
        }
        if is_relation and field.relation_to:
            field_input["relationTargetObjectId"] = field.relation_to
        variables = {"input": field_input}
        result = self._request(query, variables)
        data = result.get("data") or {}
        field_data = data.get("createField", {}).get("field")
        if field_data:
            logger.info(f"  Created field: {field.name} ({field.type})")
            return True
        logger.error(f"  Failed to create field {field.name}: {result.get('errors')}")
        return False

    def setup_all(self) -> bool:
        logger.info("Setting up Twenty CRM custom objects for MECOS...")
        object_ids: Dict[str, str] = {}

        for obj in ALL_OBJECTS:
            obj_id = self.create_object(obj)
            if not obj_id:
                logger.error(f"Aborting: failed to create object {obj.name}")
                return False
            object_ids[obj.name] = obj_id
            time.sleep(0.5)

        for obj in ALL_OBJECTS:
            obj_id = object_ids.get(obj.name)
            if not obj_id:
                continue
            logger.info(f"Creating fields for {obj.name}...")
            for field in obj.fields:
                is_relation = field.type == "RELATION"
                self.create_field(obj_id, field, is_relation=is_relation)
                time.sleep(0.3)

        logger.info("Twenty CRM setup complete.")
        return True


def main():
    setup = TwentySetup()
    success = setup.setup_all()
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
