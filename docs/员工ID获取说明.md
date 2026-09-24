# 员工 ID 获取说明

## 1. 基础地址

将 `BASE_URL` 替换为图床系统实际访问地址。

```text
BASE_URL=https://qiyeimage.xiaoc-ai.com
```

接口基础路径为：

```text
BASE_URL/api
```

## 2. 登录获取令牌

调用员工信息接口前，必须先登录。

### 请求

```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded
```

表单参数：

| 参数 | 必填 | 说明 |
|---|---|---|
| `username` | 是 | 系统账号 |
| `password` | 是 | 系统密码 |

成功响应：

```json
{
  "access_token": "登录令牌",
  "token_type": "bearer"
}
```

后续请求添加：

```http
Authorization: Bearer 登录令牌
```

## 3. 获取当前账号的员工 ID

适用于外部项目使用一个固定账号调用图床系统。

### 请求

```http
GET {BASE_URL}/api/auth/me
Authorization: Bearer 登录令牌
```

### 返回示例

```json
{
  "id": 5,
  "employee_id": "TEST1",
  "username": "test_user",
  "role": "employee",
  "supervisor_id": null,
  "is_active": true,
  "created_at": "2026-09-08T12:00:00"
}
```

员工 ID 为：

```text
employee_id=TEST1
```

后续拼接图片业务 URL 时，使用返回的 `employee_id`。

## 4. 获取员工账号列表

适用于外部项目需要同步或选择多个员工 ID。

### 请求

```http
GET {BASE_URL}/api/users
Authorization: Bearer 登录令牌
```

### 返回示例

```json
[
  {
    "id": 5,
    "employee_id": "TEST1",
    "username": "test_user",
    "role": "employee",
    "supervisor_id": 2,
    "is_active": true,
    "created_at": "2026-09-08T12:00:00"
  }
]
```

从每个对象的 `employee_id` 字段读取员工 ID。

### 权限

- 管理员：可以获取全部用户；
- 主管：只能获取自己名下的员工；
- 普通员工：无权调用该接口，接口返回 `403`。

## 5. 推荐方式

如果外部项目使用固定账号上传图片，使用以下流程：

```text
1. POST /api/auth/login，获取 access_token
2. GET /api/auth/me，获取 employee_id
3. POST /api/images/upload，上传图片
```

如果外部项目需要获取多个员工 ID，使用 `GET /api/users`，但调用账号必须是管理员或主管。

当前没有无需登录即可获取员工 ID 的公开接口。
