# 示例项目

## 目录结构

```
my-api-tests/
├── project.yaml
├── flows/
│   └── auth.yaml
├── cases/
│   ├── test_sample.yaml
│   ├── test_user_crud.yaml
│   └── test_user_failures.yaml
└── config/
    └── .env.example
```

## project.yaml

```yaml
project:
  name: sample-api-project
  base_url: ${ENV.BASE_URL}
  vars: {}
  defaults:
    headers:
      Content-Type: application/json
  report:
    allure_results_dir: allure-results
    structured_results_file: reports/results.json
```

## flows/auth.yaml

```yaml
flows:
  user_auth_flow:
    steps:
      - name: login
        request:
          method: POST
          url: /auth/login
          json:
            username: ${ENV.TEST_USER}
            password: ${ENV.TEST_PASS}
        extract:
          token: $.data.token
          user_id: $.data.user.id
        validate:
          - eq: [status_code, 200]
          - exists: $.data.token
```

## cases/test_sample.yaml

```yaml
cases:
  - id: sample_health_check
    name: sample health check
    steps:
      - name: health
        request:
          method: GET
          url: /health
        validate:
          - eq: [status_code, 200]
```

## cases/test_user_crud.yaml

```yaml
cases:
  - id: user_crud_happy_path
    name: user crud happy path
    tags: [smoke, crud]
    steps:
      - use: flow:user_auth_flow

      - name: create_user
        request:
          method: POST
          url: /api/v1/users
          headers:
            Authorization: Bearer ${vars.token}
          json:
            username: user001
            email: user001@example.com
        extract:
          created_user_id: $.data.id
        validate:
          - eq: [status_code, 200]
          - exists: $.data.id

      - name: get_user
        request:
          method: GET
          url: /api/v1/users/${vars.created_user_id}
          headers:
            Authorization: Bearer ${vars.token}
        validate:
          - eq: [status_code, 200]
          - exists: $.data.id

      - name: update_user
        request:
          method: PUT
          url: /api/v1/users/${vars.created_user_id}
          headers:
            Authorization: Bearer ${vars.token}
          json:
            email: user001-updated@example.com
        validate:
          - eq: [status_code, 200]

      - name: delete_user
        request:
          method: DELETE
          url: /api/v1/users/${vars.created_user_id}
          headers:
            Authorization: Bearer ${vars.token}
        validate:
          - eq: [status_code, 200]
```

## cases/test_user_failures.yaml

```yaml
cases:
  - id: login_missing_password
    name: login missing password
    tags: [negative, auth]
    steps:
      - name: login_fail
        request:
          method: POST
          url: /auth/login
          json:
            username: ${ENV.TEST_USER}
        validate:
          - eq: [status_code, 400]

  - id: unauthorized_profile
    name: unauthorized profile
    tags: [negative, authz]
    steps:
      - name: get_profile_without_token
        request:
          method: GET
          url: /api/v1/profile
        validate:
          - eq: [status_code, 401]
```

## config/.env.example

```
BASE_URL=http://localhost:8080
TEST_USER=CHANGE_ME_TEST_USER
TEST_PASS=CHANGE_ME_TEST_PASS
```
