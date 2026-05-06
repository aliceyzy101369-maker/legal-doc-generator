# Contract Review API

Standalone backend service for contract review.

## Run

```bash
uvicorn contract_review_api.main:app --reload
```

## Endpoints

- `GET /health`
- `POST /reviews`
- `GET /reviews/{review_id}`

## Example Request

```json
{
  "text": "甲方：A公司\n\n乙方：B公司\n\n项目名称：示例项目\n\n自2026年1月1日至2026年12月31日",
  "ruleset_ids": ["base-rules"],
  "user_position": "受让人"
}
```
