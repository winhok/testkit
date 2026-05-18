# testcases.json 示例

```json
{
  "schema_version": 2,
  "testcases": [
    {
      "id": "<需求名称>_202602280001",
      "title": "登录_凭据验证_正确凭据登录成功",
      "feature": "登录",
      "name": "正常登录-有效账号密码",
      "type": "正向",
      "regression_tier": "Smoke",
      "tp_refs": ["TP_LOGIN_CRED_001"],
      "preconditions": "1、系统已启动\n2、用户已注册",
      "steps": "1、打开登录页\n2、输入正确账号密码\n3、点击「登录」按钮",
      "expected_result": "1、登录成功，页面跳转至首页\n2、顶部显示「欢迎回来」提示",
      "priority": "P1"
    }
  ]
}
```
